import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import sys
import pathlib

base_dir = pathlib.Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

import json
import time
import statistics
from sklearn.metrics import balanced_accuracy_score, precision_recall_fscore_support

from eval.baselines import predict_majority, predict_heuristic_containment, predict_trustlens

base_dir = pathlib.Path(__file__).resolve().parent.parent
eval_file = base_dir / "data" / "processed" / "eval_slice.jsonl"
results_dir = base_dir / "eval" / "results"
results_dir.mkdir(parents=True, exist_ok=True)

if not eval_file.exists():
    import subprocess
    subprocess.run(["python", str(base_dir / "scripts" / "preprocess_ragtruth.py")], check=True)

rows = [json.loads(line) for line in open(eval_file, encoding="utf-8")]
print(f"[FLOW-15] Loaded {len(rows)} rows from eval_slice.jsonl")

def span_f1(pred: list[dict], gold: list[dict]) -> float:
    """Character-level overlap F1 — standard metric for span hallucination detection."""
    p_indices = {i for s in pred for i in range(s["start"], s["end"])}
    g_indices = {i for s in gold for i in range(s["start"], s["end"])}

    if not p_indices and not g_indices:
        return 1.0
    if not p_indices or not g_indices:
        return 0.0

    tp = len(p_indices & g_indices)
    prec = tp / len(p_indices)
    rec = tp / len(g_indices)

    if (prec + rec) == 0:
        return 0.0
    return (2 * prec * rec) / (prec + rec)

def evaluate_system(name: str, predict_fn, cost_per_query: float):
    y_true = []
    y_pred = []
    f1_scores = []
    latencies = []

    print(f"[FLOW-15] Evaluating '{name}' across {len(rows)} samples...")
    for idx, r in enumerate(rows):
        t0 = time.perf_counter()
        pred_spans = predict_fn(r)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        if idx == 0 or (idx + 1) % 10 == 0 or (idx + 1) == len(rows):
            print(f"  [{name}] Sample {idx+1}/{len(rows)}: {elapsed_ms:.1f}ms", flush=True)

        has_hallucination = int(r["has_hallucination"])
        pred_has_hallucination = int(len(pred_spans) > 0)

        y_true.append(has_hallucination)
        y_pred.append(pred_has_hallucination)
        f1_scores.append(span_f1(pred_spans, r["spans"]))

    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    bal_acc = balanced_accuracy_score(y_true, y_pred)
    sorted_lat = sorted(latencies)

    metrics = {
        "system": name,
        "balanced_accuracy": round(float(bal_acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "span_f1_mean": round(float(statistics.mean(f1_scores)), 4),
        "latency_p50_ms": round(float(statistics.median(latencies)), 1),
        "latency_p95_ms": round(float(sorted_lat[int(len(sorted_lat) * 0.95)]), 1),
        "cost_per_query_usd": cost_per_query,
        "n_samples": len(rows),
    }
    return metrics

results = [
    evaluate_system("majority-baseline", predict_majority, cost_per_query=0.0),
    evaluate_system("heuristic-containment", predict_heuristic_containment, cost_per_query=0.0),
    evaluate_system("trustlens-modernbert", predict_trustlens, cost_per_query=0.0001),
]

output_path = results_dir / "benchmark.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 80)
print(f"{'System':<24} | {'Bal.Acc':<8} | {'Span F1':<8} | {'p50 (ms)':<8} | {'Cost/Query':<10}")
print("-" * 80)
for r in results:
    span_f1_str = f"{r['span_f1_mean']:.4f}" if r['span_f1_mean'] > 0 else "—"
    print(f"{r['system']:<24} | {r['balanced_accuracy']:<8.4f} | {span_f1_str:<8} | {r['latency_p50_ms']:<8.1f} | ${r['cost_per_query_usd']:<10.4f}")
print("=" * 80)
print(f"[FLOW-15 DONE] Metrics successfully recorded to {output_path}")
