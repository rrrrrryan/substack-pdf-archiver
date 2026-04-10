from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

_slug_pattern = re.compile(r"[^\w\s-]")
_space_pattern = re.compile(r"[-\s]+")
_control_pattern = re.compile(r"[\x00-\x1F\x7F]")


@dataclass(frozen=True)
class ArchiveNameMetadata:
    title: str
    publication_name: str | None = None
    published_at: str | None = None


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
    metadata: ArchiveNameMetadata,
    output_dir: Path,
) -> Path:
    if explicit_output:
        output_path = Path(explicit_output).expanduser().resolve()
        ensure_directory(output_path.parent)
        return output_path

    basename = build_archive_basename(url=url, metadata=metadata)
    out_dir = ensure_directory(output_dir.expanduser().resolve())
    return out_dir / f"{basename}.pdf"


def filename_from_url(url: str, fallback: str = "attachment") -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name or fallback


def build_archive_basename(url: str, metadata: ArchiveNameMetadata) -> str:
    parts = [
        normalize_published_date(metadata.published_at),
        sanitize_output_component(metadata.publication_name),
        sanitize_output_component(metadata.title),
    ]
    readable_parts = [part for part in parts if part]
    if readable_parts:
        return " - ".join(readable_parts)

    parsed = urlparse(url)
    fallback = Path(parsed.path).stem or parsed.netloc or "archive"
    return slugify(metadata.title or fallback)


def normalize_published_date(value: str | None) -> str | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def sanitize_output_component(value: str | None) -> str | None:
    if not value:
        return None

    text = _control_pattern.sub("", value).strip()
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or None
