"""WeaviateVectorStore-backed semantic document retrieval with PDF citations.

Uses the existing reference-document chunker, which excludes numeric tables;
structured financial figures must come from sqlite_store instead.
"""
from __future__ import annotations

import os
from pathlib import Path


def _client():
    import weaviate
    from weaviate.classes.init import AdditionalConfig, Timeout
    return weaviate.connect_to_local(
        host=os.getenv('WEAVIATE_HOST', 'localhost'),
        port=int(os.getenv('WEAVIATE_HTTP_PORT', '8080')),
        grpc_port=int(os.getenv('WEAVIATE_GRPC_PORT', '50051')),
        additional_config=AdditionalConfig(timeout=Timeout(init=30, query=60, insert=120)),
    )


def _embeddings():
    from langchain_openai import AzureOpenAIEmbeddings, OpenAIEmbeddings
    if os.getenv('AZURE_OPENAI_ENDPOINT') and os.getenv('AZURE_OPENAI_API_KEY'):
        return AzureOpenAIEmbeddings(azure_deployment=os.environ['AZURE_EMBEDDING_MODEL'],
                                    api_version=os.getenv('OPENAI_API_VERSION', '2024-10-21'))
    return OpenAIEmbeddings(model=os.getenv('EMBEDDING_MODEL_ID', 'text-embedding-3-small'))


def _store(client):
    from langchain_weaviate import WeaviateVectorStore
    return WeaviateVectorStore(client=client,
                              index_name=os.getenv('WEAVIATE_INDEX_NAME', 'RealBasketDocuments'),
                              text_key='text', embedding=_embeddings())


def ingest_pdf_directory(directory: str | Path) -> dict:
    from langchain_core.documents import Document
    from real_basket.knowledge.ingest import ingest_documents
    documents, chunks = ingest_documents(Path(directory))
    if not documents:
        raise ValueError('No PDFs found; nothing indexed')
    client = _client()
    try:
        store = _store(client)
        # Deterministic chunk identifiers for idempotency; recreate only if IDs absent.
        import uuid
        docs = [Document(page_content=c['text'], metadata={
            'chunk_id': c['id'], 'section': c['section'], 'kind': c['kind'],
            'source_file': c['locations'][0]['file'], 'page': c['locations'][0]['page'],
            'locations': '; '.join(f"{loc['file']} S.{loc['page']}" for loc in c['locations']),
            'years': ','.join(map(str,c['years']))
        }) for c in chunks]
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, 'realbasket:' + c['id'])) for c in chunks]
        if docs:
            # Weaviate version-dependent duplicate-id semantics: replace prior objects by ID.
            collection = client.collections.get(os.getenv('WEAVIATE_INDEX_NAME', 'RealBasketDocuments'))
            if collection.exists():
                for obj_id in ids:
                    try:
                        collection.data.delete_by_id(obj_id)
                    except Exception:
                        pass
            store.add_documents(docs, ids=ids)
        return {'documents': len(documents), 'chunks': len(chunks),
                'vector_store': os.getenv('WEAVIATE_INDEX_NAME', 'RealBasketDocuments')}
    finally:
        client.close()


def search_documents(query: str, k: int = 5, year: int = 0) -> dict:
    if not query.strip():
        raise ValueError('query is required')
    if not 1 <= k <= 30:
        raise ValueError('k must be between 1 and 30')
    client = _client()
    try:
        store = _store(client)
        # Filter after retrieval for portable client behaviour; increase retrieval pool.
        results = store.similarity_search(query, k=max(k, 30) if year else k)
        if year:
            results = [d for d in results if str(year) in d.metadata.get('years', '').split(',')]
        return {'query': query, 'passages': [
            {'text': d.page_content, **d.metadata} for d in results[:k]],
            'warning': 'Context only. Never use vector search to supply numerical values.'}
    finally:
        client.close()
