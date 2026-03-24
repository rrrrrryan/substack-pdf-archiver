from __future__ import annotations

from substack_pdf_archiver.site_profiles import (
    CANONICAL_SUBSTACK_PROFILE,
    CUSTOM_DOMAIN_SUBSTACK_PROFILE,
    GENERIC_ARTICLE_PROFILE,
    choose_profile,
)


class FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakePage:
    def __init__(self, matches: set[str]) -> None:
        self._matches = matches

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(1 if selector in self._matches else 0)


def test_choose_profile_prefers_canonical_substack_host() -> None:
    page = FakePage(set())
    assert choose_profile(page, "https://example.substack.com/p/test") == CANONICAL_SUBSTACK_PROFILE


def test_choose_profile_detects_custom_domain_substack_markup() -> None:
    page = FakePage({".available-content"})
    assert (
        choose_profile(page, "https://www.somepaidpublication.com/p/test")
        == CUSTOM_DOMAIN_SUBSTACK_PROFILE
    )


def test_choose_profile_falls_back_to_generic_article() -> None:
    page = FakePage({"article"})
    assert choose_profile(page, "https://example.com/story") == GENERIC_ARTICLE_PROFILE
