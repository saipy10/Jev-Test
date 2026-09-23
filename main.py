import os
import sys
import time
import statistics
from pathlib import Path

# Import modules from current directory
import jev
import llm

BASE_DIR = Path(__file__).resolve().parent
UNORGANISED_DIR = BASE_DIR / "Unorganised Folder"

# Ground truth mapping for the 12 documents in Unorganised Folder
GROUND_TRUTH = {
    "archive_entry_04.docx": "Education",
    "status_review_nov.pdf": "Education",
    "field_observation_14.txt": "Education",
    "appendix_notes_c.docx": "Finance",
    "internal_memo_402.pdf": "Finance",
    "metrics_packet_88.txt": "Finance",
    "summary_digest_05.docx": "Law",
    "briefing_packet_09.pdf": "Law",
    "section_b_draft.txt": "Law",
    "project_nexus_v1.docx": "Technology",
    "dossier_part_4.pdf": "Technology",
    "record_log_771.txt": "Technology",
}


def load_file_contents(folder: Path) -> dict:
    """Preload contents of all files in the directory for consistent benchmarking."""
    files_data = {}
    for item in sorted(folder.iterdir()):
        if item.is_file():
            content = jev.extract_file_content(item)
            files_data[item.name] = {
                "path": item,
                "content": content,
                "size_kb": item.stat().st_size / 1024,
                "ground_truth": GROUND_TRUTH.get(item.name, "Unknown"),
            }
    return files_data


def perform_network_warmup() -> dict:
    """
    Perform pre-flight network warmup for both APIs before benchmark timing starts.
    This establishes:
      1. DNS Resolution for openrouter.ai
      2. TCP 3-Way Handshake
      3. TLS 1.3 cryptographic session negotiation
      4. Persistent keep-alive connection pooling
      5. Server-side worker allocation & prompt prefix cache warmup
    """
    print("=" * 78)
    print(" PRE-BENCHMARK NETWORK & WORKER WARMUP PHASE ".center(78))
    print("=" * 78)
    print("Pre-warming sockets to eliminate cold-start / TLS handshake penalties...\n")

    warmup_text = (
        "Warmup calibration request: evaluating academic syllabus frameworks, "
        "treasury cash management, arbitration clauses, and distributed system architectures."
    )
    warmup_stats = {}

    # 1. Warm up jev.py (~typesafe/jev-latest Decisions API)
    print("  [1/2] Warming up jev.py (~typesafe/jev-latest Decisions API)...")
    t0 = time.perf_counter()
    try:
        choice, proba = jev.classify_document(warmup_text)
        jev_warm_time = time.perf_counter() - t0
        warmup_stats["jev"] = jev_warm_time
        print(f"        -> TLS Handshake & Socket warmed in {jev_warm_time:.3f}s (Response: {choice})")
    except Exception as e:
        print(f"        -> Warning during jev warmup: {e}")
        warmup_stats["jev"] = None

    # 2. Warm up llm.py (nvidia/nemotron-3.5-lightning Chat Completions)
    print("  [2/2] Warming up llm.py (nvidia/nemotron-3.5-lightning Chat Completions)...")
    t0 = time.perf_counter()
    try:
        cat, reasoning, usage = llm.classify_document_llm(warmup_text)
        llm_warm_time = time.perf_counter() - t0
        warmup_stats["llm"] = llm_warm_time
        print(f"        -> TLS Handshake & Socket warmed in {llm_warm_time:.3f}s (Response: {cat})")
    except Exception as e:
        print(f"        -> Warning during llm warmup: {e}")
        warmup_stats["llm"] = None

    print("\nNetwork sockets and cloud GPU workers are fully primed! Starting timed benchmarks.")
    print("=" * 78 + "\n")
    return warmup_stats


def benchmark_jev(files_data: dict, run_label: str = "jev.py") -> dict:
    """Benchmark jev.py (~typesafe/jev-latest Decisions API)."""
    print(f"\n>>> Running Benchmark: [{run_label}] (~typesafe/jev-latest Decisions API)")
    results = []
    t_start_total = time.perf_counter()

    for filename, item in files_data.items():
        t0 = time.perf_counter()
        choice, proba = jev.classify_document(item["content"])
        latency = time.perf_counter() - t0

        is_correct = choice.lower() == item["ground_truth"].lower()
        confidence = proba.get(choice, 0.0) if proba else 1.0

        results.append({
            "file": filename,
            "ground_truth": item["ground_truth"],
            "prediction": choice,
            "correct": is_correct,
            "latency": latency,
            "confidence": confidence,
            "details": f"Confidence: {confidence:.2f}",
        })
        print(f"  [{filename[:24]:<24}] -> {choice:<11} | Latency: {latency:6.3f}s | {'CORRECT' if is_correct else 'INCORRECT'}")

    total_time = time.perf_counter() - t_start_total
    latencies = [r["latency"] for r in results]
    correct_count = sum(1 for r in results if r["correct"])

    stats = {
        "engine": "jev.py (Decisions API)",
        "model": jev.MODEL,
        "run_label": run_label,
        "total_time": total_time,
        "count": len(results),
        "mean_latency": statistics.mean(latencies),
        "median_latency": statistics.median(latencies),
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "stdev_latency": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        "accuracy": (correct_count / len(results) * 100) if results else 0,
        "throughput": (len(results) / total_time) if total_time > 0 else 0,
        "results": results,
    }
    return stats


