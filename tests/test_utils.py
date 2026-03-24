from pathlib import Path

from substack_pdf_archiver.utils import default_output_path, resolve_target, slugify


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
        title="My Great Post",
        output_dir=tmp_path,
    )
    assert output == tmp_path / "my-great-post.pdf"
