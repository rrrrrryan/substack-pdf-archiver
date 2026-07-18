from pathlib import Path

from substack_pdf_archiver.utils import (
    ArchiveNameMetadata,
    build_archive_basename,
    default_output_path,
    resolve_target,
    sanitize_output_component,
    slugify,
)


def test_slugify_basic() -> None:
    assert slugify("Global Oil Data Deck (March 2026)") == "global-oil-data-deck-march-2026"


def test_resolve_target_local_file(tmp_path: Path) -> None:
    html_file = tmp_path / "article.html"
    html_file.write_text("<html></html>", encoding="utf-8")
    assert resolve_target(str(html_file)).startswith("file://")


def test_default_output_path_uses_title(tmp_path: Path) -> None:
    output = default_output_path(
        explicit_output=None,
        url="https://example.com/p/some-post",
        metadata=ArchiveNameMetadata(
            title="My Great Post",
            publication_name="Example Publication",
            published_at="2026-03-24T10:30:00+00:00",
        ),
        output_dir=tmp_path,
    )
    assert output == tmp_path / "2026-03-24 - Example Publication - My Great Post.pdf"


def test_build_archive_basename_drops_missing_segments() -> None:
    basename = build_archive_basename(
        url="https://example.com/p/some-post",
        metadata=ArchiveNameMetadata(title="My Great Post", publication_name=None),
    )
    assert basename == "My Great Post"


def test_build_archive_basename_uses_manual_publication_value() -> None:
    basename = build_archive_basename(
        url="https://example.com/p/some-post",
        metadata=ArchiveNameMetadata(
            title="My Great Post",
            publication_name="Manual Publication",
            published_at="2026-03-24T10:30:00+00:00",
        ),
    )
    assert basename == "2026-03-24 - Manual Publication - My Great Post"


def test_build_archive_basename_falls_back_to_slug() -> None:
    basename = build_archive_basename(
        url="https://example.com/p/some-post",
        metadata=ArchiveNameMetadata(title="", publication_name=None, published_at=None),
    )
    assert basename == "some-post"


def test_sanitize_output_component_preserves_readable_punctuation() -> None:
    assert sanitize_output_component("  Market / Outlook?  ") == "Market - Outlook?"
