from pathlib import Path

import pytest

from real_basket.reports.pdf_report import format_eur, generate_all

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"


def test_format_eur():
    assert format_eur(1234.5) == "1.234,50 €"
    assert format_eur(0.4) == "0,400 €"


@pytest.mark.skipif(not REAL_DOCS.is_dir(), reason="reference PDFs not available")
def test_reports_from_real_data(tmp_path):
    files = generate_all(tmp_path)
    assert [f.name for f in files] == ["realbasket_preise_2024.pdf", "realbasket_preise_2025.pdf",
                                       "realbasket_preise_2026.pdf", "realbasket_miete_staedte.pdf",
                                       "realbasket_verbraucherpreisindex.pdf"]
    assert all(f.stat().st_size > 0 for f in files)