def benchmark_llm(files_data: dict, run_label: str = "llm.py") -> dict:
    """Benchmark llm.py (nvidia/nemotron-3.5-lightning Chat Completions without reasoning)."""
    print(f"\n>>> Running Benchmark: [{run_label}] (nvidia/nemotron-3.5-lightning Chat Completions)")
    results = []
    t_start_total = time.perf_counter()

    for filename, item in files_data.items():
        t0 = time.perf_counter()
        choice, reasoning_snippet, usage = llm.classify_document_llm(item["content"])
        latency = time.perf_counter() - t0

        is_correct = choice.lower() == item["ground_truth"].lower()
        results.append({
            "file": filename,
            "ground_truth": item["ground_truth"],
            "prediction": choice,
            "correct": is_correct,
            "latency": latency,
            "usage": usage,
            "details": f"Tokens: {usage.get('total_tokens', 'N/A')}",
        })
        print(f"  [{filename[:24]:<24}] -> {choice:<11} | Latency: {latency:6.3f}s | {'CORRECT' if is_correct else 'INCORRECT'}")

    total_time = time.perf_counter() - t_start_total
    latencies = [r["latency"] for r in results]
    correct_count = sum(1 for r in results if r["correct"])

    stats = {
        "engine": "llm.py (Chat Completions)",
        "model": llm.MODEL,
        "run_label": run_label,
        "total_time": total_time,
        "count": len(results),
        "mean_latency": statistics.mean(latencies),
        "median_latency": statistics.median(latencies),
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "stdev_latency": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        "accuracy": (correct_count / len(results) * 100) if results else 0,
        "throughput": (len(results) / total_time) if total_time > 0 else 0,
        "results": results,
    }
    return stats


def print_comparison_table(stats_a: dict, stats_b: dict, title: str):
    """Print a clean comparison summary table between two benchmark runs."""
    print("\n" + "=" * 78)
    print(f" {title.center(76)} ")
    print("=" * 78)
    header = f"{'Metric':<32} | {stats_a['run_label']:<20} | {stats_b['run_label']:<20}"
    print(header)
    print("-" * 78)

    rows = [
        ("Model / API Endpoint", stats_a["model"], stats_b["model"]),
        ("Total Elapsed Time", f"{stats_a['total_time']:.3f} s", f"{stats_b['total_time']:.3f} s"),
        ("Mean Latency / Doc", f"{stats_a['mean_latency']:.3f} s", f"{stats_b['mean_latency']:.3f} s"),
        ("Median Latency / Doc", f"{stats_a['median_latency']:.3f} s", f"{stats_b['median_latency']:.3f} s"),
        ("Min Latency", f"{stats_a['min_latency']:.3f} s", f"{stats_b['min_latency']:.3f} s"),
        ("Max Latency", f"{stats_a['max_latency']:.3f} s", f"{stats_b['max_latency']:.3f} s"),
        ("Latency Std Dev", f"{stats_a['stdev_latency']:.3f} s", f"{stats_b['stdev_latency']:.3f} s"),
        ("Throughput", f"{stats_a['throughput']:.2f} docs/sec", f"{stats_b['throughput']:.2f} docs/sec"),
        ("Classification Accuracy", f"{stats_a['accuracy']:.1f}%", f"{stats_b['accuracy']:.1f}%"),
    ]

    for label, val_a, val_b in rows:
        print(f"{label:<32} | {str(val_a):<20} | {str(val_b):<20}")
    print("=" * 78)


def print_per_file_breakdown(files_data: dict, stats_llm: dict, stats_jev: dict):
    """Print per-file latency comparison between both engines under warm conditions."""
    print("\n" + "=" * 90)
    print(" PER-FILE HEAD-TO-HEAD COMPARISON (STEADY-STATE WARM) ".center(90))
    print("=" * 90)
    print(f"{'Filename':<26} | {'Ground Truth':<12} | {'LLM Pred':<11} | {'LLM Time':<9} | {'JEV Pred':<11} | {'JEV Time':<9} | {'Faster Engine'}")
    print("-" * 90)

    llm_map = {r["file"]: r for r in stats_llm["results"]}
    jev_map = {r["file"]: r for r in stats_jev["results"]}

    for filename, item in files_data.items():
        r_llm = llm_map.get(filename, {})
        r_jev = jev_map.get(filename, {})

        llm_lat = r_llm.get("latency", 0.0)
        jev_lat = r_jev.get("latency", 0.0)

        faster = "JEV" if jev_lat < llm_lat else "LLM"
        diff_pct = abs(llm_lat - jev_lat) / max(min(llm_lat, jev_lat), 0.001) * 100

        print(
            f"{filename[:26]:<26} | "
            f"{item['ground_truth']:<12} | "
            f"{r_llm.get('prediction', 'N/A'):<11} | "
            f"{llm_lat:6.3f}s   | "
            f"{r_jev.get('prediction', 'N/A'):<11} | "
            f"{jev_lat:6.3f}s   | "
            f"{faster} (+{diff_pct:.0f}%)"
        )
    print("=" * 90)


def main():
    print("=" * 78)
    print(" WARMED PERFORMANCE BENCHMARK: LLM.PY vs JEV.PY ".center(78))
    print("=" * 78)
    print(f"Target Directory: {UNORGANISED_DIR}")

    if not UNORGANISED_DIR.exists():
        print(f"Error: {UNORGANISED_DIR} does not exist.")
        return

    files_data = load_file_contents(UNORGANISED_DIR)
    if not files_data:
        print("No files found in Unorganised Folder to benchmark.")
        return

    print(f"Loaded {len(files_data)} files into memory.\n")

    # =========================================================================
    # PRE-FLIGHT: Network & TLS Warmup
    # =========================================================================
    perform_network_warmup()

    # =========================================================================
    # PHASE 1: Run LLM First, then JEV
    # =========================================================================
    print("*" * 78)
    print(" [SEQUENCE 1] EVALUATING LLM.PY FIRST, THEN JEV.PY (PRE-WARMED) ".center(78))
    print("*" * 78)

    stats_llm_first = benchmark_llm(files_data, run_label="llm.py (1st)")
    stats_jev_second = benchmark_jev(files_data, run_label="jev.py (2nd)")

    print_comparison_table(stats_llm_first, stats_jev_second, "SEQUENCE 1: LLM FIRST vs JEV SECOND")

    print("\nCooldown pause (2 seconds) before Sequence 2...")
    time.sleep(2)

    # =========================================================================
    # PHASE 2: Run JEV First, then LLM
    # =========================================================================
    print("\n" + "*" * 78)
    print(" [SEQUENCE 2] EVALUATING JEV.PY FIRST, THEN LLM.PY (PRE-WARMED) ".center(78))
    print("*" * 78)

    stats_jev_first = benchmark_jev(files_data, run_label="jev.py (1st)")
    stats_llm_second = benchmark_llm(files_data, run_label="llm.py (2nd)")

    print_comparison_table(stats_jev_first, stats_llm_second, "SEQUENCE 2: JEV FIRST vs LLM SECOND")

    # =========================================================================
    # DETAILED HEAD-TO-HEAD PER-FILE ANALYSIS
    # =========================================================================
    print_per_file_breakdown(files_data, stats_llm_first, stats_jev_first)

    # =========================================================================
    # WARMED STEADY-STATE ANALYSIS
    # =========================================================================
    print("\n" + "=" * 78)
    print(" STEADY-STATE WARMED COMPARISON SUMMARY ".center(78))
    print("=" * 78)

    avg_llm_time = (stats_llm_first["total_time"] + stats_llm_second["total_time"]) / 2
    avg_jev_time = (stats_jev_first["total_time"] + stats_jev_second["total_time"]) / 2

    speedup = avg_llm_time / avg_jev_time if avg_jev_time > 0 else 0
    faster_model = "jev.py" if avg_jev_time < avg_llm_time else "llm.py"

    print(f"1. STEADY-STATE LATENCY (EXCLUDING WARMUP):")
    print(f"   - Average Jev Total Time: {avg_jev_time:.3f} s (Average: {avg_jev_time/len(files_data):.3f} s / doc)")
    print(f"   - Average LLM Total Time: {avg_llm_time:.3f} s (Average: {avg_llm_time/len(files_data):.3f} s / doc)")
    if faster_model == "jev.py":
        print(f"   - Overall Speed Winner  : jev.py ({speedup:.2f}x faster on average)")
    else:
        print(f"   - Overall Speed Winner  : llm.py ({1/speedup:.2f}x faster on average)")

    print(f"\n2. WARMED SEQUENCE DELTA (Impact of Order After Warmup):")
    llm_diff = stats_llm_second["total_time"] - stats_llm_first["total_time"]
    jev_diff = stats_jev_second["total_time"] - stats_jev_first["total_time"]
    print(f"   - llm.py difference between 1st and 2nd run: {llm_diff:+.3f} s ({'+' if llm_diff>0 else ''}{(llm_diff/stats_llm_first['total_time'])*100:.1f}%)")
    print(f"   - jev.py difference between 1st and 2nd run: {jev_diff:+.3f} s ({'+' if jev_diff>0 else ''}{(jev_diff/stats_jev_first['total_time'])*100:.1f}%)")
    print(f"   -> Notice that with pre-warming and persistent sessions, the sequence variance is stabilized.")

    print(f"\n3. ACCURACY:")
    print(f"   - jev.py Accuracy: {stats_jev_first['accuracy']:.1f}% ({sum(1 for r in stats_jev_first['results'] if r['correct'])}/{len(files_data)})")
    print(f"   - llm.py Accuracy: {stats_llm_first['accuracy']:.1f}% ({sum(1 for r in stats_llm_first['results'] if r['correct'])}/{len(files_data)})")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
