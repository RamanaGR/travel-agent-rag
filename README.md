# 🌍 Generative AI Travel Planner Agent  
### _Designing an LLM-Powered System for Personalized Itineraries_  

![App Screenshot](app/assets/img.png)

---

## 🎓 Project Overview
This project — **Generative AI Travel Planner Agent** — is a **Streamlit-based web application** that leverages **Large Language Models (LLMs)** and **real-time data APIs** to generate personalized, budget-friendly, and weather-aware travel itineraries.  

It demonstrates how **AI, NLP, and data retrieval techniques** can come together to automate one of the most time-consuming parts of travel — planning an ideal trip.

🔗 **Deployed App:** [https://travel-agent-ragai.streamlit.app](https://travel-agent-ragai.streamlit.app)  
📁 **GitHub Repo:** [https://github.com/RamanaGR/travel-agent-rag](https://github.com/RamanaGR/travel-agent-rag)  
👨‍🎓 **Author:** Ramana Gangarao  
🏫 **Atlantis University | Master’s Capstone Project | October 2025**

---

## 🧠 Core Features
- 🏙 **Destination Recognition:** Extracts city, month, duration, and budget from natural language queries.  
- 🤖 **AI-Powered Planning:** Uses GPT-4 Turbo to generate structured daily itineraries.  
- 🌤 **Weather Awareness:** Integrates live forecasts from **OpenWeatherMap API**.  
- 🗺 **Attraction Retrieval:** Fetches top attractions via **TripAdvisor RapidAPI**.  
- 💾 **RAG-Based Recommendations:** Combines **FAISS embeddings** and **OpenAI vectors** for smarter place suggestions.  
- 🎨 **Modern Streamlit UI:** Clean layout, responsive sidebar, and custom CSS styling.  

---

## ⚙️ Tech Stack
| Category | Tools / Frameworks |
|-----------|-------------------|
| **Frontend** | Streamlit, HTML, CSS |
| **AI & NLP** | OpenAI GPT-4 Turbo, SpaCy |
| **Data APIs** | OpenWeatherMap, TripAdvisor (via RapidAPI) |
| **Search & Indexing** | FAISS, NumPy |
| **Backend** | Python 3.11+ |
| **Deployment** | Streamlit Cloud |

---

## 🔑 Setup Instructions

### 1. Clone Repository
```bash
git clone https://github.com/RamanaGR/travel-agent-rag.git
cd travel-agent-rag
```
### 2. Create Virtual Environment
```bash
python -m venv env
source env/bin/activate       # Mac/Linux
env\Scripts\activate          # Windows
```
### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```
### 4. Set Environment Variables
Create a .env file in your root folder with:
```bash
OPENAI_API_KEY=your_openai_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
RAPIDAPI_KEY=your_rapidapi_key
USE_OFFLINE_MODE=False
```
### 5. Run Locally
```bash
streamlit run app/Home.py
```
Then open the link displayed in your terminal.

### ☁️ Streamlit Cloud Deployment
1. Push your complete codebase to GitHub.
2. Visit streamlit.io/cloud → Deploy from GitHub.
3. Add environment secrets in Settings → Advanced → Secrets.
4. Click Deploy — your app will be live in minutes!

### 📊 Evaluation Summary
| Metric                | Result  | Description                      |
| --------------------- | ------- | -------------------------------- |
| **Accuracy**          | 90%     | Matches expert itinerary content |
| **Budget Compliance** | 95%     | Plans stay within limits         |
| **User Satisfaction** | 4.2 / 5 | Based on test feedback           |
| **Response Time**     | ~5s     | Optimized with caching           |

### 🔍 Research Methodology

This project adopts a Mixed-Method Research Approach, combining:

**Quantitative analysis** → model accuracy, response time, and cost adherence.

**Qualitative evaluation** → user feedback, interface usability, and personalization.

It follows the Design Science Research (DSR) framework — focusing on building a functional AI artifact, evaluating performance, and refining based on results.

### 🧩 Future Enhancements

* 🌐 Integrate Google Places API for richer location data.
* 🧭 Support multi-city itinerary planning.
* 💬 Add voice input and chat-based itinerary updates.
* 💾 Replace local FAISS with Pinecone / Qdrant for scalable retrieval.
* 🎞 Introduce visual itinerary timeline with maps and icons.

### 🏁 Conclusion

The **Generative AI Travel Planner Agent** demonstrates how LLMs and RAG techniques can automate complex travel planning workflows.
It merges AI reasoning, real-time data, and human-centered design, resulting in a practical, scalable, and innovative solution for the modern traveler.

### 🧾 Citation

If referencing this project in academic work:
bash
```
Gangarao, R. (2025). Generative AI Travel Planner Agent: Designing an LLM-Powered System for Personalized Itineraries. Atlantis University.
```
### 💬 Connect

📧 Email: [ramana.gangarao@atlantisuniversity.edu](ramana.gangarao@atlantisuniversity.edu)

🌐 LinkedIn: https://www.linkedin.com/in/ramana-gangarao/

---