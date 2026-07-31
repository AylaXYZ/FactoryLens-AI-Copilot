from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: Literal["demo", "openai", "ollama"] = "demo"
    embedding_provider: Literal["demo", "openai", "ollama", "bge"] = "demo"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "bge-m3"
    bge_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    top_k: int = 4
    data_dir: Path = Path(".factorylens")

    @property
    def index_path(self) -> Path:
        if self.embedding_provider == "demo":
            return self.data_dir / "index.json"
        model = {
            "openai": self.openai_embedding_model,
            "ollama": self.ollama_embedding_model,
            "bge": self.bge_embedding_model,
        }[self.embedding_provider]
        safe_model = re.sub(r"[^a-zA-Z0-9_-]+", "-", model).strip("-").lower()
        return self.data_dir / f"index-{self.embedding_provider}-{safe_model}.json"

    @property
    def work_order_path(self) -> Path:
        return self.data_dir / "work_orders.jsonl"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
