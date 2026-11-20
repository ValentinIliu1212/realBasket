"""Search over the method notes of the reference documents (RAG retrieval).

Retrievers
- `bm25`      keyword search, offline. German-aware: light stemming, compound matching ("Kaltmiete" finds
              "Nettokaltmiete") and a small English -> German glossary so English queries of the agents work.
- `embedding` OpenAI / Azure OpenAI embeddings (multilingual), fused with BM25 by reciprocal rank fusion.
- `auto`      embedding if an LLM provider is configured (see core.llm), else bm25. Embedding errors fall
              back to bm25.

The index (data_store/knowledge/index.json) is rebuilt automatically when the documents change.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

from real_basket.core import llm
from real_basket.core.settings import Settings, get_settings, resolve_path
from real_basket.knowledge.ingest import ingest_documents

INDEX_VERSION = 1
USAGE_NOTE = ("Context and caveats from reference documents only. Cite passages; never take figures from "
              "them - all numbers come from the deterministic calculation tools.")

_STOPWORDS = set("""
der die das den dem des ein eine einer eines einem einen und oder nicht ist sind wird werden wurde wurden
mit von vom zu zum zur im in am an auf aus bei für fur als auch nur noch sich es sie er wie so da dass daher
hier diese dieser dieses diesen kein keine keinen über ueber nach vor bis je pro
the a an and or of to in on for is are was were be by with as at from this that these those it its not no
what which who why how does do did can could should would there their than then into about per
""".split())

# English query terms -> German document vocabulary (keyword retriever only; embeddings are multilingual)
GLOSSARY = {
    "rent": "miete kaltmiete", "rents": "miete mieten", "rental": "miete", "housing": "wohnen",
    "energy": "energie", "food": "lebensmittel", "groceries": "lebensmittel", "mobility": "verkehr",
    "transport": "verkehr", "fuel": "benzin", "health": "gesundheit", "communication": "kommunikation",
    "cpi": "vpi verbraucherpreisindex", "consumer": "verbraucher", "inflation": "vorjahresrate preisindex",
    "state": "bundesland", "states": "bundesland", "federal": "bundesland", "city": "stadt großstadt", "cities": "städte großstädte",
    "regional": "regional", "region": "regional bundesland", "data": "daten", "quality": "datenqualität",
    "modelled": "modellierte modell", "modeled": "modellierte modell", "model": "modell",
    "source": "quelle", "sources": "quellen", "limitation": "grenzen begrenzung",
    "limitations": "grenzen begrenzung", "caveat": "hinweis grenzen", "caveats": "hinweis grenzen",
    "method": "methodische methode", "methodology": "methodische einordnung", "basket": "warenkorb",
    "household": "haushalt", "base": "basis basisbetrag", "cold": "kalt", "net": "netto",
    "asking": "angebot", "offer": "angebot", "survey": "erhebung evs", "price": "preis", "prices": "preise",
    "monthly": "monatlich", "verified": "verifiziert", "measured": "gemessen", "official": "amtlich",
    "costs": "kosten", "cost": "kosten", "maintenance": "instandhaltung", "tobacco": "tabakwaren",
    "representative": "repräsentativ", "estimate": "näherungsmodell", "approximation": "näherungsmodell",
}

_SUFFIXES = ("ungen", "ung", "heit", "keit", "ern", "en", "er", "es", "em", "e", "n", "s")


def stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zäöü0-9]+", text.lower().replace("ß", "ss"))
    return [stem(w) for w in words if w not in _STOPWORDS and len(w) > 1]


def expand_query(query: str) -> list[str]:
    words = re.findall(r"[\wäöüß]+", query.lower())
    return tokenize(" ".join([query, *[GLOSSARY[w] for w in words if w in GLOSSARY]]))


def _matches(term: str, token: str) -> bool:
    # German compounds: the head is at the end ("Nettokaltmiete" -> "miete"); prefixes cover "Verbraucher..."
    return token == term or (len(term) >= 4 and (token.endswith(term) or token.startswith(term)))


class KnowledgeBase:
    def __init__(self, doc_dir: str | Path | None = None, index_path: str | Path | None = None,
                 settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.doc_dir = resolve_path(doc_dir or self.settings.KNOWLEDGE_DIR)
        self.index_path = Path(index_path or resolve_path(self.settings.DATA_DIR) / "knowledge" / "index.json")
        self._index: dict | None = None

    # --- index ----------------------------------------------------------------------------------
    def _files(self) -> list[Path]:
        return sorted(self.doc_dir.glob("*.pdf")) if self.doc_dir.is_dir() else []

    def is_stale(self, index: dict | None) -> bool:
        if not index or index.get("version") != INDEX_VERSION:
            return True
        known = {d["file"]: (d["size"], d["mtime"]) for d in index["documents"]}
        current = {p.name: (p.stat().st_size, p.stat().st_mtime) for p in self._files()}
        return known != current

    def build(self) -> dict:
        documents, chunks = ingest_documents(self.doc_dir) if self._files() else ([], [])
        index = {"version": INDEX_VERSION, "built_at": datetime.now().isoformat(timespec="seconds"),
                 "doc_dir": str(self.doc_dir), "documents": documents, "chunks": chunks, "embeddings": None}
        self._save(index)
        return index

    def _save(self, index: dict) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        self._index = index

    def index(self) -> dict:
        if self._index is None and self.index_path.exists():
            try:
                self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._index = None
        if self.is_stale(self._index):
            self.build()
        return self._index

    def status(self) -> dict:
        idx = self.index()
        kinds = [c["kind"] for c in idx["chunks"]]
        return {"doc_dir": str(self.doc_dir), "built_at": idx["built_at"],
                "documents": [{k: d[k] for k in ("file", "pages", "year", "sha256")} for d in idx["documents"]],
                "chunks": len(kinds), "notes": kinds.count("note"), "tables": kinds.count("table"),
                "retriever": self.retriever()}

    # --- retrieval ------------------------------------------------------------------------------
    def retriever(self) -> str:
        mode = self.settings.KNOWLEDGE_RETRIEVER.lower()
        if mode == "auto":
            return "embedding" if llm.is_configured(self.settings) else "bm25"
        return mode

    def _bm25(self, chunks: list[dict], query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
        terms = list(dict.fromkeys(expand_query(query)))
        docs = [tokenize(f"{c['section']} {c['text']}") for c in chunks]
        if not docs or not terms:
            return [0.0] * len(chunks)
        avg = sum(map(len, docs)) / len(docs)
        tf = [[sum(1 for t in doc if _matches(term, t)) for term in terms] for doc in docs]
        n = len(docs)
        idf = [math.log(1 + (n - df + 0.5) / (df + 0.5))
               for df in (sum(1 for row in tf if row[i]) for i in range(len(terms)))]
        return [sum(idf[i] * f * (k1 + 1) / (f + k1 * (1 - b + b * len(doc) / avg))
                    for i, f in enumerate(row) if f)
                for row, doc in zip(tf, docs)]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        client = llm.sync_client(self.settings)
        resp = client.embeddings.create(model=llm.embedding_model_id(self.settings), input=texts)
        return [d.embedding for d in resp.data]

    def _embedding_scores(self, index: dict, query: str) -> list[float]:
        model = ("azure:" if llm.use_azure(self.settings) else "") + llm.embedding_model_id(self.settings)
        emb = index.get("embeddings")
        if not emb or emb.get("model") != model or len(emb["vectors"]) != len(index["chunks"]):
            vectors = self._embed([f"{c['section']}: {c['text']}" for c in index["chunks"]])
            index["embeddings"] = {"model": model, "vectors": vectors}
            self._save(index)
        q = self._embed([query])[0]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        return [sum(a * b for a, b in zip(q, v)) / (qn * (math.sqrt(sum(x * x for x in v)) or 1.0))
                for v in index["embeddings"]["vectors"]]

    def search(self, query: str, top_k: int | None = None, year: int | None = None) -> dict:
        """Passages for `query` (optionally only from documents of `year`), best first."""
        index = self.index()
        top_k = top_k or self.settings.KNOWLEDGE_TOP_K
        chunks = index["chunks"]
        if not chunks:
            return {"query": query, "retriever": "none", "passages": [],
                    "note": f"No reference documents indexed (folder '{self.doc_dir}')."}
        allowed = [i for i, c in enumerate(chunks) if not year or year in c["years"]]
        bm25 = self._bm25(chunks, query)
        retriever = self.retriever()
        ranked: list[tuple[float, int]]
        if retriever == "embedding":
            try:
                emb = self._embedding_scores(index, query)
                fused: dict[int, float] = {}
                for scores in (bm25, emb):
                    order = sorted(allowed, key=lambda i: -scores[i])
                    for rank, i in enumerate(order):
                        fused[i] = fused.get(i, 0.0) + 1 / (60 + rank)
                ranked = sorted(((fused[i], i) for i in allowed if bm25[i] > 0 or emb[i] >= 0.3), reverse=True)
            except Exception as exc:  # noqa: BLE001 - search must keep working offline
                retriever = f"bm25 (embedding failed: {type(exc).__name__})"
                ranked = sorted(((bm25[i], i) for i in allowed if bm25[i] > 0), reverse=True)
        else:
            ranked = sorted(((bm25[i], i) for i in allowed if bm25[i] > 0), reverse=True)
        passages: list[dict] = []
        for score, i in ranked:
            if len(passages) >= top_k:
                break
            c = chunks[i]
            locations = [f"{loc['file']} p. {loc['page']}" for loc in c["locations"]]
            # near-duplicate (same caveat, one sentence more or less in another yearly report): merge
            dup = next((p for p in passages if c["text"] in p["text"] or p["text"] in c["text"]), None)
            if dup:
                dup["also_in"] += [loc for loc in locations if loc not in dup["also_in"]]
                continue
            first = c["locations"][0]
            passages.append({"chunk_id": c["id"], "kind": c["kind"], "section": c["section"], "text": c["text"],
                             "source": first["file"], "page": first["page"], "also_in": locations[1:],
                             "years": c["years"], "score": round(score, 4)})
        return {"query": query, "retriever": retriever, "passages": passages, "note": USAGE_NOTE}


def main() -> None:
    """CLI: build / inspect the method-notes index and try a query."""
    import argparse

    parser = argparse.ArgumentParser(description="Index reference PDFs (method notes) and search them.")
    parser.add_argument("--docs", help="folder with PDF documents (default: KNOWLEDGE_DIR)")
    parser.add_argument("--rebuild", action="store_true", help="rebuild the index even if unchanged")
    parser.add_argument("--query", help="search query")
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()

    kb = KnowledgeBase(doc_dir=args.docs)
    if args.rebuild:
        kb.build()
    st = kb.status()
    print(f"Index {kb.index_path} (built {st['built_at']}): {len(st['documents'])} document(s), "
          f"{st['notes']} note + {st['tables']} table passages, retriever: {st['retriever']}")
    for d in st["documents"]:
        print(f"  - {d['file']} ({d['pages']} pages, sha256 {d['sha256'][:12]})")
    if args.query:
        res = kb.search(args.query, args.top_k, args.year)
        print(f"\nQuery: {args.query!r} ({res['retriever']})")
        for n, p in enumerate(res["passages"], 1):
            print(f"\n[{n}] {p['source']} p. {p['page']} · {p['section']} · score {p['score']}")
            print(f"    {p['text'][:400]}")
        if not res["passages"]:
            print("No matching passages.")


if __name__ == "__main__":
    main()
