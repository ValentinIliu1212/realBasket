"""SQLite: the single read source for all figures (PDFs are only used for the import).

Import (`persist_reference_pdfs`, run by `python -m real_basket.storage --mode sql` / the MCP tool
`ingest_reference_pdfs`): the reference PDFs are parsed deterministically and re-checked (11 checks,
`real_basket.data.real_data`). Only a fully validated dataset is written, in ONE transaction:

- canonical dataset tables (`dataset_meta`, `dataset_documents`, `base_amounts`, `prices`, `cpi`,
  `printed_ecli`, `city_rents`, `state_coverage`, `checks`) - replaced on every import; read by
  `load_dataset()` -> `data.basket.load_basket()` -> dashboard, MCP tools, PDF reports, CLI agent
- provenance tables (`documents`, `observations`) - one row per PDF version (sha256) and value, with page;
  queried by the MCP tool `get_observations`

Reading never touches the PDFs. If the database or the dataset is missing, `load_dataset()` raises
`RealDataError` (no fallback, no implicit import).
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date
from functools import lru_cache
from pathlib import Path

from real_basket.core.settings import resolve_path

DEFAULT_DB = 'data_store/realbasket.sqlite3'
IMPORT_HINT = 'python -m real_basket.storage --mode sql'

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS documents (
    sha256 TEXT PRIMARY KEY, filename TEXT NOT NULL, pages INTEGER NOT NULL,
    data_basis TEXT NOT NULL, ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS observations (
    document_sha256 TEXT NOT NULL REFERENCES documents(sha256),
    period TEXT NOT NULL, category TEXT NOT NULL, region TEXT NOT NULL,
    metric TEXT NOT NULL, value_eur REAL NOT NULL, unit TEXT NOT NULL,
    source_page INTEGER, data_basis TEXT NOT NULL,
    PRIMARY KEY (document_sha256,period,category,region,metric)
);
CREATE INDEX IF NOT EXISTS obs_period ON observations(period, category, region);

-- canonical, validated dataset (read source of load_basket)
CREATE TABLE IF NOT EXISTS dataset_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dataset_documents (position INTEGER PRIMARY KEY, filename TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS base_amounts (
    position INTEGER PRIMARY KEY, category TEXT NOT NULL UNIQUE, amount_eur REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    position INTEGER PRIMARY KEY, period TEXT NOT NULL, category TEXT NOT NULL, item TEXT NOT NULL,
    price_eur REAL NOT NULL, unit TEXT NOT NULL, source TEXT NOT NULL, UNIQUE (period, category, item)
);
CREATE TABLE IF NOT EXISTS cpi (
    position INTEGER PRIMARY KEY, period TEXT NOT NULL UNIQUE, index_value REAL NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS printed_ecli (
    period TEXT PRIMARY KEY, ecli REAL, ecli_yoy_pct REAL
);
CREATE TABLE IF NOT EXISTS city_rents (
    position INTEGER PRIMARY KEY, city TEXT NOT NULL, state TEXT NOT NULL,
    rent_jan_eur_m2 REAL NOT NULL, rent_oct_eur_m2 REAL NOT NULL,
    rent_jan_flat_eur REAL NOT NULL, rent_oct_flat_eur REAL NOT NULL,
    change_pct REAL NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state_coverage (
    position INTEGER PRIMARY KEY, state TEXT NOT NULL UNIQUE, cities_json TEXT NOT NULL,
    verified_state_series INTEGER NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checks (
    position INTEGER PRIMARY KEY, name TEXT NOT NULL, ok INTEGER NOT NULL, detail TEXT NOT NULL
);
'''
_DATASET_TABLES = ('dataset_meta', 'dataset_documents', 'base_amounts', 'prices', 'cpi', 'printed_ecli',
                   'city_rents', 'state_coverage', 'checks')


def db_path() -> Path:
    """`REALBASKET_SQLITE_PATH`; relative paths resolve like DATA_DIR / KNOWLEDGE_DIR (cwd, else project root)."""
    return resolve_path(os.getenv('REALBASKET_SQLITE_PATH', DEFAULT_DB))


@contextmanager
def connect(path: str | Path | None = None):
    """Read/write connection; creates the database and the schema if necessary."""
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA foreign_keys = ON')
        con.executescript(_SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _write_dataset(con: sqlite3.Connection, ds, doc_dir: Path) -> None:
    """Replace the canonical dataset tables with the validated dataset `ds` (same transaction as the caller)."""
    for table in _DATASET_TABLES:
        con.execute(f'DELETE FROM {table}')
    meta = {'import_id': uuid.uuid4().hex, 'base_total': repr(ds.base_total), 'source_dir': str(doc_dir),
            'periods': f'{ds.periods[0]:%Y-%m}..{ds.periods[-1]:%Y-%m}'}
    con.executemany('INSERT INTO dataset_meta(key,value) VALUES (?,?)', meta.items())
    con.execute("INSERT INTO dataset_meta(key,value) VALUES ('imported_at', CURRENT_TIMESTAMP)")
    con.executemany('INSERT INTO dataset_documents(position,filename) VALUES (?,?)', enumerate(ds.documents))
    con.executemany('INSERT INTO base_amounts(position,category,amount_eur) VALUES (?,?,?)',
                    [(i, c.value, v) for i, (c, v) in enumerate(ds.base_amounts.items())])
    con.executemany('INSERT INTO prices(position,period,category,item,price_eur,unit,source) VALUES (?,?,?,?,?,?,?)',
                    [(i, p.period.isoformat(), p.category.value, p.item, p.price, p.unit, p.source)
                     for i, p in enumerate(ds.prices)])
    con.executemany('INSERT INTO cpi(position,period,index_value,source) VALUES (?,?,?,?)',
                    [(i, c.period.isoformat(), c.index_value, c.source) for i, c in enumerate(ds.cpi)])
    periods = sorted(set(ds.printed_ecli) | set(ds.printed_ecli_yoy))
    con.executemany('INSERT INTO printed_ecli(period,ecli,ecli_yoy_pct) VALUES (?,?,?)',
                    [(p.isoformat(), ds.printed_ecli.get(p), ds.printed_ecli_yoy.get(p)) for p in periods])
    con.executemany('''INSERT INTO city_rents(position,city,state,rent_jan_eur_m2,rent_oct_eur_m2,
                       rent_jan_flat_eur,rent_oct_flat_eur,change_pct,source) VALUES (?,?,?,?,?,?,?,?,?)''',
                    [(i, c['city'], c['state'], c['rent_jan_eur_m2'], c['rent_oct_eur_m2'], c['rent_jan_flat_eur'],
                      c['rent_oct_flat_eur'], c['change_pct'], c['source']) for i, c in enumerate(ds.city_rents)])
    con.executemany('''INSERT INTO state_coverage(position,state,cities_json,verified_state_series,status,source)
                       VALUES (?,?,?,?,?,?)''',
                    [(i, s['state'], json.dumps(s['cities'], ensure_ascii=False), int(s['verified_state_series']),
                      s['status'], s['source']) for i, s in enumerate(ds.state_coverage)])
    con.executemany('INSERT INTO checks(position,name,ok,detail) VALUES (?,?,?,?)',
                    [(i, c.name, int(c.ok), c.detail) for i, c in enumerate(ds.checks)])


def persist_reference_pdfs(doc_dir: str | Path, path: str | Path | None = None) -> dict:
    """Import: parse + validate the reference PDFs and write them to SQLite (the only place PDFs are read).

    Rejects the import if any of the 11 checks fails (the previous dataset stays untouched). Never interprets
    modelled ECLI costs as observed prices. Reruns are idempotent; provenance keeps every PDF version (sha256).
    """
    from real_basket.data.real_data import load_real_data, parse_document
    from real_basket.knowledge.ingest import extract_pages, file_sha256

    root = Path(doc_dir)
    ds = load_real_data(root)
    failed = [c.name for c in ds.checks if not c.ok]
    if failed:
        raise ValueError('Reference PDF validation failed: ' + ', '.join(failed))
    inserted = 0
    with connect(path) as con:
        _write_dataset(con, ds, root)
        for pdf in sorted(root.glob('*.pdf')):
            parsed = parse_document(pdf)
            if not parsed['costs'] and not parsed['cities']:
                continue
            digest = file_sha256(pdf)
            con.execute('INSERT OR IGNORE INTO documents(sha256,filename,pages,data_basis) VALUES (?,?,?,?)',
                        (digest, pdf.name, len(extract_pages(pdf)), 'modelled_ecli_with_published_city_rents'))
            for period, record in parsed['costs'].items():
                page = int(record['source'].rsplit('S. ', 1)[1])
                for category, value in record['groups'].items():
                    con.execute('''INSERT OR REPLACE INTO observations
                        (document_sha256,period,category,region,metric,value_eur,unit,source_page,data_basis)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (digest, period.isoformat()[:7], category, 'Deutschland', 'essential_cost',
                         value, 'EUR/month', page, 'modelled'))
                    inserted += 1
            for city in parsed['cities']:
                page = int(city['source'].split(' S. ')[1].split(' ')[0])
                for month, key in [('2026-01', 'rent_jan_eur_m2'), ('2026-10', 'rent_oct_eur_m2')]:
                    con.execute('''INSERT OR REPLACE INTO observations
                        (document_sha256,period,category,region,metric,value_eur,unit,source_page,data_basis)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (digest, month, 'Miete', city['city'] + ', ' + city['state'],
                         'asking_cold_rent', city[key], 'EUR/m2', page, 'published_asking_rent'))
                    inserted += 1
    return {'documents': len(ds.documents), 'observations_written': inserted,
            'prices_written': len(ds.prices), 'cpi_written': len(ds.cpi), 'city_rents_written': len(ds.city_rents),
            'checks_passed': sum(c.ok for c in ds.checks),
            'database': str(Path(path) if path else db_path())}


# --- read side ------------------------------------------------------------------------------------------------
def _read_only(target: Path) -> sqlite3.Connection:
    con = sqlite3.connect(target.resolve().as_uri() + '?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    return con


def _import_id(target: Path) -> str:
    from real_basket.data.real_data import RealDataError

    if not target.is_file():
        raise RealDataError(f"SQLite database '{target}' not found - import the reference PDFs first: {IMPORT_HINT}")
    con = _read_only(target)
    try:
        row = con.execute("SELECT value FROM dataset_meta WHERE key='import_id'").fetchone()
    except sqlite3.OperationalError:
        row = None
    finally:
        con.close()
    if row is None:
        raise RealDataError(f"SQLite database '{target}' contains no validated dataset - run: {IMPORT_HINT}")
    return row['value']


@lru_cache(maxsize=4)
def _load(target: str, import_id: str):
    from real_basket.data.real_data import Check, RealDataError, RealDataset
    from real_basket.schemas.models import Category, CpiPoint, PricePoint

    con = _read_only(Path(target))
    try:
        def q(sql: str) -> list[sqlite3.Row]:
            return con.execute(sql).fetchall()

        meta = {r['key']: r['value'] for r in q('SELECT key, value FROM dataset_meta')}
        prices = [PricePoint(category=Category(r['category']), item=r['item'], period=date.fromisoformat(r['period']),
                             price=r['price_eur'], unit=r['unit'], source=r['source'])
                  for r in q('SELECT * FROM prices ORDER BY position')]
        cpi = [CpiPoint(period=date.fromisoformat(r['period']), index_value=r['index_value'], source=r['source'])
               for r in q('SELECT * FROM cpi ORDER BY position')]
        printed = q('SELECT * FROM printed_ecli ORDER BY period')
        ds = RealDataset(
            prices=prices, cpi=cpi,
            base_amounts={Category(r['category']): r['amount_eur']
                          for r in q('SELECT * FROM base_amounts ORDER BY position')},
            base_total=float(meta['base_total']),
            printed_ecli={date.fromisoformat(r['period']): r['ecli'] for r in printed if r['ecli'] is not None},
            printed_ecli_yoy={date.fromisoformat(r['period']): r['ecli_yoy_pct']
                              for r in printed if r['ecli_yoy_pct'] is not None},
            city_rents=[{k: r[k] for k in ('city', 'state', 'rent_jan_eur_m2', 'rent_oct_eur_m2', 'rent_jan_flat_eur',
                                           'rent_oct_flat_eur', 'change_pct', 'source')}
                        for r in q('SELECT * FROM city_rents ORDER BY position')],
            documents=[r['filename'] for r in q('SELECT filename FROM dataset_documents ORDER BY position')],
            state_coverage=[{'state': r['state'], 'cities': json.loads(r['cities_json']),
                             'verified_state_series': bool(r['verified_state_series']), 'status': r['status'],
                             'source': r['source']} for r in q('SELECT * FROM state_coverage ORDER BY position')],
            checks=[Check(r['name'], bool(r['ok']), r['detail']) for r in q('SELECT * FROM checks ORDER BY position')],
        )
    finally:
        con.close()
    if not ds.prices or not ds.cpi or not ds.base_amounts:
        raise RealDataError(f"SQLite dataset in '{target}' is incomplete - run: {IMPORT_HINT}")
    return ds


def load_dataset(path: str | Path | None = None):
    """The validated dataset from SQLite (`RealDataset`), cached per import. Raises `RealDataError`."""
    target = Path(path) if path else db_path()
    return _load(str(target), _import_id(target))


def dataset_info(path: str | Path | None = None) -> dict:
    """Import metadata of the canonical dataset (import id, timestamp, source folder, periods)."""
    target = Path(path) if path else db_path()
    _import_id(target)
    con = _read_only(target)
    try:
        meta = {r['key']: r['value'] for r in con.execute('SELECT key, value FROM dataset_meta')}
    finally:
        con.close()
    return meta | {'database': str(target)}


def get_observations(category: str = '', region: str = '', metric: str = '',
                     start: str = '', end: str = '', path: str | Path | None = None) -> list[dict]:
    """Exact filtered SQL query on the provenance rows; never infer numbers from vector search."""
    parts = []
    params = []
    for column, value in [('category', category), ('region', region), ('metric', metric)]:
        if value:
            parts.append('o.' + column + ' = ?')
            params.append(value)
    for op, value in [('>=', start), ('<=', end)]:
        if value:
            parts.append('o.period ' + op + ' ?')
            params.append(value)
    where = (' WHERE ' + ' AND '.join(parts)) if parts else ''
    with connect(path) as con:
        rows = con.execute('''SELECT o.period,o.category,o.region,o.metric,o.value_eur,o.unit,
            o.source_page,o.data_basis,d.filename,d.sha256 AS document_sha256
            FROM observations o JOIN documents d ON d.sha256=o.document_sha256''' +
                           where + ' ORDER BY o.period,d.filename,o.category LIMIT 10000', params).fetchall()
        return [dict(x) for x in rows]
