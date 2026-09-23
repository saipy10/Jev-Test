# 🗂️ Intelligent Document Classifier & Benchmarking Suite

An automated document classification, organization, and performance benchmarking system powered by **OpenRouter APIs**. This project compares **OpenRouter Decisions API** (`~typesafe/jev-latest`) against standard **LLM Chat Completions** (`nvidia/nemotron-3.5-lightning`) for classifying and organizing unstructured multi-format documents.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Project Architecture & Directory Structure](#-project-architecture--directory-structure)
- [Dataset & Ground Truth](#-dataset--ground-truth)
- [Installation & Setup](#-installation--setup)
- [Usage Guide](#-usage-guide)
  - [1. Performance Benchmark (`main.py`)](#1-performance-benchmark-mainpy)
  - [2. Organize via Decisions API (`jev.py`)](#2-organize-via-decisions-api-jevpy)
  - [3. Organize via Chat Completions (`llm.py`)](#3-organize-via-chat-completions-llmpy)
  - [4. Revert / Reset Organization (`undo.py`)](#4-revert--reset-organization-undopy)
- [Benchmarking Methodology](#-benchmarking-methodology)
- [Configuration & Environment](#-configuration--environment)

---

## 🚀 Overview

Handling messy folders with unorganized files across various formats (`.pdf`, `.docx`, `.txt`) is a common challenge. This project solves that by:
1. Extracting text without heavy external libraries (using Python standard library utilities).
2. Classifying documents into domain categories: **Education**, **Finance**, **Law**, and **Technology**.
3. Benchmarking inference speed, accuracy, throughput, and consistency between specialized decision engines (`jev.py`) and traditional LLMs (`llm.py`).
4. Moving files into dedicated category subfolders with full undo capabilities.

---

## ✨ Key Features

- **Zero Heavyweight Parser Dependencies**:
  - `.docx` files are extracted using standard `zipfile` and `xml.etree.ElementTree`.
  - `.pdf` files are parsed via regex-based byte stream text extraction.
  - `.txt` files are decoded natively.
- **Dual Classification Engines**:
  - **Decisions API (`jev.py`)**: Utilizes `~typesafe/jev-latest` on OpenRouter's decisions endpoint, yielding structured category choices and probability distributions.
  - **Chat Completions API (`llm.py`)**: Utilizes `nvidia/nemotron-3.5-lightning` with zero-reasoning prompt constraints and automatic fallback.
- **Rigorous Benchmarking Suite (`main.py`)**:
  - Pre-flight network and TLS 1.3 socket warmup to eliminate cold-start penalties.
  - Symmetrical two-phase execution (LLM first then JEV; JEV first then LLM) to eliminate cache and ordering bias.
  - Per-file latency measurements, standard deviation, throughput (docs/sec), and accuracy score verification against ground truth.
- **Safe & Reversible**:
  - File collision prevention during sorting.
  - Instant one-click rollback with `undo.py` to restore files to the root directory and clean up empty folders.

---

## 📂 Project Architecture & Directory Structure

```text
Demo/
├── Unorganised Folder/        # Target dataset containing unorganized sample documents
│   ├── appendix_notes_c.docx
│   ├── archive_entry_04.docx
│   ├── briefing_packet_09.pdf
│   ├── dossier_part_4.pdf
│   ├── field_observation_14.txt
│   ├── internal_memo_402.pdf
│   ├── metrics_packet_88.txt
│   ├── project_nexus_v1.docx
│   ├── record_log_771.txt
│   ├── section_b_draft.txt
│   ├── status_review_nov.pdf
│   └── summary_digest_05.docx
├── jev.py                     # Document classifier & organizer via OpenRouter Decisions API
├── llm.py                     # Document classifier & organizer via OpenRouter Chat Completions
├── main.py                    # Comprehensive benchmarking suite & head-to-head evaluation
├── undo.py                    # Cleanup & rollback script to restore original folder layout
├── pyproject.toml             # Project metadata & Python package requirements
├── uv.lock                    # Dependency lockfile (uv)
└── README.md                  # Project documentation
```

---

## 🏷️ Dataset & Ground Truth

The project includes 12 multi-format test documents categorized across 4 distinct domains:

| Category | Description | Benchmark Files |
| :--- | :--- | :--- |
| **Education** | Curriculum, pedagogy, syllabus, and academic studies | `archive_entry_04.docx`, `status_review_nov.pdf`, `field_observation_14.txt` |
| **Finance** | Investments, cash flow, EBITDA, working capital, budget | `appendix_notes_c.docx`, `internal_memo_402.pdf`, `metrics_packet_88.txt` |
| **Law** | Contracts, arbitration clauses, litigation, jurisdiction | `summary_digest_05.docx`, `briefing_packet_09.pdf`, `section_b_draft.txt` |
| **Technology** | Software architecture, microservices, databases, cloud | `project_nexus_v1.docx`, `dossier_part_4.pdf`, `record_log_771.txt` |

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.13+ installed
- [OpenRouter API](https://openrouter.ai/) account and API key

### 1. Clone & Navigate to Repository

```bash
git clone <repo-url>
cd Demo
```

### 2. Set Up Virtual Environment

Using standard Python `venv`:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

Or using `uv`:
```bash
uv sync
```

### 3. Install Dependencies

The project intentionally keeps dependencies lightweight:
```bash
pip install requests
```

### 4. Configure API Keys

Ensure your OpenRouter API key is configured inside `jev.py` and `llm.py`:
```python
API_KEY = "your-openrouter-api-key"
```

> **Security Note:** In production setups, it is recommended to read the API key from an environment variable:
> ```python
> API_KEY = os.getenv("OPENROUTER_API_KEY", "")
> ```

---

## 📖 Usage Guide

### 1. Performance Benchmark (`main.py`)

Runs the full comparative benchmark between `jev.py` and `llm.py` across all files in `Unorganised Folder`:

```bash
python main.py
```

**What it does:**
- Runs network warmup (TCP handshake + TLS session initiation + worker warmup).
- Executes Sequence 1: `llm.py` first, then `jev.py`.
- Executes Sequence 2: `jev.py` first, then `llm.py`.
- Computes mean, median, min, max, standard deviation, throughput, and accuracy.
- Displays a head-to-head per-file latency breakdown.

---

### 2. Organize via Decisions API (`jev.py`)

Classifies and moves files into subfolders using OpenRouter's structured Decisions API (`~typesafe/jev-latest`):

```bash
python jev.py
```

**Output:** Files in `Unorganised Folder` are sorted into `Education/`, `Finance/`, `Law/`, and `Technology/`.

---

### 3. Organize via Chat Completions (`llm.py`)

Classifies and moves files into subfolders using OpenRouter Chat Completions (`nvidia/nemotron-3.5-lightning`):

```bash
python llm.py
```

---

### 4. Revert / Reset Organization (`undo.py`)

If you want to reset `Unorganised Folder` back to its initial flat state for testing or benchmarking again:

```bash
python undo.py
```

**Output:** Moves all files from the subfolders back to `Unorganised Folder/` root and removes the empty subdirectories.

---

## 📊 Benchmarking Methodology

| Parameter | JEV (`jev.py`) | LLM (`llm.py`) |
| :--- | :--- | :--- |
| **API Endpoint** | `/api/alpha/decisions` | `/api/v1/chat/completions` |
| **Primary Model** | `~typesafe/jev-latest` | `nvidia/nemotron-3.5-lightning:free` |
| **Output Type** | Direct Choice + Probabilities | Formatted Text Completion (`Category: <Name>`) |
| **Warmup Protocol** | Pre-flight socket & GPU ping | Pre-flight socket & GPU ping |
| **Connection Pooling** | `requests.Session()` keep-alive | `requests.Session()` keep-alive |

---

## 📝 License

This project is created for evaluation and benchmarking purposes. Feel free to modify and extend it for your own workflows.
