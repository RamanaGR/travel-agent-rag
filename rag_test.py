from modules.rag_engine import RAGEngine
rag = RAGEngine()

# Optional first run:
# entries = rag.load_data()
# rag.build_index(entries)

results = rag.search("Best things to do in New Delhi", top_k=3)
for r in results:
    print(r["name"], "-", r.get("rating"))
