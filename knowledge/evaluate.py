"""Reproducible retrieval comparisons over a labeled, disposable corpus."""

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import statistics
import tempfile

from dotenv import load_dotenv

from .config import Settings
from .embeddings import ProviderError
from .service import KnowledgeService


def retrieval_metrics(retrieved, expected, k):
    hits, recalls, precisions, ndcgs, empty = [], [], [], [], []
    for actual, relevant in zip(retrieved, expected):
        actual = list(dict.fromkeys(actual))[:k]
        if not relevant:
            empty.append(float(not actual))
            continue
        found = set(actual) & set(relevant)
        hits.append(float(bool(found)))
        recalls.append(len(found) / len(relevant))
        precisions.append(len(found) / k)
        dcg = sum((1 / math.log2(rank + 2)) for rank, document in enumerate(actual) if document in relevant)
        ideal = sum(1 / math.log2(rank + 2) for rank in range(min(k, len(relevant))))
        ndcgs.append(dcg / ideal)
    average = lambda values: round(statistics.mean(values), 6) if values else None
    return {"hit_at_k": average(hits), "recall_at_k": average(recalls), "precision_at_k": average(precisions),
            "ndcg_at_k": average(ndcgs), "unanswerable_empty_accuracy": average(empty),
            "answerable_queries": len(hits), "unanswerable_queries": len(empty)}


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def evaluate(service, dataset, modes, k):
    owner = "evaluation"
    service.ingest_many(owner, dataset["documents"])
    expected = [set(question["relevant"]) for question in dataset["queries"]]
    report = {"dataset": dataset.get("name", "custom"), "k": k, "modes": {},
              "embedding_provider": service.settings.embedding_provider,
              "embedding_model": service.settings.embedding_model,
              "notes": ["Synthetic seed data; replace or expand it with held-out questions from your own sources.",
                        "Retrieval metrics are document-level after duplicate documents are removed.",
                        "These metrics do not measure generated-answer faithfulness."]}
    for mode in modes:
        if mode != "lexical" and not service.provider:
            report["modes"][mode] = {"skipped": "No embedding provider configured."}
            continue
        retrieved, latencies, questions, evidence = [], [], [], []
        for question in dataset["queries"]:
            result = service.search(owner, question["query"], k, mode)
            actual = [hit["document_id"] for hit in result["results"]]
            retrieved.append(actual)
            latencies.append(result["timings_ms"]["total"])
            checks = [any(hit["document_id"] == document_id and phrase.casefold() in hit["text"].casefold()
                          for hit in result["results"])
                      for document_id, phrases in question["relevant"].items() for phrase in phrases]
            if checks:
                evidence.append(sum(checks) / len(checks))
            questions.append({"id": question["id"], "retrieved": list(dict.fromkeys(actual)),
                              "expected": sorted(question["relevant"]), "latency_ms": result["timings_ms"]["total"]})
        report["modes"][mode] = retrieval_metrics(retrieved, expected, k) | {
            "evidence_coverage": round(statistics.mean(evidence), 6) if evidence else None,
            "latency_ms": {"p50": round(percentile(latencies, .5), 3), "p95": round(percentile(latencies, .95), 3)},
            "queries": questions,
        }
    metrics = service.status(owner)["metrics"]
    report["embedding_usage"] = metrics | {"input_tokens": metrics.get("input_tokens") if metrics.get("tokens_reported") else None}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evals/retrieval.json"))
    parser.add_argument("--modes", default="lexical,dense,hybrid")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    modes = args.modes.split(",")
    if not 1 <= args.k <= 10 or any(mode not in {"lexical", "dense", "hybrid"} for mode in modes):
        parser.error("Use k between 1 and 10, and modes lexical,dense,hybrid.")
    load_dotenv()
    root = Path(__file__).resolve().parents[1]
    try:
        dataset = json.loads(args.dataset.read_text())
        if not dataset.get("documents") or not dataset.get("queries"):
            raise ValueError("The dataset requires nonempty documents and queries arrays.")
        with tempfile.TemporaryDirectory(prefix="saariv-eval-") as directory:
            settings = replace(Settings.from_env(root), data_dir=Path(directory))
            service = KnowledgeService(settings)
            try:
                report = evaluate(service, dataset, modes, args.k)
            finally:
                service.close()
        output = json.dumps(report, indent=2)
        if args.output:
            args.output.write_text(output + "\n")
        print(output)
    except (OSError, ValueError, KeyError, ProviderError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")


if __name__ == "__main__":
    main()
