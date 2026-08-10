from __future__ import annotations

from functools import lru_cache
from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@lru_cache(maxsize=16)
def load_content_skill(name: str) -> str:
    clean_name = name.strip()
    if not clean_name or "/" in clean_name or "\\" in clean_name:
        raise ValueError(f"invalid skill name: {name}")

    skill_path = SKILLS_DIR / clean_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"content skill not found: {clean_name}")
    return skill_path.read_text(encoding="utf-8").strip()
