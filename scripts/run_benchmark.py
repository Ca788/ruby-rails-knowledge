#!/usr/bin/env python3
"""Retrieval Quality & Context Efficiency Benchmark Suite (Section 17)."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.config import AppConfig, RetrievalLimits
from src.ingestion.pipeline import IngestionPipeline
from src.retrieval.lexical_search import RetrievalEngine


BENCHMARK_CASES: List[Dict[str, Any]] = [
    {
        "id": "Q1_after_save_vs_after_commit_61",
        "query": "What is the difference between after_save and after_commit?",
        "technology": "rails",
        "version": "6.1",
        "expected_sources": ["rails_guides", "rails_api"],
        "expected_subtopics": ["difference_between_after_save", "transaction_callbacks_after_commit", "callbacks_overview_and_lifecycle"],
        "required_terms_top1": ["after_save", "after_commit", "transaction"],
        "expected_graph_concepts": ["transactions", "after_save", "callbacks"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v6.1/",
    },
    {
        "id": "Q2_prevent_n_plus_one_61",
        "query": "How does Active Record prevent N+1 queries?",
        "technology": "rails",
        "version": "6.1",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["preventing_n_1_queries", "difference_between_includes_preload"],
        "required_terms_top1": ["n+1", "includes", "strict_loading"],
        "expected_graph_concepts": ["n_plus_one", "includes", "strict_loading"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v6.1/",
    },
    {
        "id": "Q3_includes_preload_eager_load_61",
        "query": "What is the difference between includes, preload and eager_load?",
        "technology": "rails",
        "version": "6.1",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["difference_between_includes_preload", "preventing_n_1_queries"],
        "required_terms_top1": ["includes", "preload", "eager_load", "left outer join"],
        "expected_graph_concepts": ["preload", "eager_load", "includes"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v6.1/",
    },
    {
        "id": "Q4_find_each_61",
        "query": "How does find_each work?",
        "technology": "rails",
        "version": "6.1",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["batch_processing_how_find", "preventing_n_1_queries"],
        "required_terms_top1": ["find_each", "batch_size", "1000"],
        "expected_graph_concepts": ["in_batches", "find_each"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v6.1/",
    },
    {
        "id": "Q5_nested_transactions_61",
        "query": "How do nested transactions work?",
        "technology": "rails",
        "version": "6.1",
        "expected_sources": ["rails_api", "rails_guides"],
        "expected_subtopics": ["how_nested_transactions_and", "transaction_callbacks_after_commit"],
        "required_terms_top1": ["requires_new", "savepoint", "rollback"],
        "expected_graph_concepts": ["savepoints", "transactions"],
        "expected_url_prefix": "https://api.rubyonrails.org/v6.1/",
    },
    {
        "id": "Q6_zeitwerk_autoloading_72",
        "query": "How does Zeitwerk autoloading work?",
        "technology": "rails",
        "version": "7.2",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["how_zeitwerk_autoloading_works", "what_changed_between_rails"],
        "required_terms_top1": ["zeitwerk", "autoload_paths", "camelize"],
        "expected_graph_concepts": ["autoloading", "zeitwerk"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v7.2/",
    },
    {
        "id": "Q7_ruby_enumerable_methods_33",
        "query": "What are the Ruby Enumerable methods?",
        "technology": "ruby",
        "version": "3.3",
        "expected_sources": ["ruby_api"],
        "expected_subtopics": ["what_are_the_ruby"],
        "required_terms_top1": ["enumerable", "#map", "#select", "#reduce", "#tally"],
        "expected_graph_concepts": ["enumerator", "enumerable"],
        "expected_url_prefix": "https://docs.ruby-lang.org/en/3.3/Enumerable.html",
    },
    {
        "id": "Q8_connection_pooling_72",
        "query": "How does Rails handle database connection pooling?",
        "technology": "rails",
        "version": "7.2",
        "expected_sources": ["rails_api"],
        "expected_subtopics": ["how_rails_handles_database", "how_nested_transactions_and"],
        "required_terms_top1": ["connectionpool", "checkout_timeout", "pool"],
        "expected_graph_concepts": ["connection_pool", "active_record"],
        "expected_url_prefix": "https://api.rubyonrails.org/v7.2/",
    },
    {
        "id": "Q9_changes_61_to_72_api",
        "query": "What changed between Rails 6.1 and Rails 7.2 regarding transaction callbacks and strict_loading?",
        "technology": "rails",
        "version": "7.2",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["what_changed_between_rails", "transaction_callbacks_after_commit", "preventing_n_1_queries"],
        "required_terms_top1": ["after_all_transactions_commit", "strict_loading", "6.1", "7.2"],
        "expected_graph_concepts": ["after_all_transactions_commit", "strict_loading"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v7.2/",
    },
    {
        "id": "Q10_deprecated_methods_documented_72",
        "query": "How are deprecated methods documented and handled with ActiveSupport::Deprecation?",
        "technology": "rails",
        "version": "7.2",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["how_deprecated_methods_are", "what_changed_between_rails"],
        "required_terms_top1": ["activesupport::deprecation", "deprecators", "rdoc"],
        "expected_graph_concepts": ["deprecations", "active_support"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v7.2/",
    },
    {
        "id": "Q11_after_commit_rails_72_comparison",
        "query": "How do transaction callbacks and after_commit work in Rails 7.2?",
        "technology": "rails",
        "version": "7.2",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["transaction_callbacks_after_commit", "difference_between_after_save", "what_changed_between_rails"],
        "required_terms_top1": ["after_commit", "after_all_transactions_commit"],
        "expected_graph_concepts": ["transactions", "after_commit"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v7.2/",
    },
    {
        "id": "Q12_strict_loading_n_plus_one_only_71",
        "query": "How does strict_loading n_plus_one_only mode prevent N+1 queries?",
        "technology": "rails",
        "version": "7.1",
        "expected_sources": ["rails_guides"],
        "expected_subtopics": ["preventing_n_1_queries", "what_changed_between_rails"],
        "required_terms_top1": ["strict_loading", ":n_plus_one_only"],
        "expected_graph_concepts": ["n_plus_one", "strict_loading"],
        "expected_url_prefix": "https://guides.rubyonrails.org/v7.1/",
    },
]


def run_benchmarks() -> Dict[str, Any]:
    cfg = AppConfig()
    cfg.retrieval_limits = RetrievalLimits(
        max_results=3,
        max_related_concepts=8,
        max_graph_depth=2,
        max_content_chars=2400,
        max_estimated_tokens=1800,
    )
    pipeline = IngestionPipeline(cfg)
    pipeline.run_ingestion()
    engine = RetrievalEngine(cfg)

    # Calculate full corpus size in chars & tokens for baseline comparison
    with pipeline.db.connect(readonly=True) as conn:
        total_corpus_chars = int(conn.execute("SELECT SUM(char_count) FROM knowledge_chunks").fetchone()[0] or 0)
        version_corpus_rows = conn.execute(
            "SELECT technology, version, SUM(char_count) AS chars FROM knowledge_chunks GROUP BY technology, version"
        ).fetchall()
        version_corpus_chars = {
            f"{r['technology']}:{r['version']}": int(r["chars"] or 0)
            for r in version_corpus_rows
        }

    case_reports: List[Dict[str, Any]] = []
    p_at_1_list: List[float] = []
    p_at_k_list: List[float] = []
    r_at_k_list: List[float] = []
    mrr_list: List[float] = []
    latencies: List[float] = []
    chunks_counts: List[int] = []
    returned_tokens_list: List[int] = []
    full_docs_tokens_list: List[int] = []
    version_corpus_tokens_list: List[int] = []
    zero_results_count = 0

    for case in BENCHMARK_CASES:
        res = engine.search(
            query=case["query"],
            technology=case["technology"],
            version=case["version"],
            limit=3,
            expand_graph=True,
        )
        results = res["results"]
        meta = res["metadata"]
        latencies.append(float(meta["elapsed_ms"]))
        chunks_counts.append(len(results))

        if not results:
            zero_results_count += 1
            p_at_1_list.append(0.0)
            p_at_k_list.append(0.0)
            r_at_k_list.append(0.0)
            mrr_list.append(0.0)
            continue

        # Check relevance of each returned chunk
        relevant_ranks: List[int] = []
        relevant_subtopics_found = set()
        for rank_idx, r in enumerate(results, start=1):
            ver_ok = r["version"] == case["version"]
            src_ok = r["source_id"] in case["expected_sources"]
            sub_ok = r["subtopic"] in case["expected_subtopics"]
            if ver_ok and src_ok and sub_ok:
                relevant_ranks.append(rank_idx)
                relevant_subtopics_found.add(r["subtopic"])

        top1 = results[0]
        top1_text_low = (top1["title"] + "\n" + top1["content"]).lower()
        terms_present = [t for t in case["required_terms_top1"] if t.lower() in top1_text_low]
        context_complete = len(terms_present) == len(case["required_terms_top1"])
        url_valid = top1["source_url"].startswith(case["expected_url_prefix"])

        graph_nodes = set(top1.get("related_concepts", []))
        for g in top1.get("graph_relations", []):
            graph_nodes.add(g["source"])
            graph_nodes.add(g["target"])
        graph_coherent = any(c in graph_nodes for c in case["expected_graph_concepts"])

        p_at_1 = 1.0 if (1 in relevant_ranks and context_complete) else 0.0
        p_at_k = round(len(relevant_ranks) / float(len(results)), 4)
        # Recall@K against the primary target subtopic(s) (capped at len(results))
        target_recall_denom = min(len(case["expected_subtopics"]), len(results))
        r_at_k = 1.0 if (1 in relevant_ranks and context_complete) else round(
            len(relevant_subtopics_found) / float(max(1, target_recall_denom)), 4
        )
        mrr = round(1.0 / relevant_ranks[0], 4) if relevant_ranks else 0.0

        p_at_1_list.append(p_at_1)
        p_at_k_list.append(p_at_k)
        r_at_k_list.append(r_at_k)
        mrr_list.append(mrr)

        ret_tokens = int(meta["estimated_tokens"])
        f_doc_tokens = int(meta["full_docs_tokens"])
        v_corp_chars = version_corpus_chars.get(f"{case['technology']}:{case['version']}", total_corpus_chars)
        v_corp_tokens = max(f_doc_tokens, (v_corp_chars + 3) // 4)

        returned_tokens_list.append(ret_tokens)
        full_docs_tokens_list.append(f_doc_tokens)
        version_corpus_tokens_list.append(v_corp_tokens)

        case_reports.append({
            "id": case["id"],
            "query": case["query"],
            "technology": case["technology"],
            "version": case["version"],
            "top1_title": top1["title"],
            "top1_source_url": top1["source_url"],
            "version_exact": top1["version"] == case["version"],
            "source_correct": top1["source_id"] in case["expected_sources"],
            "context_sufficient": context_complete,
            "graph_coherent": graph_coherent,
            "reference_valid": url_valid,
            "precision_at_1": p_at_1,
            "precision_at_k": p_at_k,
            "recall_at_k": r_at_k,
            "reciprocal_rank": mrr,
            "latency_ms": meta["elapsed_ms"],
            "chunks_retrieved": len(results),
            "returned_chars": sum(len(r["content"]) for r in results),
            "returned_tokens": ret_tokens,
            "matched_full_docs_tokens": f_doc_tokens,
            "version_corpus_tokens": v_corp_tokens,
            "savings_vs_matched_docs_pct": round((1.0 - ret_tokens / float(f_doc_tokens)) * 100.0, 2) if f_doc_tokens else 0.0,
            "savings_vs_version_corpus_pct": round((1.0 - ret_tokens / float(v_corp_tokens)) * 100.0, 2) if v_corp_tokens else 0.0,
        })

    avg_ret_tokens = statistics.mean(returned_tokens_list)
    avg_doc_tokens = statistics.mean(full_docs_tokens_list)
    avg_ver_tokens = statistics.mean(version_corpus_tokens_list)
    total_corpus_tokens = (total_corpus_chars + 3) // 4

    summary = {
        "total_queries": len(BENCHMARK_CASES),
        "zero_result_rate": round(zero_results_count / float(len(BENCHMARK_CASES)), 4),
        "mean_precision_at_1": round(statistics.mean(p_at_1_list), 4),
        "mean_precision_at_3": round(statistics.mean(p_at_k_list), 4),
        "mean_recall_at_3": round(statistics.mean(r_at_k_list), 4),
        "mrr": round(statistics.mean(mrr_list), 4),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2),
            "median": round(statistics.median(latencies), 2),
            "max": round(max(latencies), 2),
            "min": round(min(latencies), 2),
        },
        "avg_chunks_retrieved": round(statistics.mean(chunks_counts), 2),
        "context_economy": {
            "avg_returned_tokens": round(avg_ret_tokens, 1),
            "avg_matched_full_docs_tokens": round(avg_doc_tokens, 1),
            "avg_version_corpus_tokens": round(avg_ver_tokens, 1),
            "entire_kb_corpus_tokens": total_corpus_tokens,
            "token_reduction_vs_matched_docs_pct": round((1.0 - avg_ret_tokens / avg_doc_tokens) * 100.0, 2),
            "token_reduction_vs_version_corpus_pct": round((1.0 - avg_ret_tokens / avg_ver_tokens) * 100.0, 2),
            "token_reduction_vs_entire_kb_pct": round((1.0 - avg_ret_tokens / float(total_corpus_tokens)) * 100.0, 2),
        },
        "cases": case_reports,
    }
    return summary


if __name__ == "__main__":
    report = run_benchmarks()
    print(json.dumps(report, indent=2))
