import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = ""
MODEL = "nvidia/nemotron-3.5-lightning:free"
FALLBACK_MODEL = "nvidia/nemotron-3.5-lightning"

CATEGORIES = ["Education", "Finance", "Law", "Technology"]
SESSION = requests.Session()


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
        matches = re.findall(r"\((.*?)\)\s*(?:'|\"|Tj)", content)
        if matches:
            cleaned = [
                m.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
                for m in matches
            ]
            return " ".join(cleaned)
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
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""


import time

def call_chat_completion(model_name: str, sample_text: str, timeout: int = 15, max_retries: int = 3) -> dict:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert document classification assistant. "
                    "Analyze the provided document text and classify it into exactly ONE of the following categories: "
                    "Education, Finance, Law, Technology.\n"
                    "Provide your decision strictly in the format: Category: <CategoryName>"
                ),
            },
            {
                "role": "user",
                "content": f"Document content snippet:\n{sample_text}\n\nWhich category does this belong to?",
            },
        ],
        "reasoning": {"enabled": False},
    }

    for attempt in range(max_retries):
        try:
            response = SESSION.post(API_URL, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 429:
                # Rate limit encountered - wait with exponential backoff
                wait_sec = 2 * (attempt + 1)
                time.sleep(wait_sec)
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


_USE_FALLBACK = False

def classify_document_llm(text: str) -> tuple[str, str, dict]:
    """Classify document using Chat Completions with reasoning, trying MODEL first then FALLBACK_MODEL."""
    global _USE_FALLBACK
    sample_text = text[:2500].strip()
    if not sample_text:
        return "Unclassified", "Empty text", {}

    data = None

    # Try primary model (nvidia/nemotron-3.5-lightning:free) if not marked down
    if not _USE_FALLBACK:
        try:
            data = call_chat_completion(MODEL, sample_text, timeout=3, max_retries=1)
        except Exception:
            _USE_FALLBACK = True

    # Use fallback model if primary is down/slow
    if data is None:
        try:
            data = call_chat_completion(FALLBACK_MODEL, sample_text, timeout=20)
        except Exception as e:
            return "Unclassified", f"Error: {e}", {}

    choices = data.get("choices", [])
    if not choices:
        return "Unclassified", "No response choices returned", data.get("usage", {})

    message = choices[0].get("message", {})
    content = message.get("content", "")
    reasoning = message.get("reasoning_details") or message.get("reasoning") or ""

    # Parse Category from content
    match = re.search(r"Category:\s*(Education|Finance|Law|Technology)", content, re.IGNORECASE)
    if match:
        category = match.group(1).capitalize()
    else:
        # Fallback keyword match in the generated answer
        category = "Unclassified"
        for cat in CATEGORIES:
            if re.search(rf"\b{cat}\b", content, re.IGNORECASE):
                category = cat
                break

    return category, str(reasoning)[:150], data.get("usage", {})


def organize_unorganised_folder(target_dir: Path):
    """Scan Unorganised Folder, classify documents with the LLM, and move into subfolders."""
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

    print(f"Found {len(items_to_process)} file(s) to classify using '{MODEL}'...\n")
    results = {cat: [] for cat in CATEGORIES}
    results["Unclassified"] = []

    for item in items_to_process:
        print(f"Analyzing content of '{item.name}'...")
        content = extract_file_content(item)
        category, reasoning_snippet, usage = classify_document_llm(content)

        if category not in CATEGORIES:
            category = "Unclassified"
            (target_dir / "Unclassified").mkdir(exist_ok=True)

        destination_folder = target_dir / category
        destination_path = destination_folder / item.name

        # Prevent overwriting
        if destination_path.exists():
            stem, suffix = item.stem, item.suffix
            counter = 1
            while destination_path.exists():
                destination_path = destination_folder / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.move(str(item), str(destination_path))
        results[category].append(item.name)

        print(f" -> Classified as: [{category}]")
        if reasoning_snippet:
            print(f"    Reasoning: {reasoning_snippet.strip()}...")
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
    print(f"Starting organization for: {unorganised_folder}")
    print(f"Model: {MODEL} (Fallback: {FALLBACK_MODEL})\n")
    organize_unorganised_folder(unorganised_folder)


if __name__ == "__main__":
    main()