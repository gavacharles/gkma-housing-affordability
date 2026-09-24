"""Load config.yaml and resolve project-relative paths."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict:
    # GKMA_CONFIG lets the synthetic demo run with its own paths
    cfg_path = Path(path or os.environ.get("GKMA_CONFIG") or ROOT / "config.yaml")
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    with open(cfg_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def p(rel: str) -> Path:
    """Resolve a config path relative to the project root."""
    path = Path(rel)
    return path if path.is_absolute() else ROOT / path


def user_agent() -> str:
    """User-Agent for web requests; the contact email is optional."""
    c = load_config()["collection"]
    ua = c["user_agent"]
    email = (c.get("contact_email") or "").strip()
    return f"{ua[:-1]}; contact: {email})" if email and ua.endswith(")") else ua
