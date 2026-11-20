"""Offline tests for deterministic persistent storage, no embeddings or MCP runtime required."""
from pathlib import Path

import pytest

from real_basket.storage.sqlite_store import get_observations, persist_reference_pdfs


@pytest.fixture
def reference_dir():
    return Path(__file__).resolve().parents[1] / 'reports' / 'real-data'


def test_pdf_provenance_and_modelled_flag(reference_dir, tmp_path):
    db = tmp_path / 'data.sqlite3'
    result = persist_reference_pdfs(reference_dir, db)
    assert result['checks_passed'] > 0
    data = get_observations(category='Lebensmittel', metric='essential_cost',path=db)
    assert len(data) == 24
    assert all(r['data_basis'] == 'modelled' for r in data)
    assert all(r['filename'].endswith('.pdf') and r['source_page'] > 0 for r in data)


def test_rent_metadata_and_idempotency(reference_dir, tmp_path):
    db = tmp_path / 'data.sqlite3'
    persist_reference_pdfs(reference_dir, db)
    first = get_observations(metric='asking_cold_rent', path=db)
    assert len(first) == 30
    assert all(r['unit'] == 'EUR/m2' and r['data_basis'] == 'published_asking_rent' for r in first)
    persist_reference_pdfs(reference_dir, db)
    assert first == get_observations(metric='asking_cold_rent', path=db)
