"""Guard against broken umlauts: every source/doc file must be valid UTF-8 without double-encoded characters."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".sh", ".example"}
# typical sequences of UTF-8 decoded as cp1252 (umlauts, dashes, middle dot, emoji); escaped on purpose so that
# this file does not match itself
MOJIBAKE = ("\u00c3\u00a4", "\u00c3\u00b6", "\u00c3\u00bc", "\u00c3\u0178", "\u00c3\u201e", "\u00c3\u2013",
            "\u00c3\u0153", "\u00e2\u20ac", "\u00c2\u00b7", "\u00f0\u0178")
FILES = sorted(p for p in ROOT.rglob("*") if p.suffix in SUFFIXES or p.name == ".env.example"
               if p.is_file() and not any(part.startswith(".") and part not in (".env.example",)
                                          for part in p.relative_to(ROOT).parts[:-1]))


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_utf8_without_mojibake(path: Path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM"
    text = raw.decode("utf-8")
    found = [m for m in MOJIBAKE if m in text]
    assert not found, f"double-encoded characters {found}"
    controls = sorted({hex(ord(c)) for c in text if 0x80 <= ord(c) <= 0x9F})
    assert not controls, f"C1 control characters (bytes decoded as latin-1) {controls}"
