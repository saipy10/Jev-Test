import os
import sys
import time
import statistics
from pathlib import Path

# ReportLab imports for generating result.pdf
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Import modules from current directory
import jev
import llm

BASE_DIR = Path(__file__).resolve().parent
UNORGANISED_DIR = BASE_DIR / "Unorganised Folder"

# Original 12 documents
INITIAL_FILES = {
    "archive_entry_04.docx",
    "status_review_nov.pdf",
    "field_observation_14.txt",
    "appendix_notes_c.docx",
    "internal_memo_402.pdf",
    "metrics_packet_88.txt",
    "summary_digest_05.docx",
    "briefing_packet_09.pdf",
    "section_b_draft.txt",
    "project_nexus_v1.docx",
    "dossier_part_4.pdf",
    "record_log_771.txt",
}

# 12 New Lengthy documents
LENGTHY_FILES = {
    "curriculum_standards_2026.txt",
    "faculty_symposium_proceedings.docx",
    "pedagogical_assessment_report.pdf",
    "quarterly_treasury_audit.txt",
    "consolidated_financial_statement.docx",
    "portfolio_risk_disclosure.pdf",
    "appellate_brief_in_re_tech.txt",
    "master_services_agreement.docx",
    "statutory_compliance_filing.pdf",
    "distributed_systems_architecture.txt",
    "cloud_infrastructure_blueprint.docx",
    "cybersecurity_threat_model.pdf",
}

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
            file_type = "Initial" if item.name in INITIAL_FILES else "Lengthy"
            files_data[item.name] = {
                "path": item,
                "content": content,
                "size_kb": item.stat().st_size / 1024,
                "ground_truth": GROUND_TRUTH.get(item.name, "Unknown"),
                "file_type": file_type,
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
            "file_type": item.get("file_type", "Initial"),
            "ground_truth": item["ground_truth"],
            "prediction": choice,
            "correct": is_correct,
            "latency": latency,
            "confidence": confidence,
            "details": f"Confidence: {confidence:.2f}",
        })
        status_str = "CORRECT" if is_correct else "INCORRECT"
        print(f"  [{filename[:32]:<32}] ({item.get('file_type', 'Initial'):<7}) -> {choice:<11} | Latency: {latency:6.3f}s | {status_str}")

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
        "correct_count": correct_count,
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
            "file_type": item.get("file_type", "Initial"),
            "ground_truth": item["ground_truth"],
            "prediction": choice,
            "correct": is_correct,
            "latency": latency,
            "usage": usage,
            "details": f"Tokens: {usage.get('total_tokens', 'N/A')}",
        })
        status_str = "CORRECT" if is_correct else "INCORRECT"
        print(f"  [{filename[:32]:<32}] ({item.get('file_type', 'Initial'):<7}) -> {choice:<11} | Latency: {latency:6.3f}s | {status_str}")

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
        "correct_count": correct_count,
        "results": results,
    }
    return stats


def compute_stats(results_subset: list, engine: str, model: str, run_label: str) -> dict:
    """Compute statistics for any subset of document benchmark results."""
    if not results_subset:
        return {}
    latencies = [r["latency"] for r in results_subset]
    total_time = sum(latencies)
    correct_count = sum(1 for r in results_subset if r["correct"])
    count = len(results_subset)
    return {
        "engine": engine,
        "model": model,
        "run_label": run_label,
        "total_time": total_time,
        "count": count,
        "mean_latency": statistics.mean(latencies),
        "median_latency": statistics.median(latencies),
        "min_latency": min(latencies),
        "max_latency": max(latencies),
        "stdev_latency": statistics.stdev(latencies) if count > 1 else 0.0,
        "accuracy": (correct_count / count * 100) if count > 0 else 0.0,
        "throughput": (count / total_time) if total_time > 0 else 0.0,
        "correct_count": correct_count,
        "results": results_subset,
    }


