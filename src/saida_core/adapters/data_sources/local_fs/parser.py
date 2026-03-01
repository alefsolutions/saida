from __future__ import annotations

from pathlib import Path

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".log",
    ".py",
    ".sql",
}


def is_supported_text_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS


def read_text_file(path: Path, max_chars: int = 20_000) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    return content[:max_chars]


def parse_file(path: Path, max_chars: int = 20_000) -> dict:
    if not is_supported_text_file(path):
        return {"text": "", "length": 0, "extension": path.suffix.lower()}
    text = read_text_file(path, max_chars=max_chars)
    return {
        "text": text,
        "length": len(text),
        "extension": path.suffix.lower(),
    }


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    if not text:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks
