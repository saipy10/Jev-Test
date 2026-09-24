import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

API_URL = "https://openrouter.ai/api/alpha/decisions"
API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL = "~typesafe/jev-latest"

SESSION = requests.Session()

CATEGORIES = {
    "Education": "Curriculum, teaching pedagogy, student engagement, academic study, syllabus, schools",
    "Finance": "Financial analysis, investments, budget, cash flow, EBITDA, working capital, credit, treasury",
    "Law": "Legal statutes, contracts, dispute arbitration, litigation, liability, jurisdiction, compliance",
    "Technology": "Software architecture, microservices, databases, infrastructure, cryptography, cloud systems",
}


def extract_text_from_txt(path: Path) -> str:
    """Read text from a plain text file."""
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_from_docx(path: Path) -> str:
    """Extract text from a .docx file without external dependencies."""
    try:
        with zipfile.ZipFile(path) as zf:
            xml_content = zf.read("word/document.xml")
            root = ET.fromstring(xml_content)
            texts = [elem.text for elem in root.iter() if elem.text]
            return " ".join(texts)
    except Exception as e:
        print(f"Warning: Failed to extract text from docx {path.name}: {e}")
        return ""


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from a .pdf file."""
    try:
        raw_bytes = path.read_bytes()
        content = raw_bytes.decode("latin-1", errors="ignore")
        # Extract strings from PDF text streams
        matches = re.findall(r"\((.*?)\)\s*(?:'|\"|Tj)", content)
        if matches:
            cleaned = [
                m.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                for m in matches
            ]
            return " ".join(cleaned)
        # Fallback regex for ASCII text blocks
        words = re.findall(r"[A-Za-z]{3,}", content)
        return " ".join(words)
    except Exception as e:
        print(f"Warning: Failed to extract text from pdf {path.name}: {e}")
        return ""


def extract_file_content(path: Path) -> str:
    """Dispatch extraction based on file extension."""
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return extract_text_from_txt(path)
    elif suffix == ".docx":
        return extract_text_from_docx(path)
    elif suffix == ".pdf":
        return extract_text_from_pdf(path)
    else:
        # Fallback attempt as text
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


def classify_document(text: str) -> tuple[str, dict]:
    """Classify text using OpenRouter Decisions API (~typesafe/jev-latest)."""
    sample_text = text[:3000].strip()
    if not sample_text:
        return "Unclassified", {}

    payload = {
        "model": MODEL,
        "state": sample_text,
        "questions": {
            "category": {
                "type": "choice",
                "instructions": "Which topic category does this document belong to?",
                "criteria": CATEGORIES,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    response = SESSION.post(API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    category_info = data.get("answers", {}).get("category", {})
    choice = category_info.get("choice", "Unclassified")
    probabilities = category_info.get("probabilities", {})
    return choice, probabilities


def organize_unorganised_folder(target_dir: Path):
    """Scan Unorganised Folder, classify documents by content, and sort into subfolders."""
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Directory '{target_dir}' does not exist.")
        return

    # Ensure category folders exist
    for cat in CATEGORIES:
        (target_dir / cat).mkdir(exist_ok=True)

    items_to_process = [item for item in target_dir.iterdir() if item.is_file()]

    if not items_to_process:
        print("No files found to organize in the folder.")
        return

    print(f"Found {len(items_to_process)} file(s) to classify and organize...\n")
    results = {cat: [] for cat in CATEGORIES}
    results["Unclassified"] = []

    for item in items_to_process:
        print(f"Analyzing content of '{item.name}'...")
        content = extract_file_content(item)
        category, probabilities = classify_document(content)

        if category not in CATEGORIES:
            category = "Unclassified"
            (target_dir / "Unclassified").mkdir(exist_ok=True)

        destination_folder = target_dir / category
        destination_path = destination_folder / item.name

        # Avoid collision
        if destination_path.exists():
            stem, suffix = item.stem, item.suffix
            counter = 1
            while destination_path.exists():
                destination_path = destination_folder / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(item), str(destination_path))
        results[category].append(item.name)

        prob_str = ", ".join(f"{k}: {v:.2f}" for k, v in probabilities.items()) if probabilities else "N/A"
        print(f" -> Classified as: [{category}] (Probabilities: {prob_str})")
        print(f" -> Moved to: '{category}/{destination_path.name}'\n")

    print("=================== SUMMARY ===================")
    for cat, files in results.items():
        if files:
            print(f"[{cat}] ({len(files)} files):")
            for f in files:
                print(f"  - {f}")
    print("===============================================")


def main():
    base_dir = Path(__file__).resolve().parent
    unorganised_folder = base_dir / "Unorganised Folder"
    print(f"Starting organization for: {unorganised_folder}\n")
    organize_unorganised_folder(unorganised_folder)


if __name__ == "__main__":
    main()