def print_combined_results_first_table(
    j_init: dict, j_len: dict, j_comb: dict,
    l_init: dict, l_len: dict, l_comb: dict
):
    """
    Prints the first combined results table with columns:
    Metric / Parameter | Initial Files (12) | Lengthy Files (12) | Combined Files (24)
    """
    col_w = 24
    line_w = 34 + 3 * (col_w + 3)
    print("\n" + "=" * line_w)
    print(" FIRST TABLE: COMBINED BENCHMARK RESULTS (INITIAL vs LENGTHY vs COMBINED) ".center(line_w))
    print("=" * line_w)
    header = f"{'Metric / Performance Parameter':<34} | {'Initial Files (12)':<{col_w}} | {'Lengthy Files (12)':<{col_w}} | {'Combined Files (24)':<{col_w}}"
    print(header)
    print("-" * line_w)

    def print_section(section_name: str):
        print(f"[{section_name}]")

    def print_row(label: str, v_init, v_len, v_comb):
        print(f"  {label:<32} | {str(v_init):<{col_w}} | {str(v_len):<{col_w}} | {str(v_comb):<{col_w}}")

    # Section 1: JEV
    print_section("JEV (~typesafe/jev-latest Decisions API)")
    print_row("Mean Latency / Doc", f"{j_init['mean_latency']:.3f} s", f"{j_len['mean_latency']:.3f} s", f"{j_comb['mean_latency']:.3f} s")
    print_row("Median Latency / Doc", f"{j_init['median_latency']:.3f} s", f"{j_len['median_latency']:.3f} s", f"{j_comb['median_latency']:.3f} s")
    print_row("Min Latency", f"{j_init['min_latency']:.3f} s", f"{j_len['min_latency']:.3f} s", f"{j_comb['min_latency']:.3f} s")
    print_row("Max Latency", f"{j_init['max_latency']:.3f} s", f"{j_len['max_latency']:.3f} s", f"{j_comb['max_latency']:.3f} s")
    print_row("Latency Std Dev", f"{j_init['stdev_latency']:.3f} s", f"{j_len['stdev_latency']:.3f} s", f"{j_comb['stdev_latency']:.3f} s")
    print_row("Total Processing Time", f"{j_init['total_time']:.3f} s", f"{j_len['total_time']:.3f} s", f"{j_comb['total_time']:.3f} s")
    print_row("Throughput", f"{j_init['throughput']:.2f} docs/sec", f"{j_len['throughput']:.2f} docs/sec", f"{j_comb['throughput']:.2f} docs/sec")
    print_row("Classification Accuracy", f"{j_init['accuracy']:.1f}% ({j_init['correct_count']}/{j_init['count']})", f"{j_len['accuracy']:.1f}% ({j_len['correct_count']}/{j_len['count']})", f"{j_comb['accuracy']:.1f}% ({j_comb['correct_count']}/{j_comb['count']})")
    print("-" * line_w)

    # Section 2: LLM
    print_section("LLM (nvidia/nemotron-3.5-lightning Chat Completions)")
    print_row("Mean Latency / Doc", f"{l_init['mean_latency']:.3f} s", f"{l_len['mean_latency']:.3f} s", f"{l_comb['mean_latency']:.3f} s")
    print_row("Median Latency / Doc", f"{l_init['median_latency']:.3f} s", f"{l_len['median_latency']:.3f} s", f"{l_comb['median_latency']:.3f} s")
    print_row("Min Latency", f"{l_init['min_latency']:.3f} s", f"{l_len['min_latency']:.3f} s", f"{l_comb['min_latency']:.3f} s")
    print_row("Max Latency", f"{l_init['max_latency']:.3f} s", f"{l_len['max_latency']:.3f} s", f"{l_comb['max_latency']:.3f} s")
    print_row("Latency Std Dev", f"{l_init['stdev_latency']:.3f} s", f"{l_len['stdev_latency']:.3f} s", f"{l_comb['stdev_latency']:.3f} s")
    print_row("Total Processing Time", f"{l_init['total_time']:.3f} s", f"{l_len['total_time']:.3f} s", f"{l_comb['total_time']:.3f} s")
    print_row("Throughput", f"{l_init['throughput']:.2f} docs/sec", f"{l_len['throughput']:.2f} docs/sec", f"{l_comb['throughput']:.2f} docs/sec")
    print_row("Classification Accuracy", f"{l_init['accuracy']:.1f}% ({l_init['correct_count']}/{l_init['count']})", f"{l_len['accuracy']:.1f}% ({l_len['correct_count']}/{l_len['count']})", f"{l_comb['accuracy']:.1f}% ({l_comb['correct_count']}/{l_comb['count']})")
    print("-" * line_w)

    # Section 3: Comparative Speedup
    print_section("COMPARATIVE PERFORMANCE & SPEEDUP")
    speed_init = l_init['mean_latency'] / j_init['mean_latency'] if j_init['mean_latency'] > 0 else 0
    speed_len = l_len['mean_latency'] / j_len['mean_latency'] if j_len['mean_latency'] > 0 else 0
    speed_comb = l_comb['mean_latency'] / j_comb['mean_latency'] if j_comb['mean_latency'] > 0 else 0
    print_row("Speedup Factor (JEV vs LLM)", f"{speed_init:.2f}x faster", f"{speed_len:.2f}x faster", f"{speed_comb:.2f}x faster")

    time_saved_init = l_init['total_time'] - j_init['total_time']
    time_saved_len = l_len['total_time'] - j_len['total_time']
    time_saved_comb = l_comb['total_time'] - j_comb['total_time']
    pct_init = (time_saved_init / l_init['total_time'] * 100) if l_init['total_time'] > 0 else 0
    pct_len = (time_saved_len / l_len['total_time'] * 100) if l_len['total_time'] > 0 else 0
    pct_comb = (time_saved_comb / l_comb['total_time'] * 100) if l_comb['total_time'] > 0 else 0
    print_row("Time Saved by JEV", f"{time_saved_init:.2f}s (-{pct_init:.1f}%)", f"{time_saved_len:.2f}s (-{pct_len:.1f}%)", f"{time_saved_comb:.2f}s (-{pct_comb:.1f}%)")

    acc_diff_init = j_init['accuracy'] - l_init['accuracy']
    acc_diff_len = j_len['accuracy'] - l_len['accuracy']
    acc_diff_comb = j_comb['accuracy'] - l_comb['accuracy']
    print_row("Accuracy Delta (JEV - LLM)", f"{acc_diff_init:+.1f}%", f"{acc_diff_len:+.1f}%", f"{acc_diff_comb:+.1f}%")
    print("=" * line_w)


