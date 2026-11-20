#!/bin/sh
set -eu

# SQLite is the single read source of all figures; the PDFs are read only by this import (11 checks).
echo "[RealBasket] Importing the validated reference PDFs into SQLite ..."
python -m real_basket.storage --mode sql

if [ "${REALBASKET_AUTO_INDEX_VECTOR:-false}" = "true" ]; then
    echo "[RealBasket] Indexing PDF method notes in Weaviate ..."
    # Indexing requires a configured embedding provider. Fail explicitly when requested.
    python -m real_basket.storage --mode vector
fi

exec real-basket-mcp --transport streamable-http
