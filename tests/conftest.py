"""Test isolation: every test session gets its own SQLite database, imported once from the reference PDFs.

The app reads all figures from SQLite (`data.basket.load_basket` -> `storage.sqlite_store.load_dataset`); the PDFs
are only read by the import. Tests never touch the developer database `data_store/realbasket.sqlite3`.
"""
import os
from pathlib import Path

import pytest

REAL_DOCS = Path(__file__).resolve().parents[1] / "reports" / "real-data"


@pytest.fixture(scope="session", autouse=True)
def sqlite_dataset(tmp_path_factory):
    db = tmp_path_factory.mktemp("sqlite") / "realbasket.sqlite3"
    previous = os.environ.get("REALBASKET_SQLITE_PATH")
    os.environ["REALBASKET_SQLITE_PATH"] = str(db)
    if REAL_DOCS.is_dir() and any(REAL_DOCS.glob("*.pdf")):
        from real_basket.storage.sqlite_store import persist_reference_pdfs

        persist_reference_pdfs(REAL_DOCS)
    yield db
    if previous is None:
        os.environ.pop("REALBASKET_SQLITE_PATH", None)
    else:
        os.environ["REALBASKET_SQLITE_PATH"] = previous
