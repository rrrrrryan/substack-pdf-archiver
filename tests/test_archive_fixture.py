from __future__ import annotations

import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from substack_pdf_archiver.archiver import (
    ArchiveOptions,
    _collect_attachment_links,
    _prepare_clean_archive_dom,
    archive_target,
)
from substack_pdf_archiver.site_profiles import CUSTOM_DOMAIN_SUBSTACK_PROFILE, choose_profile

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "custom_domain_substack.html"


@pytest.fixture
def attachment_server(tmp_path: Path):
    attachment_root = tmp_path / "server"
    attachment_root.mkdir()
    (attachment_root / "deck.pdf").write_bytes(b"%PDF-1.4\nfixture\n")

    handler = partial(SimpleHTTPRequestHandler, directory=str(attachment_root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/deck.pdf"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_dom_cleanup_removes_chrome_and_preserves_links(chromium_available: bool) -> None:
    if not chromium_available:
        pytest.skip("Chromium is not installed for Playwright")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FIXTURE_PATH.resolve().as_uri())
        profile = choose_profile(page, page.url)
        assert profile == CUSTOM_DOMAIN_SUBSTACK_PROFILE
        _prepare_clean_archive_dom(page, profile)

        assert page.locator("#__archive_root__").count() == 1
        assert page.locator("#__archive_root__ .subscription-widget-wrap").count() == 0
        assert page.locator("#__archive_root__ [data-testid='reaction-bar']").count() == 0
        assert page.locator("#__archive_root__ a[href='https://example.com/source']").count() == 1
        browser.close()


def test_archive_local_fixture_writes_pdf_metadata_and_downloads(
    chromium_available: bool,
    tmp_path: Path,
    attachment_server: str,
) -> None:
    if not chromium_available:
        pytest.skip("Chromium is not installed for Playwright")

    fixture_html = FIXTURE_PATH.read_text(encoding="utf-8").replace(
        "__ATTACHMENT_URL__", attachment_server
    )
    target_path = tmp_path / "article.html"
    target_path.write_text(fixture_html, encoding="utf-8")

    result = archive_target(
        str(target_path),
        ArchiveOptions(
            user_data_dir=tmp_path / "profile",
            output_dir=tmp_path / "output",
            download_attachments=True,
            debug_dir=tmp_path / "debug",
            timeout_ms=10_000,
            wait_ms=250,
        ),
    )

    assert result.pdf_path.exists()
    assert result.metadata_path.exists()
    assert len(result.attachment_paths) == 1
    assert result.attachment_paths[0].name == "deck.pdf"
    assert (tmp_path / "debug" / "before-cleanup.png").exists()
    assert (tmp_path / "debug" / "after-cleanup.png").exists()
    assert (tmp_path / "debug" / "cleaned.html").exists()

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert metadata["profile"] == "substack-custom-domain"
    assert metadata["attachments"][0]["filename"] == "deck.pdf"
    assert metadata["debug_artifacts"]["cleaned_html"].endswith("cleaned.html")


def test_collect_attachment_links_deduplicates_urls(chromium_available: bool) -> None:
    if not chromium_available:
        pytest.skip("Chromium is not installed for Playwright")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FIXTURE_PATH.resolve().as_uri())
        links = _collect_attachment_links(page, CUSTOM_DOMAIN_SUBSTACK_PROFILE)
        hrefs = [item["href"] for item in links]
        assert len(hrefs) == len(set(hrefs))
        browser.close()
