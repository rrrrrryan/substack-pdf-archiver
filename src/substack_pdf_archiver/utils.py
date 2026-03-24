from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

_slug_pattern = re.compile(r"[^\w\s-]")
_space_pattern = re.compile(r"[-\s]+")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str, max_length: int = 120) -> str:
    cleaned = _slug_pattern.sub("", value.strip().lower())
    cleaned = _space_pattern.sub("-", cleaned).strip("-")
    if not cleaned:
        return "archive"
    return cleaned[:max_length].rstrip("-") or "archive"


def resolve_target(target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "file"}:
        return target

    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate.resolve().as_uri()

    return target


def default_output_path(
    explicit_output: str | None,
    url: str,
    title: str,
    output_dir: Path,
) -> Path:
    if explicit_output:
        output_path = Path(explicit_output).expanduser().resolve()
        ensure_directory(output_path.parent)
        return output_path

    parsed = urlparse(url)
    fallback = Path(parsed.path).stem or parsed.netloc or "archive"
    slug = slugify(title or fallback)
    out_dir = ensure_directory(output_dir.expanduser().resolve())
    return out_dir / f"{slug}.pdf"


def filename_from_url(url: str, fallback: str = "attachment") -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or fallback
