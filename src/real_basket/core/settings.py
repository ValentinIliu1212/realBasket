from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root (folder with pyproject.toml): src/real_basket/core/settings.py -> parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def resolve_path(path: str | Path) -> Path:
    """Relative paths (KNOWLEDGE_DIR, REALBASKET_SQLITE_PATH, ...) are resolved against the current working directory if they
    exist there, otherwise against the project root - so `streamlit run` works from any folder."""
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return PROJECT_ROOT / p


class Settings(BaseSettings):
    # .env in the project root, overridden by a .env in the current working directory
    model_config = SettingsConfigDict(env_file=(str(PROJECT_ROOT / ".env"), ".env"), env_file_encoding="utf-8",
                                      extra="ignore")

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_ID: str = "gpt-4o-mini"

    # --- Azure OpenAI (used when OPENAI_API_TYPE=azure; see real_basket.core.llm) ------------------
    OPENAI_API_TYPE: str = ""                  # "" / openai -> api.openai.com | azure -> Azure OpenAI
    OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_ENDPOINT: str = ""            # e.g. https://<resource>.openai.azure.com/
    AZURE_OPENAI_API_KEY: str = ""             # falls back to OPENAI_API_KEY when empty
    AZURE_COMPLETION_MODEL: str = ""           # chat deployment name (falls back to OPENAI_MODEL_ID)
    # Embeddings (AZURE_EMBEDDING_MODEL / EMBEDDING_MODEL_ID) are read from the environment by storage/weaviate_store.py

    # --- Reference PDFs: read only by the SQLite import and the Weaviate indexing --------------------
    KNOWLEDGE_DIR: str = "reports/real-data"   # ECLI reference PDFs


@lru_cache
def get_settings() -> Settings:
    return Settings()
