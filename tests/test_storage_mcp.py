"""SQLite is the single read source: the import writes the validated dataset, the app reads only SQLite.

Offline tests - no embeddings, no MCP runtime, no LLM.
"""
import shutil
from pathlib import Path

import pytest

from real_basket.data.real_data import RealDataError, load_real_data
from real_basket.storage import sqlite_store
from real_basket.storage.sqlite_store import get_observations, load_dataset, persist_reference_pdfs

REFERENCE_DIR = Path(__file__).resolve().parents[1] / 'reports' / 'real-data'
pytestmark = pytest.mark.skipif(not REFERENCE_DIR.is_dir(), reason='reference PDFs not available')


@pytest.fixture
def reference_dir():
    return REFERENCE_DIR


def test_pdf_provenance_and_modelled_flag(reference_dir, tmp_path):
    db = tmp_path / 'data.sqlite3'
    result = persist_reference_pdfs(reference_dir, db)
    assert result['checks_passed'] == 11 and result['prices_written'] == 120
    data = get_observations(category='Lebensmittel', metric='essential_cost', path=db)
    assert len(data) == 24
    assert all(r['data_basis'] == 'modelled' for r in data)
    assert all(r['filename'].endswith('.pdf') and r['source_page'] > 0 for r in data)


def test_rent_metadata_and_idempotency(reference_dir, tmp_path):
    db = tmp_path / 'data.sqlite3'
    persist_reference_pdfs(reference_dir, db)
    first = get_observations(metric='asking_cold_rent', path=db)
    assert len(first) == 30
    assert all(r['unit'] == 'EUR/m2' and r['data_basis'] == 'published_asking_rent' for r in first)
    dataset = load_dataset(db)
    persist_reference_pdfs(reference_dir, db)
    assert first == get_observations(metric='asking_cold_rent', path=db)
    assert load_dataset(db) == dataset            # new import id, identical content


def test_sqlite_dataset_equals_validated_pdf_import(reference_dir, tmp_path):
    db = tmp_path / 'data.sqlite3'
    persist_reference_pdfs(reference_dir, db)
    assert load_dataset(db) == load_real_data(reference_dir)    # lossless round trip, incl. order and checks


def test_reading_never_touches_the_pdfs(reference_dir, tmp_path, monkeypatch):
    db = tmp_path / 'data.sqlite3'
    persist_reference_pdfs(reference_dir, db)
    copy = tmp_path / 'copy.sqlite3'                       # fresh cache key, then forbid any PDF access
    shutil.copy(db, copy)

    def forbidden(*_a, **_k):
        raise AssertionError('PDF read at runtime')

    monkeypatch.setattr('real_basket.data.real_data.parse_document', forbidden)
    monkeypatch.setattr('real_basket.data.real_data.load_real_data', forbidden)
    monkeypatch.setattr('real_basket.knowledge.ingest.extract_pages', forbidden)
    monkeypatch.setenv('REALBASKET_SQLITE_PATH', str(copy))
    monkeypatch.setenv('KNOWLEDGE_DIR', str(tmp_path / 'no-pdfs-here'))

    from real_basket.data.basket import load_basket
    from real_basket.mcp_server.server import get_dashboard_snapshot

    basket = load_basket()
    assert len(basket.real.checks) == 11 and basket.real.all_checks_ok
    snap = get_dashboard_snapshot()
    assert snap['data_store']['database'] == str(copy) and len(snap['cities']) == 15


def test_missing_or_empty_database_raises(tmp_path):
    with pytest.raises(RealDataError, match='--mode sql'):
        load_dataset(tmp_path / 'missing.sqlite3')
    empty = tmp_path / 'empty.sqlite3'
    with sqlite_store.connect(empty):
        pass                                              # schema only, no import
    with pytest.raises(RealDataError, match='no validated dataset'):
        load_dataset(empty)


def test_failed_validation_keeps_previous_dataset(reference_dir, tmp_path, monkeypatch):
    db = tmp_path / 'data.sqlite3'
    persist_reference_pdfs(reference_dir, db)
    before = sqlite_store.dataset_info(db)['import_id']
    broken = load_real_data(reference_dir)
    broken = type(broken)(**{**broken.__dict__, 'checks': [sqlite_store_check('kaputt')]})
    monkeypatch.setattr('real_basket.data.real_data.load_real_data', lambda *_a, **_k: broken)
    with pytest.raises(ValueError, match='kaputt'):
        persist_reference_pdfs(reference_dir, db)
    assert sqlite_store.dataset_info(db)['import_id'] == before


def sqlite_store_check(name: str):
    from real_basket.data.real_data import Check

    return Check(name, False, 'simuliert')
