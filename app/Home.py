import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
import streamlit as st
from datetime import datetime
from modules.nlp_extractor import extract_entities
from modules.rag_engine import load_and_normalize_data, build_embeddings, INDEX_FILE, META_FILE  # New RAG imports

# Add project root to sys.path (go up one directory from app/)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets /app/ dir
css_path = os.path.join(current_dir, 'assets', 'style.css')  # Builds full path

# Load and inject CSS
with open(css_path, 'r') as f:
    css_content = f.read()

st.markdown(
    f"<style>{css_content}</style>",
    unsafe_allow_html=True
)
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.sidebar.image("app/assets/img.png", use_container_width=True)
st.sidebar.markdown("### ✈️ AI Travel Planner")
st.sidebar.write("Personalized itineraries using Generative AI")
st.sidebar.markdown("---")
st.sidebar.subheader("🧭 Navigation")

st.sidebar.page_link("Home.py", label="🏠 Home")
st.sidebar.page_link("pages/1_Travel_Results.py", label="📍 Travel Results")
st.sidebar.page_link("pages/2_Itinerary_Generator.py", label="🧳 Itinerary Generator")

# -------------------------------------------------------------
# --- RAG INDEX SETUP (OPTIONAL) ---
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ RAG Index Control")

# Initialize session state for RAG status
if 'rag_index_built' not in st.session_state:
    # Check if files already exist on startup (for persistence in Streamlit Cloud)
    faiss_exists = os.path.exists(INDEX_FILE)
    meta_exists = os.path.exists(META_FILE)
    st.session_state.rag_index_built = faiss_exists and meta_exists


def build_rag_index_action():
    """Function to load data and build the FAISS index synchronously."""
    # Reset status temporarily
    st.session_state.rag_index_built = False

    try:
        with st.spinner("Loading attraction data..."):
            entries = load_and_normalize_data()
            if not entries:
                raise ValueError("Attraction data is empty. Cannot build index.")

        with st.spinner("Building vector index (may take 30-60 seconds)..."):
            # This is the synchronous, heavy lifting call
            build_embeddings(entries)

        st.session_state.rag_index_built = True
        st.success("✅ Attraction Index Built Successfully! You can now generate itineraries.")

    except Exception as e:
        st.session_state.rag_index_built = False
        st.error(f"❌ Error building RAG index: {e}.")
        st.exception(e)


if st.session_state.rag_index_built:
    st.sidebar.success("Index Status: Built")
else:
    st.sidebar.warning("Index Status: Not Built (Will use general knowledge)")

    # Use the button to trigger the build function
    if st.sidebar.button("⚙️ Build Attraction Index", type="primary"):
        build_rag_index_action()
# -------------------------------------------------------------


# --- Title ---
st.title("🌍 Plan Your Next Adventure")
st.caption("Let AI craft your perfect trip based on budget, duration, and even weather constraints.")

# --- Examples Section ---
st.markdown("### 💡 Input Examples:")

st.markdown(
    """
    Provide your travel request in natural language. The AI will extract the **destination**, **duration**, **budget**, and **date**.
    """,
    unsafe_allow_html=True
)

# --- Start of Colored Examples ---
st.markdown(
    """
    <div style="background-color: #f0f8ff; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #007bff;">
        <b>1. Standard:</b>
        <br>
        Plan a <span style="color: #28a745; font-weight: bold;">4-day</span> trip to <span style="color: #6f42c1; font-weight: bold;">Miami</span> in <span style="color: #ffc107; font-weight: bold;">December</span> for <span style="color: #dc3545; font-weight: bold;">under $1000</span>.
    </div>
    <div style="background-color: #fff8f2; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #fd7e14;">
        <b>2. Specific Date:</b>
        <br>
        I need a <span style="color: #28a745; font-weight: bold;">5-night</span> itinerary for <span style="color: #6f42c1; font-weight: bold;">Paris</span> starting from <span style="color: #ffc107; font-weight: bold;">2026-03-20</span>.
    </div>
    <div style="background-color: #f2fcf5; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #28a745;">
        <b>3. Minimal:</b>
        <br>
        <span style="color: #6f42c1; font-weight: bold;">New York</span> for <span style="color: #28a745; font-weight: bold;">a week</span> with a <span style="color: #dc3545; font-weight: bold;">$1500 budget</span>.
    </div>
    <div style="background-color: #f7f0ff; padding: 10px; border-radius: 8px; border-left: 5px solid #6f42c1;">
        <b>4. General:</b>
        <br>
        Show me things to do in <span style="color: #6f42c1; font-weight: bold;">London</span> <span style="color: #ffc107; font-weight: bold;">next month</span>.
    </div>
    """,
    unsafe_allow_html=True,
)

user_query = st.text_input("Enter your Plan:")
# The st.text_input() for user input follows this block.
col1, col2 = st.columns([1, 3])
with col1:
    generate = st.button("✨ Generate Plan")
with col2:
    st.caption("AI will extract details and prepare your plan instantly!")

if generate:
    if not user_query.strip():
        st.warning("Please enter a travel request first.")
    # REMOVED: Mandatory check for st.session_state.rag_index_built
    else:
        with st.spinner("Analyzing your request..."):
            details = extract_entities(user_query)
            destination = details.get("destination")
            budget = details.get("budget")
            duration = details.get("duration")
            date = details.get("date")

            st.session_state.update({
                "query": user_query,
                "destination": destination,
                "budget": budget,
                "duration": duration,
                "date": date,
            })

        st.success(
            f"✅ Destination: **{destination}** | Budget: **${budget}** | Duration: **{duration} days** | Date: **{date}**")
        st.balloons()
        st.switch_page("pages/2_Itinerary_Generator.py")