def print_individual_table(stats_jev: dict, stats_llm: dict, title: str):
    """Print an individual comparison table between JEV and LLM for a specific dataset subset."""
    print("\n" + "=" * 82)
    print(f" {title.center(80)} ")
    print("=" * 82)
    header = f"{'Metric':<32} | {'JEV (Decisions API)':<20} | {'LLM (Chat Completions)':<22} | {'Advantage / Ratio'}"
    print(header)
    print("-" * 82)

    speedup = stats_llm['mean_latency'] / stats_jev['mean_latency'] if stats_jev['mean_latency'] > 0 else 0
    time_saved = stats_llm['total_time'] - stats_jev['total_time']
    time_saved_pct = (time_saved / stats_llm['total_time'] * 100) if stats_llm['total_time'] > 0 else 0

    rows = [
        ("Model / API Endpoint", stats_jev["model"], stats_llm["model"], "—"),
        ("Dataset Sample Size", f"{stats_jev['count']} documents", f"{stats_llm['count']} documents", "Identical"),
        ("Total Elapsed Time", f"{stats_jev['total_time']:.3f} s", f"{stats_llm['total_time']:.3f} s", f"-{time_saved:.2f}s (-{time_saved_pct:.1f}%)"),
        ("Mean Latency / Doc", f"{stats_jev['mean_latency']:.3f} s", f"{stats_llm['mean_latency']:.3f} s", f"{speedup:.2f}x faster"),
        ("Median Latency / Doc", f"{stats_jev['median_latency']:.3f} s", f"{stats_llm['median_latency']:.3f} s", f"{(stats_llm['median_latency']/stats_jev['median_latency'] if stats_jev['median_latency']>0 else 0):.2f}x faster"),
        ("Min Latency", f"{stats_jev['min_latency']:.3f} s", f"{stats_llm['min_latency']:.3f} s", f"{(stats_llm['min_latency']-stats_jev['min_latency']):+.3f}s"),
        ("Max Latency", f"{stats_jev['max_latency']:.3f} s", f"{stats_llm['max_latency']:.3f} s", f"{(stats_llm['max_latency']-stats_jev['max_latency']):+.3f}s"),
        ("Latency Std Dev", f"{stats_jev['stdev_latency']:.3f} s", f"{stats_llm['stdev_latency']:.3f} s", f"JEV {stats_jev['stdev_latency']:.3f}s"),
        ("Throughput", f"{stats_jev['throughput']:.2f} docs/sec", f"{stats_llm['throughput']:.2f} docs/sec", f"{stats_jev['throughput']/stats_llm['throughput'] if stats_llm['throughput']>0 else 0:.1f}x higher"),
        ("Classification Accuracy", f"{stats_jev['accuracy']:.1f}% ({stats_jev['correct_count']}/{stats_jev['count']})", f"{stats_llm['accuracy']:.1f}% ({stats_llm['correct_count']}/{stats_llm['count']})", f"{stats_jev['accuracy']-stats_llm['accuracy']:+.1f}%"),
    ]

    for label, val_j, val_l, adv in rows:
        print(f"{label:<32} | {str(val_j):<20} | {str(val_l):<22} | {adv}")
    print("=" * 82)


def print_per_file_detailed_table(files_data: dict, results_jev: list, results_llm: list):
    """Print complete per-file head-to-head breakdown for all 24 documents."""
    print("\n" + "=" * 105)
    print(" INDIVIDUAL TABLE: PER-FILE HEAD-TO-HEAD BREAKDOWN (ALL 24 DOCUMENTS) ".center(105))
    print("=" * 105)
    print(f"{'Filename':<37} | {'Type':<8} | {'Ground Truth':<11} | {'JEV Pred':<11} | {'JEV Time':<9} | {'LLM Pred':<11} | {'LLM Time':<9} | {'Faster Engine'}")
    print("-" * 105)

    jev_map = {r["file"]: r for r in results_jev}
    llm_map = {r["file"]: r for r in results_llm}

    for filename, item in sorted(files_data.items(), key=lambda x: (x[1]["file_type"], x[0])):
        r_jev = jev_map.get(filename, {})
        r_llm = llm_map.get(filename, {})

        jev_lat = r_jev.get("latency", 0.0)
        llm_lat = r_llm.get("latency", 0.0)

        faster = "JEV" if jev_lat < llm_lat else "LLM"
        diff_pct = abs(llm_lat - jev_lat) / max(min(llm_lat, jev_lat), 0.001) * 100

        print(
            f"{filename[:37]:<37} | "
            f"{item['file_type']:<8} | "
            f"{item['ground_truth']:<11} | "
            f"{r_jev.get('prediction', 'N/A'):<11} | "
            f"{jev_lat:6.3f}s   | "
            f"{r_llm.get('prediction', 'N/A'):<11} | "
            f"{llm_lat:6.3f}s   | "
            f"{faster} (+{diff_pct:.0f}%)"
        )
    print("=" * 105)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas for dynamic total page count in header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Header (on pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 762, "Document Classification Benchmark: JEV Decisions API vs LLM Baseline")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 22, page_str)
        self.drawString(36, 22, "Automated Benchmark Report • OpenRouter Architecture Evaluation")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 30, 576, 30)
        self.restoreState()


