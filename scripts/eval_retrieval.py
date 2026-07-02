#!/usr/bin/env python3
"""Offline retrieval evaluation for hybrid RAG."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.attractions_api import fetch_attractions
from modules.query_builder import build_retrieval_query
from modules.rag_engine import ensure_index_for_city, retrieve_for_trip


def _name_match(result_name: str, expected: str) -> bool:
    return expected.lower() in (result_name or "").lower()


def recall_at_k(results: list[dict], expected_names: list[str], k: int) -> float:
    if not expected_names:
        return 0.0
    top = results[:k]
    hits = 0
    for expected in expected_names:
        if any(_name_match(r.get("name", ""), expected) for r in top):
            hits += 1
    return hits / len(expected_names)


def mrr(results: list[dict], expected_names: list[str]) -> float:
    if not expected_names:
        return 0.0
    scores = []
    for expected in expected_names:
        rank = None
        for i, r in enumerate(results):
            if _name_match(r.get("name", ""), expected):
                rank = i + 1
                break
        scores.append(1.0 / rank if rank else 0.0)
    return sum(scores) / len(scores)


def run_eval(eval_path: str, top_k: int = 8, rebuild: bool = False):
    with open(eval_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    totals = {"recall": 0.0, "mrr": 0.0, "count": 0}

    for case in cases:
        city = case["city"]
        query = case["query"]
        budget = case.get("budget", 1000)
        duration = case.get("duration", 3)
        expected = case.get("expected_names", [])

        print(f"\n--- Evaluating: {city} ---")
        print(f"Query: {query}")

        if rebuild:
            attractions = fetch_attractions(city)
            if not attractions:
                print(f"  Skipping {city}: no attractions")
                continue
            ensure_index_for_city(city, attractions, budget, duration)

        enriched = build_retrieval_query(query, city, budget, duration)
        results = retrieve_for_trip(query, city, budget, duration, top_k=top_k)

        r_at_k = recall_at_k(results, expected, top_k)
        mrr_score = mrr(results, expected)
        totals["recall"] += r_at_k
        totals["mrr"] += mrr_score
        totals["count"] += 1

        print(f"  Recall@{top_k}: {r_at_k:.2f}")
        print(f"  MRR: {mrr_score:.2f}")
        print("  Top results:")
        for i, r in enumerate(results[:5], 1):
            print(f"    {i}. {r.get('name')} ({r.get('match_reason', '')})")

    if totals["count"]:
        print("\n=== Summary ===")
        print(f"Cases: {totals['count']}")
        print(f"Avg Recall@{top_k}: {totals['recall'] / totals['count']:.2f}")
        print(f"Avg MRR: {totals['mrr'] / totals['count']:.2f}")
    else:
        print("No cases evaluated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate hybrid RAG retrieval")
    parser.add_argument(
        "--eval-path",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "eval", "queries.json"),
    )
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--rebuild", action="store_true", help="Rebuild indexes before eval")
    args = parser.parse_args()
    run_eval(args.eval_path, top_k=args.top_k, rebuild=args.rebuild)
