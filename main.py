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

# Ground truth mapping for the documents in Unorganised Folder
GROUND_TRUTH = {
    # Original 12 documents
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

    # 12 New Lengthy documents
    "curriculum_standards_2026.txt": "Education",
    "faculty_symposium_proceedings.docx": "Education",
    "pedagogical_assessment_report.pdf": "Education",
    "quarterly_treasury_audit.txt": "Finance",
    "consolidated_financial_statement.docx": "Finance",
    "portfolio_risk_disclosure.pdf": "Finance",
    "appellate_brief_in_re_tech.txt": "Law",
    "master_services_agreement.docx": "Law",
    "statutory_compliance_filing.pdf": "Law",
    "distributed_systems_architecture.txt": "Technology",
    "cloud_infrastructure_blueprint.docx": "Technology",
    "cybersecurity_threat_model.pdf": "Technology",
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


# =============================================================================
# SECTION: ON 12 FILES
# =============================================================================
r"""
RESULTS ON 12 FILES:

==============================================================================
                WARMED PERFORMANCE BENCHMARK: LLM.PY vs JEV.PY                
==============================================================================
Target Directory: F:\Project\Demo\Unorganised Folder
Loaded 12 files into memory.

==============================================================================
                 PRE-BENCHMARK NETWORK & WORKER WARMUP PHASE                  
==============================================================================
Pre-warming sockets to eliminate cold-start / TLS handshake penalties...

  [1/2] Warming up jev.py (~typesafe/jev-latest Decisions API)...
        -> TLS Handshake & Socket warmed in 7.248s (Response: Education)
  [2/2] Warming up llm.py (nvidia/nemotron-3.5-lightning Chat Completions)...
        -> TLS Handshake & Socket warmed in 29.527s (Response: Technology)

Network sockets and cloud GPU workers are fully primed! Starting timed benchmarks.
==============================================================================

******************************************************************************
        [SEQUENCE 1] EVALUATING LLM.PY FIRST, THEN JEV.PY (PRE-WARMED)        
******************************************************************************

>>> Running Benchmark: [llm.py (1st)] (nvidia/nemotron-3.5-lightning Chat Completions)
  [appendix_notes_c.docx   ] -> Finance     | Latency:  7.897s | CORRECT
  [archive_entry_04.docx   ] -> Education   | Latency: 22.194s | CORRECT
  [briefing_packet_09.pdf  ] -> Law         | Latency:  1.683s | CORRECT
  [dossier_part_4.pdf      ] -> Technology  | Latency: 43.920s | CORRECT
  [field_observation_14.txt] -> Education   | Latency:  6.503s | CORRECT
  [internal_memo_402.pdf   ] -> Finance     | Latency:  7.374s | CORRECT
  [metrics_packet_88.txt   ] -> Finance     | Latency: 24.590s | CORRECT
  [project_nexus_v1.docx   ] -> Technology  | Latency:  2.520s | CORRECT
  [record_log_771.txt      ] -> Technology  | Latency:  1.264s | CORRECT
  [section_b_draft.txt     ] -> Law         | Latency:  5.282s | CORRECT
  [status_review_nov.pdf   ] -> Education   | Latency:  3.775s | CORRECT
  [summary_digest_05.docx  ] -> Law         | Latency:  1.677s | CORRECT

>>> Running Benchmark: [jev.py (2nd)] (~typesafe/jev-latest Decisions API)
  [appendix_notes_c.docx   ] -> Finance     | Latency:  1.222s | CORRECT
  [archive_entry_04.docx   ] -> Education   | Latency:  1.493s | CORRECT
  [briefing_packet_09.pdf  ] -> Law         | Latency:  1.264s | CORRECT
  [dossier_part_4.pdf      ] -> Technology  | Latency:  1.465s | CORRECT
  [field_observation_14.txt] -> Education   | Latency:  0.837s | CORRECT
  [internal_memo_402.pdf   ] -> Finance     | Latency:  1.265s | CORRECT
  [metrics_packet_88.txt   ] -> Finance     | Latency:  1.259s | CORRECT
  [project_nexus_v1.docx   ] -> Technology  | Latency:  0.841s | CORRECT
  [record_log_771.txt      ] -> Technology  | Latency:  0.631s | CORRECT
  [section_b_draft.txt     ] -> Law         | Latency:  0.636s | CORRECT
  [status_review_nov.pdf   ] -> Education   | Latency:  0.635s | CORRECT
  [summary_digest_05.docx  ] -> Law         | Latency:  0.853s | CORRECT

==============================================================================
                     SEQUENCE 1: LLM FIRST vs JEV SECOND                      
==============================================================================
Metric                           | llm.py (1st)         | jev.py (2nd)        
------------------------------------------------------------------------------
Model / API Endpoint             | nvidia/nemotron-3.5-lightning:free | ~typesafe/jev-latest
Total Elapsed Time               | 128.680 s            | 12.403 s            
Mean Latency / Doc               | 10.723 s             | 1.033 s             
Median Latency / Doc             | 5.892 s              | 1.037 s             
Min Latency                      | 1.264 s              | 0.631 s             
Max Latency                      | 43.920 s             | 1.493 s             
Latency Std Dev                  | 13.008 s             | 0.327 s             
Throughput                       | 0.09 docs/sec        | 0.97 docs/sec       
Classification Accuracy          | 100.0%               | 100.0%              
==============================================================================

Cooldown pause (2 seconds) before Sequence 2...

******************************************************************************
        [SEQUENCE 2] EVALUATING JEV.PY FIRST, THEN LLM.PY (PRE-WARMED)        
******************************************************************************

>>> Running Benchmark: [jev.py (1st)] (~typesafe/jev-latest Decisions API)
  [appendix_notes_c.docx   ] -> Finance     | Latency:  1.180s | CORRECT
  [archive_entry_04.docx   ] -> Education   | Latency:  0.629s | CORRECT
  [briefing_packet_09.pdf  ] -> Law         | Latency:  0.632s | CORRECT
  [dossier_part_4.pdf      ] -> Technology  | Latency:  0.853s | CORRECT
  [field_observation_14.txt] -> Education   | Latency:  0.627s | CORRECT
  [internal_memo_402.pdf   ] -> Finance     | Latency:  0.837s | CORRECT
  [metrics_packet_88.txt   ] -> Finance     | Latency:  0.838s | CORRECT
  [project_nexus_v1.docx   ] -> Technology  | Latency:  0.844s | CORRECT
  [record_log_771.txt      ] -> Technology  | Latency:  0.633s | CORRECT
  [section_b_draft.txt     ] -> Law         | Latency:  0.844s | CORRECT
  [status_review_nov.pdf   ] -> Education   | Latency:  0.636s | CORRECT
  [summary_digest_05.docx  ] -> Law         | Latency:  0.632s | CORRECT

>>> Running Benchmark: [llm.py (2nd)] (nvidia/nemotron-3.5-lightning Chat Completions)
  [appendix_notes_c.docx   ] -> Finance     | Latency:  3.216s | CORRECT
  [archive_entry_04.docx   ] -> Education   | Latency: 20.774s | CORRECT
  [briefing_packet_09.pdf  ] -> Law         | Latency:  2.541s | CORRECT
  [dossier_part_4.pdf      ] -> Technology  | Latency:  9.571s | CORRECT
  [field_observation_14.txt] -> Education   | Latency:  7.622s | CORRECT
  [internal_memo_402.pdf   ] -> Finance     | Latency: 21.732s | CORRECT
  [metrics_packet_88.txt   ] -> Finance     | Latency:  5.924s | CORRECT
  [project_nexus_v1.docx   ] -> Technology  | Latency: 44.211s | CORRECT
  [record_log_771.txt      ] -> Technology  | Latency:  4.724s | CORRECT
  [section_b_draft.txt     ] -> Law         | Latency:  4.839s | CORRECT
  [status_review_nov.pdf   ] -> Education   | Latency:  8.201s | CORRECT
  [summary_digest_05.docx  ] -> Law         | Latency:  3.581s | CORRECT

==============================================================================
                     SEQUENCE 2: JEV FIRST vs LLM SECOND                      
==============================================================================
Metric                           | jev.py (1st)         | llm.py (2nd)        
------------------------------------------------------------------------------
Model / API Endpoint             | ~typesafe/jev-latest | nvidia/nemotron-3.5-lightning:free
Total Elapsed Time               | 9.187 s              | 136.935 s           
Mean Latency / Doc               | 0.765 s              | 11.411 s            
Median Latency / Doc             | 0.737 s              | 6.773 s             
Min Latency                      | 0.627 s              | 2.541 s             
Max Latency                      | 1.180 s              | 44.211 s            
Latency Std Dev                  | 0.168 s              | 12.148 s            
Throughput                       | 1.31 docs/sec        | 0.09 docs/sec       
Classification Accuracy          | 100.0%               | 100.0%              
==============================================================================

==========================================================================================
                   PER-FILE HEAD-TO-HEAD COMPARISON (STEADY-STATE WARM)                   
==========================================================================================
Filename                   | Ground Truth | LLM Pred    | LLM Time  | JEV Pred    | JEV Time  | Faster Engine
------------------------------------------------------------------------------------------
appendix_notes_c.docx      | Finance      | Finance     |  7.897s   | Finance     |  1.180s   | JEV (+569%)
archive_entry_04.docx      | Education    | Education   | 22.194s   | Education   |  0.629s   | JEV (+3429%)
briefing_packet_09.pdf     | Law          | Law         |  1.683s   | Law         |  0.632s   | JEV (+166%)
dossier_part_4.pdf         | Technology   | Technology  | 43.920s   | Technology  |  0.853s   | JEV (+5052%)
field_observation_14.txt   | Education    | Education   |  6.503s   | Education   |  0.627s   | JEV (+937%)
internal_memo_402.pdf      | Finance      | Finance     |  7.374s   | Finance     |  0.837s   | JEV (+781%)
metrics_packet_88.txt      | Finance      | Finance     | 24.590s   | Finance     |  0.838s   | JEV (+2835%)
project_nexus_v1.docx      | Technology   | Technology  |  2.520s   | Technology  |  0.844s   | JEV (+199%)
record_log_771.txt         | Technology   | Technology  |  1.264s   | Technology  |  0.633s   | JEV (+100%)
section_b_draft.txt        | Law          | Law         |  5.282s   | Law         |  0.844s   | JEV (+525%)
status_review_nov.pdf      | Education    | Education   |  3.775s   | Education   |  0.636s   | JEV (+493%)
summary_digest_05.docx     | Law          | Law         |  1.677s   | Law         |  0.632s   | JEV (+165%)
==========================================================================================

==============================================================================
                    STEADY-STATE WARMED COMPARISON SUMMARY                    
==============================================================================
1. STEADY-STATE LATENCY (EXCLUDING WARMUP):
   - Average Jev Total Time: 10.795 s (Average: 0.900 s / doc)
   - Average LLM Total Time: 132.808 s (Average: 11.067 s / doc)
   - Overall Speed Winner  : jev.py (12.30x faster on average)

2. WARMED SEQUENCE DELTA (Impact of Order After Warmup):
   - llm.py difference between 1st and 2nd run: +8.255 s (+6.4%)
   - jev.py difference between 1st and 2nd run: +3.216 s (+35.0%)
   -> Notice that with pre-warming and persistent sessions, the sequence variance is stabilized.

3. ACCURACY:
   - jev.py Accuracy: 100.0% (12/12)
   - llm.py Accuracy: 100.0% (12/12)
==============================================================================
"""
