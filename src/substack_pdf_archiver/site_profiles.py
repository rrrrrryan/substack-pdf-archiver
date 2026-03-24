from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page
else:
    Page = Any


@dataclass(frozen=True)
class SiteProfile:
    name: str
    article_selectors: tuple[str, ...]
    body_selectors: tuple[str, ...]
    image_selectors: tuple[str, ...]
    attachment_selectors: tuple[str, ...]
    title_selectors: tuple[str, ...] = ()
    byline_selectors: tuple[str, ...] = ()
    header_selectors: tuple[str, ...] = ()
    chrome_remove_selectors: tuple[str, ...] = ()
    fingerprint_selectors: tuple[str, ...] = ()
    auth_blocked_selectors: tuple[str, ...] = ()
    host_suffixes: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def article_selector(self) -> str:
        return ", ".join(self.article_selectors)

    @property
    def body_selector(self) -> str:
        return ", ".join(self.body_selectors)

    @property
    def image_selector(self) -> str:
        return ", ".join(self.image_selectors)

    @property
    def attachment_selector(self) -> str:
        return ", ".join(self.attachment_selectors)

    @property
    def header_selector(self) -> str:
        return ", ".join(self.header_selectors)

    @property
    def title_selector(self) -> str:
        return ", ".join(self.title_selectors)

    @property
    def byline_selector(self) -> str:
        return ", ".join(self.byline_selectors)

    @property
    def chrome_remove_selector(self) -> str:
        return ", ".join(self.chrome_remove_selectors)


CANONICAL_SUBSTACK_PROFILE = SiteProfile(
    name="substack-canonical",
    host_suffixes=("substack.com",),
    article_selectors=(
        "article.newsletter-post",
        "article.post-viewer-post",
        "article.post",
    ),
    body_selectors=(
        ".available-content",
        ".body.markup",
        "[data-testid='post-content']",
    ),
    image_selectors=(
        ".available-content img",
        ".body.markup img",
        "article img",
    ),
    attachment_selectors=(
        ".file-embed-wrapper a[href]",
        "a.file-embed-button[href]",
        "a[href*='/api/v1/file/'][href]",
    ),
    title_selectors=(
        "article.newsletter-post h1",
        "article.post-viewer-post h1",
        "[data-testid='post-title']",
        "h1",
    ),
    byline_selectors=(
        "[data-testid='post-meta']",
        ".post-meta",
        ".byline",
        "article header",
    ),
    header_selectors=(
        "article header",
        "article .post-header",
        "article .post-hero",
        "article > div:first-child",
    ),
    chrome_remove_selectors=(
        ".header-anchor-parent",
        ".image-link-expand",
        ".subscription-widget-wrap",
        ".paywall-jump",
        "[data-testid='recommendation-footer']",
        "[data-testid='post-footer']",
        "[data-testid='reaction-bar']",
        ".post-footer",
        ".comments-page",
        ".footer-anchor",
        ".button-wrap",
        ".subscribe-widget",
    ),
    auth_blocked_selectors=(
        "form[action*='sign-in']",
        "form input[type='password']",
        "[href*='/sign-in']",
        "[data-testid='signin']",
        ".subscribe-page",
    ),
    fingerprint_selectors=(
        "script[src*='substackcdn.com']",
        "link[href*='substackcdn.com']",
        "meta[name='application-name'][content*='Substack']",
    ),
    metadata={"family": "substack"},
)


CUSTOM_DOMAIN_SUBSTACK_PROFILE = SiteProfile(
    name="substack-custom-domain",
    article_selectors=CANONICAL_SUBSTACK_PROFILE.article_selectors,
    body_selectors=CANONICAL_SUBSTACK_PROFILE.body_selectors,
    image_selectors=CANONICAL_SUBSTACK_PROFILE.image_selectors,
    attachment_selectors=CANONICAL_SUBSTACK_PROFILE.attachment_selectors,
    title_selectors=CANONICAL_SUBSTACK_PROFILE.title_selectors,
    byline_selectors=CANONICAL_SUBSTACK_PROFILE.byline_selectors,
    header_selectors=CANONICAL_SUBSTACK_PROFILE.header_selectors,
    chrome_remove_selectors=CANONICAL_SUBSTACK_PROFILE.chrome_remove_selectors,
    auth_blocked_selectors=CANONICAL_SUBSTACK_PROFILE.auth_blocked_selectors,
    fingerprint_selectors=(
        ".available-content",
        ".file-embed-wrapper",
        "script[src*='substackcdn.com']",
        "link[href*='substackcdn.com']",
        "meta[name='application-name'][content*='Substack']",
    ),
    metadata={"family": "substack"},
)


GENERIC_ARTICLE_PROFILE = SiteProfile(
    name="generic-article",
    article_selectors=(
        "main article",
        "[role='main'] article",
        "article",
        "main",
    ),
    body_selectors=(
        ".article-content",
        ".post-content",
        ".entry-content",
        ".content",
        "[itemprop='articleBody']",
        ".markup",
        "article",
    ),
    image_selectors=(
        "article img",
        "main img",
    ),
    attachment_selectors=(
        ".file-embed-wrapper a[href]",
        "a[download][href]",
        "article a[href$='.pdf']",
        "article a[href$='.zip']",
    ),
    title_selectors=(
        "article h1",
        "main h1",
        "h1",
    ),
    byline_selectors=(
        "[rel='author']",
        ".byline",
        "time",
    ),
    header_selectors=(
        "article header",
        "main header",
        "article > div:first-child",
    ),
    chrome_remove_selectors=(
        "nav",
        "aside",
        ".subscribe-widget",
        ".comments",
        ".reactions",
        ".share-buttons",
    ),
    metadata={"family": "generic"},
)


PROFILE_REGISTRY: tuple[SiteProfile, ...] = (
    CANONICAL_SUBSTACK_PROFILE,
    CUSTOM_DOMAIN_SUBSTACK_PROFILE,
    GENERIC_ARTICLE_PROFILE,
)


def choose_profile(page: Page, url: str) -> SiteProfile:
    host = urlparse(url).hostname or ""
    if _host_matches(host, CANONICAL_SUBSTACK_PROFILE.host_suffixes):
        return CANONICAL_SUBSTACK_PROFILE

    if _page_has_any(page, CUSTOM_DOMAIN_SUBSTACK_PROFILE.fingerprint_selectors):
        return CUSTOM_DOMAIN_SUBSTACK_PROFILE

    return GENERIC_ARTICLE_PROFILE


def first_selector(page: Page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            if page.locator(selector).count() > 0:
                return selector
        except Exception:
            continue
    return None


def page_has_article(page: Page, profile: SiteProfile) -> bool:
    return first_selector(page, profile.article_selectors) is not None


def _host_matches(host: str, suffixes: tuple[str, ...]) -> bool:
    host = host.lower()
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


def _page_has_any(page: Page, selectors: tuple[str, ...]) -> bool:
    return first_selector(page, selectors) is not None
