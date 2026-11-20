"""Ingestion of PDF reference documents into text passages ("chunks") for retrieval.

Indexed are
- `note`  chunks: prose paragraphs, i.e. method notes, caveats, data-quality hints, source descriptions;
- `table` chunks: the NON-numeric cells of a table (e.g. "Brandenburg · Keine verifizierte Monatsreihe").

Numeric table cells and mostly-numeric tables are dropped on purpose: figures must come from structured,
validated datasets and the deterministic engine, never from text search. Page headers / page numbers that
repeat on every page are removed. Identical passages (the same caveat in several yearly reports) are stored
once with all their locations.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

PROSE_MIN_LEN = 60           # lines at least this long are prose (table cells are short)
MAX_CHUNK_CHARS = 800
MIN_TABLE_CELLS = 4          # tables with fewer descriptive (non-numeric) cells are data tables -> not indexed

_TERMINATOR = re.compile(r"[.!?]$")
_LABEL = re.compile(r"^[A-ZÄÖÜ][\wäöüß /()-]{1,40}:\s")       # "Grenzen: ...", "Hinweis zur Datenqualität: ..."
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"])")
_DIGIT = re.compile(r"[\d€]")    # numeric cells: values and unit columns ("Jan €/m²")
_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_pages(path: Path) -> list[list[str]]:
    """Text lines per page."""
    from pypdf import PdfReader

    return [[ln.strip() for ln in (page.extract_text() or "").splitlines() if ln.strip()]
            for page in PdfReader(str(path)).pages]


def strip_repeated_headers(pages: list[list[str]]) -> list[list[str]]:
    """Remove page numbers and header lines that appear at the top of (almost) every page."""
    if len(pages) > 1:
        tops = Counter(ln for p in pages for ln in set(p[:3]))
        repeated = {ln for ln, n in tops.items() if n >= max(2, len(pages) - 1)}
    else:
        repeated = set()
    return [[ln for i, ln in enumerate(p) if not (i < 3 and (ln in repeated or ln.isdigit()))] for p in pages]


def _ends_with_url(text: str) -> bool:
    return bool(text.split()) and text.split()[-1].startswith("http")


def _is_continuation(prev: str, line: str) -> bool:
    if _TERMINATOR.search(prev) or _LABEL.match(line):
        return False
    return line[:1].islower() or len(line) >= 25 or _ends_with_url(prev)


def _join(prev: str, line: str) -> str:
    # a URL wrapped mid-word continues without a space ("...Lebenshaltun" + "gskosten/...")
    return prev + line if _ends_with_url(prev) and line[:1].islower() else f"{prev} {line}"


def _is_heading(line: str, nxt: str | None) -> bool:
    """A medium-length line without sentence end that is followed by a short line: a title or table cell,
    not prose (e.g. 'Eigener ECLI im Vergleich zum offiziellen Verbraucherpreisindex' -> 'Monat')."""
    return (nxt is not None and len(line) < 90 and len(nxt) < PROSE_MIN_LEN and nxt[:1].isupper()
            and not _TERMINATOR.search(line) and not line.endswith((",", ";", "=", "-", "–", ":")))


def _blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split a page into ('prose', [paragraph, ...]) and ('short', [cell, ...]) blocks."""
    blocks: list[tuple[str, list[str]]] = []
    for n, line in enumerate(lines):
        kind, items = blocks[-1] if blocks else ("", [])
        nxt = lines[n + 1] if n + 1 < len(lines) else None
        is_prose = len(line) >= PROSE_MIN_LEN and not _is_heading(line, nxt)
        if kind == "prose" and _is_continuation(items[-1], line) and (is_prose or len(line) < PROSE_MIN_LEN):
            items[-1] = _join(items[-1], line)
        elif is_prose:
            if kind == "prose" and not _LABEL.match(line) and len(items[-1]) < 350:
                items[-1] = f"{items[-1]} {line}"
            elif kind == "prose":
                items.append(line)
            else:
                blocks.append(("prose", [line]))
        elif kind == "short":
            items.append(line)
        else:
            blocks.append(("short", [line]))
    return blocks


def _split(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for sentence in _SENTENCE.split(text):
        if current and len(current) + len(sentence) + 1 > limit:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    return parts + ([current] if current else [])


def table_text_cells(cells: list[str]) -> list[str]:
    """Non-numeric cells that have at least one non-numeric neighbour. Labels of numeric rows
    ('Berlin / Berlin' between rent values, 'nicht berechenbar' between index values) are dropped together
    with the numbers; descriptive rows ('Brandenburg' -> 'Keine verifizierte Monatsreihe') are kept."""
    numeric = [bool(_DIGIT.search(c)) for c in cells]
    kept = []
    for i, cell in enumerate(cells):
        if numeric[i] or len(cell) <= 2:
            continue
        if (i > 0 and not numeric[i - 1]) or (i + 1 < len(cells) and not numeric[i + 1]):
            kept.append(cell)
    return kept


def page_chunks(lines: list[str]) -> list[dict]:
    """Chunks of one page: {'kind', 'section', 'text'}. The section is the heading preceding the text."""
    chunks, section = [], ""
    for kind, items in _blocks(lines):
        if kind == "prose":
            for paragraph in items:
                chunks += [{"kind": "note", "section": section, "text": t} for t in _split(paragraph)]
            continue
        heading, cells = items[0], items[1:]
        section = heading
        text_cells = table_text_cells(cells)
        if len(text_cells) >= MIN_TABLE_CELLS:
            body = f"{heading}: " + " · ".join(text_cells)
            chunks += [{"kind": "table", "section": heading, "text": t} for t in _split(body)]
    return chunks


def ingest_documents(doc_dir: Path) -> tuple[list[dict], list[dict]]:
    """Return (documents, chunks) for all PDFs in `doc_dir`. Identical passages are merged."""
    documents, merged = [], {}
    for path in sorted(doc_dir.glob("*.pdf")):
        pages = strip_repeated_headers(extract_pages(path))
        year = _YEAR.search(path.stem)
        documents.append({"file": path.name, "sha256": file_sha256(path), "pages": len(pages),
                          "size": path.stat().st_size, "mtime": path.stat().st_mtime,
                          "year": int(year.group(0)) if year else None})
        for page_no, lines in enumerate(pages, 1):
            for c in page_chunks(lines):
                key = re.sub(r"\s+", " ", c["text"]).strip().lower()
                chunk_id = "n-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
                entry = merged.setdefault(chunk_id, {"id": chunk_id, **c, "locations": [], "years": []})
                entry["locations"].append({"file": path.name, "page": page_no})
                if year and int(year.group(0)) not in entry["years"]:
                    entry["years"].append(int(year.group(0)))
    return documents, list(merged.values())
