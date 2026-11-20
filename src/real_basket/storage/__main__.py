"""Run both PDF ingestion pipelines from the CLI."""
import argparse
from real_basket.data.real_data import real_data_dir
from real_basket.storage.sqlite_store import persist_reference_pdfs
from real_basket.storage.weaviate_store import ingest_pdf_directory

p = argparse.ArgumentParser()
p.add_argument('--mode', choices=['sql','vector','all'], default='all')
a = p.parse_args()
if a.mode in ('sql', 'all'):
    print(persist_reference_pdfs(real_data_dir()))
if a.mode in ('vector', 'all'):
    print(ingest_pdf_directory(real_data_dir()))
