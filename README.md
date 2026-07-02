# Generative AI Travel Planner Agent

Streamlit web application that uses LLMs and real-time APIs to generate personalized, budget-friendly, and weather-aware travel itineraries.

**Deployed app:** [travel-agent-ragai.streamlit.app](https://travel-agent-ragai.streamlit.app)

## Features

- Natural-language trip planning (destination, budget, duration, date)
- Hybrid RAG attraction ranking (FAISS + BM25 + metadata fusion)
- GPT-4o itinerary generation with grounding and source citations
- OpenWeatherMap 5-day forecast integration
- TripAdvisor attractions via RapidAPI
- Per-city FAISS indexes with embedding cache
- Four switchable UI themes (default: **Sunset Wanderlust**)

## Tech Stack

| Category | Tools |
|----------|-------|
| Frontend | Streamlit, CSS themes |
| AI & NLP | OpenAI GPT-4o, spaCy |
| Data APIs | OpenWeatherMap, TripAdvisor (RapidAPI) |
| Search | FAISS, BM25 (rank-bm25), NumPy |
| Runtime | Python 3.11+ |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/RamanaGR/travel-agent-rag.git
cd travel-agent-rag
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
OPENAI_API_KEY=your_openai_api_key
OPENWEATHER_KEY=your_openweather_api_key
RAPIDAPI_KEY=your_rapidapi_key
USE_OFFLINE_MODE=False
DEBUG=False
UI_THEME=sunset
```

### 3. Run locally

```bash
streamlit run app/Home.py
```

Or:

```bash
./streamlit_app.sh
```

## Project Structure

```
travel-agent-rag/
├── app/
│   ├── Home.py                     # Entry point
│   ├── components/
│   │   └── layout.py               # Sidebar, themes, shared UI
│   ├── pages/
│   │   ├── 0_Theme_Preview.py
│   │   ├── 1_Travel_Results.py
│   │   └── 2_Itinerary_Generator.py
│   └── assets/
│       ├── style.css
│       └── themes/                 # ocean, sunset, minimal, tropical
├── config/
│   └── config.py
├── data/
│   ├── eval/queries.json           # Retrieval eval fixtures
│   └── indexes/                    # Per-city indexes (generated, gitignored)
├── modules/
│   ├── attractions_api.py
│   ├── nlp_extractor.py
│   ├── query_builder.py
│   ├── rag_engine.py
│   ├── retrieval.py
│   └── weather_api.py
├── scripts/
│   └── eval_retrieval.py
├── .env.example
├── .streamlit/
│   ├── config.toml
│   ├── theme_pref.toml
│   └── secrets.toml.example        # Template for Streamlit Cloud
├── requirements.txt
└── streamlit_app.sh
```

## Retrieval Evaluation

```bash
python scripts/eval_retrieval.py --rebuild
```

Requires valid API keys and network access to fetch attractions.

## Streamlit Cloud Deployment

1. Push this repository to GitHub.
2. Create a new app at [share.streamlit.io](https://share.streamlit.io).
3. Set **Main file path** to `app/Home.py`.
4. Add secrets under **Settings → Secrets** (see `.streamlit/secrets.toml.example`).
5. On first use, indexes build automatically when a user generates a plan.

## Notes

- Weather forecasts are limited to OpenWeather's **5-day window**.
- Runtime caches (`data/attractions.json`, `data/indexes/`, etc.) are created locally and not committed.
- Never commit `.env` or real API keys.

## Author

Ramana Gangarao — Atlantis University Master's Capstone Project (2025)