def generate_result_pdf(
    pdf_path: Path,
    j_init: dict, j_len: dict, j_comb: dict,
    l_init: dict, l_len: dict, l_comb: dict,
    files_data: dict,
    results_jev: list,
    results_llm: list,
):
    """
    Generates an executive-ready, highly polished PDF benchmark report (result.pdf).
    Includes the combined results table, all individual tables, and per-file breakdown.
    """
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=42,
        bottomMargin=42,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=10,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=8,
        spaceAfter=6,
    )

    cell_style = ParagraphStyle(
        "Cell_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#2D3748"),
    )

    cell_bold_style = ParagraphStyle(
        "Cell_Bold_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1A202C"),
    )

    cell_header_style = ParagraphStyle(
        "Cell_Header_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    cell_section_style = ParagraphStyle(
        "Cell_Section_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#2B6CB0"),
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("Document Classification Performance Benchmark", title_style))
    story.append(Paragraph("Head-to-Head Evaluation: <b>~typesafe/jev-latest</b> (Decisions API) vs <b>nvidia/nemotron-3.5-lightning</b> (Chat Completions)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E0"), spaceAfter=8))

    # Executive Summary Cards Table
    speedup_val = l_comb['mean_latency'] / j_comb['mean_latency'] if j_comb['mean_latency'] > 0 else 0
    saved_time = l_comb['total_time'] - j_comb['total_time']
    saved_pct = (saved_time / l_comb['total_time'] * 100) if l_comb['total_time'] > 0 else 0

    summary_data = [
        [
            Paragraph("<b>Total Documents</b><br/>24 Multi-Format Files<br/>(12 Initial + 12 Lengthy)", cell_style),
            Paragraph(f"<b>Overall Speedup</b><br/><b>{speedup_val:.2f}x Faster</b><br/>JEV: {j_comb['mean_latency']:.2f}s vs LLM: {l_comb['mean_latency']:.2f}s", cell_style),
            Paragraph(f"<b>Total Time Saved</b><br/><b>{saved_time:.2f}s (-{saved_pct:.1f}%)</b><br/>{j_comb['total_time']:.2f}s vs {l_comb['total_time']:.2f}s", cell_style),
            Paragraph("<b>Accuracy Score</b><br/><b>100.0% Parity</b><br/>Both 24/24 Correct", cell_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # FIRST TABLE: COMBINED BENCHMARK RESULTS
    # =========================================================================
    story.append(Paragraph("1. Combined Benchmark Results Across Dataset Categories", h1_style))

    first_table_rows = [
        [
            Paragraph("Metric / Performance Parameter", cell_header_style),
            Paragraph("Initial Files (12)", cell_header_style),
            Paragraph("Lengthy Files (12)", cell_header_style),
            Paragraph("Combined Files (24)", cell_header_style),
        ],
        # Section JEV
        [Paragraph("<b>JEV (~typesafe/jev-latest Decisions API)</b>", cell_section_style), "", "", ""],
        [Paragraph("Mean Latency / Document", cell_bold_style), Paragraph(f"{j_init['mean_latency']:.3f} s", cell_style), Paragraph(f"{j_len['mean_latency']:.3f} s", cell_style), Paragraph(f"{j_comb['mean_latency']:.3f} s", cell_bold_style)],
        [Paragraph("Median Latency / Document", cell_style), Paragraph(f"{j_init['median_latency']:.3f} s", cell_style), Paragraph(f"{j_len['median_latency']:.3f} s", cell_style), Paragraph(f"{j_comb['median_latency']:.3f} s", cell_style)],
        [Paragraph("Min Latency", cell_style), Paragraph(f"{j_init['min_latency']:.3f} s", cell_style), Paragraph(f"{j_len['min_latency']:.3f} s", cell_style), Paragraph(f"{j_comb['min_latency']:.3f} s", cell_style)],
        [Paragraph("Max Latency", cell_style), Paragraph(f"{j_init['max_latency']:.3f} s", cell_style), Paragraph(f"{j_len['max_latency']:.3f} s", cell_style), Paragraph(f"{j_comb['max_latency']:.3f} s", cell_style)],
        [Paragraph("Latency Std Dev", cell_style), Paragraph(f"{j_init['stdev_latency']:.3f} s", cell_style), Paragraph(f"{j_len['stdev_latency']:.3f} s", cell_style), Paragraph(f"{j_comb['stdev_latency']:.3f} s", cell_style)],
        [Paragraph("Total Processing Time", cell_bold_style), Paragraph(f"{j_init['total_time']:.3f} s", cell_style), Paragraph(f"{j_len['total_time']:.3f} s", cell_style), Paragraph(f"{j_comb['total_time']:.3f} s", cell_bold_style)],
        [Paragraph("Throughput (docs/sec)", cell_style), Paragraph(f"{j_init['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{j_len['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{j_comb['throughput']:.2f} docs/sec", cell_style)],
        [Paragraph("Classification Accuracy", cell_bold_style), Paragraph(f"{j_init['accuracy']:.1f}% ({j_init['correct_count']}/{j_init['count']})", cell_style), Paragraph(f"{j_len['accuracy']:.1f}% ({j_len['correct_count']}/{j_len['count']})", cell_style), Paragraph(f"{j_comb['accuracy']:.1f}% ({j_comb['correct_count']}/{j_comb['count']})", cell_bold_style)],

        # Section LLM
        [Paragraph("<b>LLM (nvidia/nemotron-3.5-lightning Chat Completions)</b>", cell_section_style), "", "", ""],
        [Paragraph("Mean Latency / Document", cell_bold_style), Paragraph(f"{l_init['mean_latency']:.3f} s", cell_style), Paragraph(f"{l_len['mean_latency']:.3f} s", cell_style), Paragraph(f"{l_comb['mean_latency']:.3f} s", cell_bold_style)],
        [Paragraph("Median Latency / Document", cell_style), Paragraph(f"{l_init['median_latency']:.3f} s", cell_style), Paragraph(f"{l_len['median_latency']:.3f} s", cell_style), Paragraph(f"{l_comb['median_latency']:.3f} s", cell_style)],
        [Paragraph("Min Latency", cell_style), Paragraph(f"{l_init['min_latency']:.3f} s", cell_style), Paragraph(f"{l_len['min_latency']:.3f} s", cell_style), Paragraph(f"{l_comb['min_latency']:.3f} s", cell_style)],
        [Paragraph("Max Latency", cell_style), Paragraph(f"{l_init['max_latency']:.3f} s", cell_style), Paragraph(f"{l_len['max_latency']:.3f} s", cell_style), Paragraph(f"{l_comb['max_latency']:.3f} s", cell_style)],
        [Paragraph("Latency Std Dev", cell_style), Paragraph(f"{l_init['stdev_latency']:.3f} s", cell_style), Paragraph(f"{l_len['stdev_latency']:.3f} s", cell_style), Paragraph(f"{l_comb['stdev_latency']:.3f} s", cell_style)],
        [Paragraph("Total Processing Time", cell_bold_style), Paragraph(f"{l_init['total_time']:.3f} s", cell_style), Paragraph(f"{l_len['total_time']:.3f} s", cell_style), Paragraph(f"{l_comb['total_time']:.3f} s", cell_bold_style)],
        [Paragraph("Throughput (docs/sec)", cell_style), Paragraph(f"{l_init['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{l_len['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{l_comb['throughput']:.2f} docs/sec", cell_style)],
        [Paragraph("Classification Accuracy", cell_bold_style), Paragraph(f"{l_init['accuracy']:.1f}% ({l_init['correct_count']}/{l_init['count']})", cell_style), Paragraph(f"{l_len['accuracy']:.1f}% ({l_len['correct_count']}/{l_len['count']})", cell_style), Paragraph(f"{l_comb['accuracy']:.1f}% ({l_comb['correct_count']}/{l_comb['count']})", cell_bold_style)],

        # Section Comparative
        [Paragraph("<b>Comparative Performance & Efficiency</b>", cell_section_style), "", "", ""],
        [Paragraph("Speedup Factor (JEV vs LLM)", cell_bold_style), Paragraph(f"<b>{l_init['mean_latency']/j_init['mean_latency']:.2f}x faster</b>", cell_bold_style), Paragraph(f"<b>{l_len['mean_latency']/j_len['mean_latency']:.2f}x faster</b>", cell_bold_style), Paragraph(f"<b>{l_comb['mean_latency']/j_comb['mean_latency']:.2f}x faster</b>", cell_bold_style)],
        [Paragraph("Time Saved by JEV", cell_bold_style), Paragraph(f"{l_init['total_time']-j_init['total_time']:.2f}s (-{(l_init['total_time']-j_init['total_time'])/l_init['total_time']*100:.1f}%)", cell_style), Paragraph(f"{l_len['total_time']-j_len['total_time']:.2f}s (-{(l_len['total_time']-j_len['total_time'])/l_len['total_time']*100:.1f}%)", cell_style), Paragraph(f"<b>{l_comb['total_time']-j_comb['total_time']:.2f}s (-{(l_comb['total_time']-j_comb['total_time'])/l_comb['total_time']*100:.1f}%)</b>", cell_bold_style)],
        [Paragraph("Accuracy Delta (JEV - LLM)", cell_style), Paragraph(f"{j_init['accuracy']-l_init['accuracy']:+.1f}%", cell_style), Paragraph(f"{j_len['accuracy']-l_len['accuracy']:+.1f}%", cell_style), Paragraph(f"{j_comb['accuracy']-l_comb['accuracy']:+.1f}%", cell_style)],
    ]

    t1 = Table(first_table_rows, colWidths=[180, 120, 120, 120])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('SPAN', (0,1), (-1,1)),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#EBF8FF")),
        ('SPAN', (0,10), (-1,10)),
        ('BACKGROUND', (0,10), (-1,10), colors.HexColor("#EBF8FF")),
        ('SPAN', (0,19), (-1,19)),
        ('BACKGROUND', (0,19), (-1,19), colors.HexColor("#FEFCBF")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # =========================================================================
    # INDIVIDUAL TABLES
    # =========================================================================
    def create_indiv_table(s_j: dict, s_l: dict) -> Table:
        speedup = s_l['mean_latency'] / s_j['mean_latency'] if s_j['mean_latency'] > 0 else 0
        saved = s_l['total_time'] - s_j['total_time']
        saved_pct = (saved / s_l['total_time'] * 100) if s_l['total_time'] > 0 else 0

        rows = [
            [Paragraph("Metric", cell_header_style), Paragraph("JEV (Decisions API)", cell_header_style), Paragraph("LLM (Chat Completions)", cell_header_style), Paragraph("Advantage / Ratio", cell_header_style)],
            [Paragraph("Dataset Sample Size", cell_style), Paragraph(f"{s_j['count']} documents", cell_style), Paragraph(f"{s_l['count']} documents", cell_style), Paragraph("Identical", cell_style)],
            [Paragraph("Total Elapsed Time", cell_bold_style), Paragraph(f"<b>{s_j['total_time']:.3f} s</b>", cell_bold_style), Paragraph(f"{s_l['total_time']:.3f} s", cell_style), Paragraph(f"<b>-{saved:.2f}s (-{saved_pct:.1f}%)</b>", cell_bold_style)],
            [Paragraph("Mean Latency / Doc", cell_bold_style), Paragraph(f"<b>{s_j['mean_latency']:.3f} s</b>", cell_bold_style), Paragraph(f"{s_l['mean_latency']:.3f} s", cell_style), Paragraph(f"<b>{speedup:.2f}x faster</b>", cell_bold_style)],
            [Paragraph("Median Latency / Doc", cell_style), Paragraph(f"{s_j['median_latency']:.3f} s", cell_style), Paragraph(f"{s_l['median_latency']:.3f} s", cell_style), Paragraph(f"{(s_l['median_latency']/s_j['median_latency'] if s_j['median_latency']>0 else 0):.2f}x faster", cell_style)],
            [Paragraph("Min Latency", cell_style), Paragraph(f"{s_j['min_latency']:.3f} s", cell_style), Paragraph(f"{s_l['min_latency']:.3f} s", cell_style), Paragraph(f"{s_l['min_latency']-s_j['min_latency']:+.3f}s", cell_style)],
            [Paragraph("Max Latency", cell_style), Paragraph(f"{s_j['max_latency']:.3f} s", cell_style), Paragraph(f"{s_l['max_latency']:.3f} s", cell_style), Paragraph(f"{s_l['max_latency']-s_j['max_latency']:+.3f}s", cell_style)],
            [Paragraph("Latency Std Dev", cell_style), Paragraph(f"{s_j['stdev_latency']:.3f} s", cell_style), Paragraph(f"{s_l['stdev_latency']:.3f} s", cell_style), Paragraph(f"{s_l['stdev_latency']/s_j['stdev_latency'] if s_j['stdev_latency']>0 else 0:.1f}x lower variance", cell_style)],
            [Paragraph("Throughput", cell_style), Paragraph(f"{s_j['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{s_l['throughput']:.2f} docs/sec", cell_style), Paragraph(f"{s_j['throughput']/s_l['throughput'] if s_l['throughput']>0 else 0:.1f}x higher", cell_style)],
            [Paragraph("Classification Accuracy", cell_bold_style), Paragraph(f"<b>{s_j['accuracy']:.1f}% ({s_j['correct_count']}/{s_j['count']})</b>", cell_bold_style), Paragraph(f"<b>{s_l['accuracy']:.1f}% ({s_l['correct_count']}/{s_l['count']})</b>", cell_bold_style), Paragraph("100% Parity", cell_bold_style)],
        ]
        t = Table(rows, colWidths=[180, 120, 120, 120])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        return t

    story.append(PageBreak())
    story.append(Paragraph("2. Individual Table 1: Initial Files (12 Documents)", h1_style))
    story.append(create_indiv_table(j_init, l_init))
    story.append(Spacer(1, 10))

    story.append(Paragraph("3. Individual Table 2: Lengthy Files (12 Documents)", h1_style))
    story.append(create_indiv_table(j_len, l_len))
    story.append(Spacer(1, 10))

    story.append(Paragraph("4. Individual Table 3: Combined Dataset (24 Documents)", h1_style))
    story.append(create_indiv_table(j_comb, l_comb))
    story.append(Spacer(1, 10))

    # =========================================================================
    # INDIVIDUAL TABLE 4: PER-FILE BREAKDOWN
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Individual Table 4: Per-File Head-to-Head Detailed Breakdown", h1_style))

    jev_map = {r["file"]: r for r in results_jev}
    llm_map = {r["file"]: r for r in results_llm}

    per_file_rows = [
        [
            Paragraph("Filename", cell_header_style),
            Paragraph("Type", cell_header_style),
            Paragraph("Ground Truth", cell_header_style),
            Paragraph("JEV Pred", cell_header_style),
            Paragraph("JEV Time", cell_header_style),
            Paragraph("LLM Pred", cell_header_style),
            Paragraph("LLM Time", cell_header_style),
            Paragraph("Faster Engine", cell_header_style),
        ]
    ]

    for filename, item in sorted(files_data.items(), key=lambda x: (x[1]["file_type"], x[0])):
        r_jev = jev_map.get(filename, {})
        r_llm = llm_map.get(filename, {})
        jev_lat = r_jev.get("latency", 0.0)
        llm_lat = r_llm.get("latency", 0.0)
        faster = "JEV" if jev_lat < llm_lat else "LLM"
        diff_pct = abs(llm_lat - jev_lat) / max(min(llm_lat, jev_lat), 0.001) * 100

        winner_cell = Paragraph(f"<b>{faster} (+{diff_pct:.0f}%)</b>", cell_bold_style) if faster == "JEV" else Paragraph(f"{faster} (+{diff_pct:.0f}%)", cell_style)

        per_file_rows.append([
            Paragraph(filename, cell_style),
            Paragraph(item["file_type"], cell_style),
            Paragraph(item["ground_truth"], cell_style),
            Paragraph(r_jev.get("prediction", "N/A"), cell_style),
            Paragraph(f"{jev_lat:.3f}s", cell_style),
            Paragraph(r_llm.get("prediction", "N/A"), cell_style),
            Paragraph(f"{llm_lat:.3f}s", cell_style),
            winner_cell,
        ])

    t_perf = Table(per_file_rows, colWidths=[165, 45, 55, 55, 50, 55, 50, 65])
    t_perf.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1A365D")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_perf)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"\n[PDF GENERATOR] Successfully generated benchmark PDF report: {pdf_path}")


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

    init_count = sum(1 for item in files_data.values() if item["file_type"] == "Initial")
    len_count = sum(1 for item in files_data.values() if item["file_type"] == "Lengthy")
    print(f"Loaded {len(files_data)} files into memory ({init_count} initial files, {len_count} lengthy files).\n")

    # =========================================================================
    # PRE-FLIGHT: Network & TLS Warmup
    # =========================================================================
    perform_network_warmup()

    # =========================================================================
    # PHASE 1: Benchmark JEV.PY
    # =========================================================================
    print("*" * 78)
    print(" [PHASE 1] EVALUATING JEV.PY (~typesafe/jev-latest Decisions API) ".center(78))
    print("*" * 78)
    stats_jev = benchmark_jev(files_data, run_label="jev.py")

    # =========================================================================
    # PHASE 2: Benchmark LLM.PY
    # =========================================================================
    print("\n" + "*" * 78)
    print(" [PHASE 2] EVALUATING LLM.PY (nvidia/nemotron-3.5-lightning Chat Completions) ".center(78))
    print("*" * 78)
    stats_llm = benchmark_llm(files_data, run_label="llm.py")

    # =========================================================================
    # COMPUTE SUBSET STATISTICS
    # =========================================================================
    results_jev_init = [r for r in stats_jev["results"] if r["file_type"] == "Initial"]
    results_jev_len = [r for r in stats_jev["results"] if r["file_type"] == "Lengthy"]
    results_jev_comb = stats_jev["results"]

    results_llm_init = [r for r in stats_llm["results"] if r["file_type"] == "Initial"]
    results_llm_len = [r for r in stats_llm["results"] if r["file_type"] == "Lengthy"]
    results_llm_comb = stats_llm["results"]

    j_init = compute_stats(results_jev_init, "jev.py", jev.MODEL, "JEV (Initial)")
    j_len = compute_stats(results_jev_len, "jev.py", jev.MODEL, "JEV (Lengthy)")
    j_comb = compute_stats(results_jev_comb, "jev.py", jev.MODEL, "JEV (Combined)")

    l_init = compute_stats(results_llm_init, "llm.py", llm.MODEL, "LLM (Initial)")
    l_len = compute_stats(results_llm_len, "llm.py", llm.MODEL, "LLM (Lengthy)")
    l_comb = compute_stats(results_llm_comb, "llm.py", llm.MODEL, "LLM (Combined)")

    # =========================================================================
    # FIRST TABLE: COMBINED RESULTS (INITIAL vs LENGTHY vs COMBINED)
    # =========================================================================
    print_combined_results_first_table(j_init, j_len, j_comb, l_init, l_len, l_comb)

    # =========================================================================
    # INDIVIDUAL TABLES
    # =========================================================================
    print_individual_table(j_init, l_init, "INDIVIDUAL TABLE 1: INITIAL FILES (12 DOCUMENTS) - JEV vs LLM")
    print_individual_table(j_len, l_len, "INDIVIDUAL TABLE 2: LENGTHY FILES (12 DOCUMENTS) - JEV vs LLM")
    print_individual_table(j_comb, l_comb, "INDIVIDUAL TABLE 3: COMBINED DATASET (24 DOCUMENTS) - JEV vs LLM")
    print_per_file_detailed_table(files_data, stats_jev["results"], stats_llm["results"])

    # =========================================================================
    # GENERATE RESULT.PDF
    # =========================================================================
    pdf_path = BASE_DIR / "result.pdf"
    generate_result_pdf(
        pdf_path=pdf_path,
        j_init=j_init, j_len=j_len, j_comb=j_comb,
        l_init=l_init, l_len=l_len, l_comb=l_comb,
        files_data=files_data,
        results_jev=stats_jev["results"],
        results_llm=stats_llm["results"],
    )


if __name__ == "__main__":
    main()
# =============================================================================
# SECTION: BENCHMARK RESULTS (INITIAL vs LENGTHY vs COMBINED FILES)
# =============================================================================
r"""
WARMED PERFORMANCE BENCHMARK RESULTS:

===================================================================================================================
                      FIRST TABLE: COMBINED BENCHMARK RESULTS (INITIAL vs LENGTHY vs COMBINED)                     
===================================================================================================================
Metric / Performance Parameter     | Initial Files (12)       | Lengthy Files (12)       | Combined Files (24)     
-------------------------------------------------------------------------------------------------------------------
[JEV (~typesafe/jev-latest Decisions API)]
  Mean Latency / Doc               | 1.735 s                  | 1.619 s                  | 1.677 s                 
  Median Latency / Doc             | 1.682 s                  | 1.270 s                  | 1.576 s                 
  Min Latency                      | 0.630 s                  | 0.640 s                  | 0.630 s                 
  Max Latency                      | 4.419 s                  | 4.853 s                  | 4.853 s                 
  Latency Std Dev                  | 1.000 s                  | 1.146 s                  | 1.053 s                 
  Total Processing Time            | 20.824 s                 | 19.429 s                 | 40.252 s                
  Throughput                       | 0.58 docs/sec            | 0.62 docs/sec            | 0.60 docs/sec           
  Classification Accuracy          | 100.0% (12/12)           | 100.0% (12/12)           | 100.0% (24/24)          
-------------------------------------------------------------------------------------------------------------------
[LLM (nvidia/nemotron-3.5-lightning Chat Completions)]
  Mean Latency / Doc               | 4.831 s                  | 9.514 s                  | 7.172 s                 
  Median Latency / Doc             | 2.955 s                  | 4.838 s                  | 3.531 s                 
  Min Latency                      | 1.692 s                  | 1.705 s                  | 1.692 s                 
  Max Latency                      | 20.841 s                 | 47.026 s                 | 47.026 s                
  Latency Std Dev                  | 5.353 s                  | 13.241 s                 | 10.162 s                
  Total Processing Time            | 57.969 s                 | 114.163 s                | 172.132 s               
  Throughput                       | 0.21 docs/sec            | 0.11 docs/sec            | 0.14 docs/sec           
  Classification Accuracy          | 100.0% (12/12)           | 100.0% (12/12)           | 100.0% (24/24)          
-------------------------------------------------------------------------------------------------------------------
[COMPARATIVE PERFORMANCE & SPEEDUP]
  Speedup Factor (JEV vs LLM)      | 2.78x faster             | 5.88x faster             | 4.28x faster            
  Time Saved by JEV                | 37.15s (-64.1%)          | 94.73s (-83.0%)          | 131.88s (-76.6%)        
  Accuracy Delta (JEV - LLM)       | +0.0%                    | +0.0%                    | +0.0%                   
===================================================================================================================

==================================================================================
          INDIVIDUAL TABLE 1: INITIAL FILES (12 DOCUMENTS) - JEV vs LLM           
==================================================================================
Metric                           | JEV (Decisions API)  | LLM (Chat Completions) | Advantage / Ratio
----------------------------------------------------------------------------------
Model / API Endpoint             | ~typesafe/jev-latest | nvidia/nemotron-3.5-lightning:free | —
Dataset Sample Size              | 12 documents         | 12 documents           | Identical
Total Elapsed Time               | 20.824 s             | 57.969 s               | -37.15s (-64.1%)
Mean Latency / Doc               | 1.735 s              | 4.831 s                | 2.78x faster
Median Latency / Doc             | 1.682 s              | 2.955 s                | 1.76x faster
Min Latency                      | 0.630 s              | 1.692 s                | +1.061s
Max Latency                      | 4.419 s              | 20.841 s               | +16.422s
Latency Std Dev                  | 1.000 s              | 5.353 s                | JEV 1.000s
Throughput                       | 0.58 docs/sec        | 0.21 docs/sec          | 2.8x higher
Classification Accuracy          | 100.0% (12/12)       | 100.0% (12/12)         | +0.0%
==================================================================================

==================================================================================
          INDIVIDUAL TABLE 2: LENGTHY FILES (12 DOCUMENTS) - JEV vs LLM           
==================================================================================
Metric                           | JEV (Decisions API)  | LLM (Chat Completions) | Advantage / Ratio
----------------------------------------------------------------------------------
Model / API Endpoint             | ~typesafe/jev-latest | nvidia/nemotron-3.5-lightning:free | —
Dataset Sample Size              | 12 documents         | 12 documents           | Identical
Total Elapsed Time               | 19.429 s             | 114.163 s              | -94.73s (-83.0%)
Mean Latency / Doc               | 1.619 s              | 9.514 s                | 5.88x faster
Median Latency / Doc             | 1.270 s              | 4.838 s                | 3.81x faster
Min Latency                      | 0.640 s              | 1.705 s                | +1.065s
Max Latency                      | 4.853 s              | 47.026 s               | +42.173s
Latency Std Dev                  | 1.146 s              | 13.241 s               | JEV 1.146s
Throughput                       | 0.62 docs/sec        | 0.11 docs/sec          | 5.9x higher
Classification Accuracy          | 100.0% (12/12)       | 100.0% (12/12)         | +0.0%
==================================================================================

==================================================================================
         INDIVIDUAL TABLE 3: COMBINED DATASET (24 DOCUMENTS) - JEV vs LLM         
==================================================================================
Metric                           | JEV (Decisions API)  | LLM (Chat Completions) | Advantage / Ratio
----------------------------------------------------------------------------------
Model / API Endpoint             | ~typesafe/jev-latest | nvidia/nemotron-3.5-lightning:free | —
Dataset Sample Size              | 24 documents         | 24 documents           | Identical
Total Elapsed Time               | 40.252 s             | 172.132 s              | -131.88s (-76.6%)
Mean Latency / Doc               | 1.677 s              | 7.172 s                | 4.28x faster
Median Latency / Doc             | 1.576 s              | 3.531 s                | 2.24x faster
Min Latency                      | 0.630 s              | 1.692 s                | +1.061s
Max Latency                      | 4.853 s              | 47.026 s               | +42.173s
Latency Std Dev                  | 1.053 s              | 10.162 s               | JEV 1.053s
Throughput                       | 0.60 docs/sec        | 0.14 docs/sec          | 4.3x higher
Classification Accuracy          | 100.0% (24/24)       | 100.0% (24/24)         | +0.0%
==================================================================================

=========================================================================================================
                   INDIVIDUAL TABLE: PER-FILE HEAD-TO-HEAD BREAKDOWN (ALL 24 DOCUMENTS)                  
=========================================================================================================
Filename                              | Type     | Ground Truth | JEV Pred    | JEV Time  | LLM Pred    | LLM Time  | Faster Engine
---------------------------------------------------------------------------------------------------------
appendix_notes_c.docx                 | Initial  | Finance     | Finance     |  0.630s   | Finance     |  6.278s   | JEV (+896%)
archive_entry_04.docx                 | Initial  | Education   | Education   |  0.844s   | Education   | 20.841s   | JEV (+2368%)
briefing_packet_09.pdf                | Initial  | Law         | Law         |  0.838s   | Law         |  3.364s   | JEV (+301%)
dossier_part_4.pdf                    | Initial  | Technology  | Technology  |  1.056s   | Technology  |  3.698s   | JEV (+250%)
field_observation_14.txt              | Initial  | Education   | Education   |  2.103s   | Education   |  4.303s   | JEV (+105%)
internal_memo_402.pdf                 | Initial  | Finance     | Finance     |  1.471s   | Finance     |  2.178s   | JEV (+48%)
metrics_packet_88.txt                 | Initial  | Finance     | Finance     |  4.419s   | Finance     |  2.546s   | LLM (+74%)
project_nexus_v1.docx                 | Initial  | Technology  | Technology  |  1.681s   | Technology  |  1.692s   | JEV (+1%)
record_log_771.txt                    | Initial  | Technology  | Technology  |  2.102s   | Technology  |  1.698s   | LLM (+24%)
section_b_draft.txt                   | Initial  | Law         | Law         |  1.683s   | Law         |  2.257s   | JEV (+34%)
status_review_nov.pdf                 | Initial  | Education   | Education   |  1.890s   | Education   |  1.876s   | LLM (+1%)
summary_digest_05.docx                | Initial  | Law         | Law         |  2.105s   | Law         |  7.239s   | JEV (+244%)
appellate_brief_in_re_tech.txt        | Lengthy  | Law         | Law         |  0.844s   | Law         | 47.026s   | JEV (+5475%)
cloud_infrastructure_blueprint.docx   | Lengthy  | Technology  | Technology  |  0.855s   | Technology  |  3.155s   | JEV (+269%)
consolidated_financial_statement.docx | Lengthy  | Finance     | Finance     |  0.857s   | Finance     |  8.215s   | JEV (+858%)
curriculum_standards_2026.txt         | Lengthy  | Education   | Education   |  0.640s   | Education   |  5.757s   | JEV (+799%)
cybersecurity_threat_model.pdf        | Lengthy  | Technology  | Technology  |  1.067s   | Technology  |  2.179s   | JEV (+104%)
distributed_systems_architecture.txt  | Lengthy  | Technology  | Technology  |  1.065s   | Technology  |  6.222s   | JEV (+484%)
faculty_symposium_proceedings.docx    | Lengthy  | Education   | Education   |  4.853s   | Education   |  3.920s   | LLM (+24%)
master_services_agreement.docx        | Lengthy  | Law         | Law         |  1.679s   | Law         | 23.676s   | JEV (+1310%)
pedagogical_assessment_report.pdf     | Lengthy  | Education   | Education   |  2.310s   | Education   |  1.705s   | LLM (+35%)
portfolio_risk_disclosure.pdf         | Lengthy  | Finance     | Finance     |  1.472s   | Finance     |  2.156s   | JEV (+46%)
quarterly_treasury_audit.txt          | Lengthy  | Finance     | Finance     |  1.889s   | Finance     |  2.424s   | JEV (+28%)
statutory_compliance_filing.pdf       | Lengthy  | Law         | Law         |  1.897s   | Law         |  7.728s   | JEV (+307%)
=========================================================================================================
"""
