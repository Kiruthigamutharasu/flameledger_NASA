"""Runtime settings. Secrets come only from environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load a local .env file for development. Real environment variables always win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    web_dir: Path
    gemini_api_key: str
    gemini_model: str

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_model)


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "").strip()
    if key.startswith("your_") or model.startswith("your_"):
        key, model = "", ""
    return Settings(
        data_dir=Path(os.environ.get("FLAMELEDGER_DATA_DIR", ROOT / "data")),
        web_dir=ROOT / "web",
        gemini_api_key=key,
        gemini_model=model,
    )
