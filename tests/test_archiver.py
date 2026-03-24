from __future__ import annotations

from pathlib import Path

from substack_pdf_archiver.archiver import _filename_from_response, _sanitize_filename, _unique_path


class DummyResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_filename_from_response_prefers_utf8_filename() -> None:
    response = DummyResponse(
        {"content-disposition": "attachment; filename*=UTF-8''deck%20march%202026.pdf"}
    )
    assert _filename_from_response(response, fallback="fallback.pdf") == "deck march 2026.pdf"


def test_sanitize_filename_strips_path_components() -> None:
    assert _sanitize_filename("../Quarterly Deck?.pdf") == "quarterly_deck.pdf"


def test_unique_path_adds_numeric_suffix(tmp_path: Path) -> None:
    original = tmp_path / "report.pdf"
    original.write_bytes(b"one")
    assert _unique_path(tmp_path, "report.pdf") == tmp_path / "report-2.pdf"
