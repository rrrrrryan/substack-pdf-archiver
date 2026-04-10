from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

import requests

from .config import DEFAULT_OUTPUT_DIR, DEFAULT_PROFILE_DIR
from .print_css import SUBSTACK_ARCHIVE_PRINT_CSS
from .site_profiles import SiteProfile, choose_profile, first_selector
from .utils import (
    ArchiveNameMetadata,
    default_output_path,
    ensure_directory,
    filename_from_url,
    resolve_target,
    slugify,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page
else:
    Page = Any

logger = logging.getLogger(__name__)
_BYLINE_MONTH_DATE_PATTERN = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}",
    flags=re.IGNORECASE,
)
_PLAIN_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class ArchiveError(RuntimeError):
    """Base archiver error."""


class LoginRequiredError(ArchiveError):
    """Raised when an authenticated browser profile is missing or expired."""


@dataclass
class ArchiveOptions:
    user_data_dir: Path = DEFAULT_PROFILE_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    output_path: str | None = None
    publication_name: str | None = None
    paper_format: str = "Letter"
    timeout_ms: int = 60_000
    wait_ms: int = 1_500
    download_attachments: bool = False
    attachments_dir: Path | None = None
    debug_dir: Path | None = None
    headed: bool = False
    browser_args: list[str] = field(
        default_factory=lambda: [
            "--disable-blink-features=AutomationControlled",
            "--font-render-hinting=medium",
        ]
    )


@dataclass
class ImageIssue:
    src: str
    reason: str


@dataclass
class AttachmentRecord:
    url: str
    filename: str
    path: Path
    label: str


@dataclass
class ArchiveResult:
    pdf_path: Path
    attachment_paths: list[Path]


def run_login(user_data_dir: Path, login_url: str = "https://substack.com/sign-in") -> None:
    from playwright.sync_api import sync_playwright

    user_data_dir = ensure_directory(user_data_dir.expanduser().resolve())

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport={"width": 1440, "height": 1100},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--font-render-hinting=medium",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        logger.info("Opening login page: %s", login_url)
        page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)
        print("\nComplete login in the browser window.")
        print("When you can open a paid Substack post normally, return here and press Enter.\n")
        input()
        context.close()
        logger.info("Saved browser profile to %s", user_data_dir)


def archive_target(
    target: str,
    options: ArchiveOptions,
    profile: SiteProfile | None = None,
) -> ArchiveResult:
    from playwright.sync_api import sync_playwright

    target_url = resolve_target(target)
    user_data_dir = options.user_data_dir.expanduser().resolve()
    local_input = _is_local_target(target_url)
    _ensure_login_state(user_data_dir, local_input=local_input)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ensure_directory(user_data_dir)),
            headless=not options.headed,
            viewport={"width": 1440, "height": 1400},
            args=options.browser_args,
        )
        page = context.pages[0] if context.pages else context.new_page()

        logger.info("Navigating to %s", target_url)
        page.goto(target_url, wait_until="domcontentloaded", timeout=options.timeout_ms)
        detected_profile = profile or choose_profile(page, target_url)
        _wait_for_article(
            page, detected_profile, target_url, options.timeout_ms, local_input=local_input
        )
        page.wait_for_timeout(options.wait_ms)
        _dismiss_simple_overlays(page)

        archive_name = _extract_archive_name_metadata(
            page,
            detected_profile,
            publication_override=options.publication_name,
        )
        pdf_path = default_output_path(
            explicit_output=options.output_path,
            url=page.url,
            metadata=archive_name,
            output_dir=options.output_dir,
        )
        ensure_directory(pdf_path.parent)

        debug_dir = _resolve_debug_dir(options.debug_dir)
        if debug_dir:
            _save_screenshot(page, debug_dir / "before-cleanup.png")

        _auto_scroll(page)
        _promote_images_to_eager(page, detected_profile.image_selector)
        _ensure_images_ready(page, detected_profile.image_selector, options.timeout_ms)

        attachment_records: list[AttachmentRecord] = []
        if options.download_attachments:
            attachments_root = options.attachments_dir or pdf_path.with_suffix("")
            attachment_records = _download_attachments(page, detected_profile, attachments_root)

        _prepare_clean_archive_dom(page, detected_profile)
        page.add_style_tag(content=SUBSTACK_ARCHIVE_PRINT_CSS)
        _ensure_images_ready(page, "#__archive_root__ img", options.timeout_ms)

        if debug_dir:
            _save_screenshot(page, debug_dir / "after-cleanup.png")
            cleaned_html_path = debug_dir / "cleaned.html"
            cleaned_html_path.write_text(page.content(), encoding="utf-8")

        page.emulate_media(media="print")
        logger.info("Writing PDF to %s", pdf_path)
        page.pdf(
            path=str(pdf_path),
            format=options.paper_format,
            print_background=True,
            margin={
                "top": "0.55in",
                "right": "0.65in",
                "bottom": "0.70in",
                "left": "0.65in",
            },
        )
        context.close()

    return ArchiveResult(
        pdf_path=pdf_path,
        attachment_paths=[record.path for record in attachment_records],
    )


def _is_local_target(target_url: str) -> bool:
    return urlparse(target_url).scheme == "file"


def _ensure_login_state(user_data_dir: Path, local_input: bool) -> None:
    if local_input:
        return

    if not user_data_dir.exists() or not any(user_data_dir.iterdir()):
        raise LoginRequiredError(
            f"No browser profile found at {user_data_dir}. Run `substack-pdf login` first."
        )


def _wait_for_article(
    page: Page,
    profile: SiteProfile,
    target_url: str,
    timeout_ms: int,
    *,
    local_input: bool,
) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    for selector in profile.article_selectors:
        try:
            page.wait_for_selector(selector, timeout=timeout_ms)
            return
        except PlaywrightTimeoutError:
            logger.debug("Article selector did not match yet: %s", selector)

    if not local_input and _looks_like_auth_gate(page, target_url, profile):
        raise LoginRequiredError(
            "The article did not render in the authenticated browser profile. "
            "Run `substack-pdf login` again and confirm the target post opens in that browser."
        )

    raise ArchiveError(
        f"Could not find an article container for profile `{profile.name}` at {page.url}."
    )


def _looks_like_auth_gate(page: Page, target_url: str, profile: SiteProfile) -> bool:
    current = page.url.lower()
    if any(token in current for token in ("/sign-in", "/signin", "/subscribe", "/account/login")):
        return True

    selector = first_selector(page, profile.auth_blocked_selectors)
    if selector:
        logger.debug("Detected auth gate via selector: %s", selector)
        return True

    target_host = urlparse(target_url).hostname
    current_host = urlparse(page.url).hostname
    return bool(
        target_host and current_host and target_host != current_host and "substack" in current
    )


def _dismiss_simple_overlays(page: Page) -> None:
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        page.keyboard.press("Escape")
    except Exception:
        logger.debug("Overlay dismiss attempt failed", exc_info=True)


def _auto_scroll(page: Page, max_passes: int = 36, settle_ms: int = 450) -> None:
    last_height = -1
    stable_passes = 0

    for _ in range(max_passes):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(settle_ms)
        current_height = int(page.evaluate("document.body.scrollHeight"))
        if current_height == last_height:
            stable_passes += 1
            if stable_passes >= 3:
                break
        else:
            stable_passes = 0
            last_height = current_height

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(250)


def _promote_images_to_eager(page: Page, image_selector: str) -> None:
    page.evaluate(
        """
        (selector) => {
          for (const img of document.querySelectorAll(selector)) {
            img.loading = "eager";
            img.decoding = "sync";
            if (!img.getAttribute("fetchpriority")) {
              img.setAttribute("fetchpriority", "high");
            }
            const candidate = img.getAttribute("data-src")
              || img.getAttribute("data-srcset")
              || img.getAttribute("data-original-src");
            if (!img.currentSrc && candidate && !img.src) {
              img.src = candidate;
            }
          }
        }
        """,
        image_selector,
    )


def _ensure_images_ready(
    page: Page, image_selector: str, timeout_ms: int, retries: int = 3
) -> list[ImageIssue]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    timeout_per_pass = max(1_000, timeout_ms // max(retries, 1))
    failures: list[dict[str, str]] = []
    total = int(
        page.evaluate(
            """
        (selector) => document.querySelectorAll(selector).length
        """,
            image_selector,
        )
    )
    if total == 0:
        return []

    for attempt in range(1, retries + 1):
        _promote_images_to_eager(page, image_selector)
        _focus_incomplete_images(page, image_selector)
        try:
            page.wait_for_function(
                """
                (selector) => {
                  const imgs = Array.from(document.querySelectorAll(selector));
                  if (!imgs.length) {
                    return true;
                  }
                  return imgs.every((img) => img.complete && img.naturalWidth > 0);
                }
                """,
                arg=image_selector,
                timeout=timeout_per_pass,
            )
            return []
        except PlaywrightTimeoutError:
            failures = _collect_incomplete_images(page, image_selector)
            for failure in failures:
                logger.warning(
                    "Image still incomplete after attempt %s/%s: %s (%s)",
                    attempt,
                    retries,
                    failure["src"],
                    failure["reason"],
                )

    if failures and len(failures) * 2 >= total:
        raise ArchiveError(
            f"Too many images failed to load ({len(failures)}/{total}). "
            "Retry with `--headed` or use `--debug-dir` to inspect the page state."
        )

    return [ImageIssue(src=item["src"], reason=item["reason"]) for item in failures]


def _focus_incomplete_images(page: Page, image_selector: str) -> None:
    page.evaluate(
        """
        (selector) => {
          const imgs = Array.from(document.querySelectorAll(selector));
          for (const img of imgs) {
            if (img.complete && img.naturalWidth > 0) {
              continue;
            }
            img.scrollIntoView({ block: "center", inline: "center" });
          }
        }
        """,
        image_selector,
    )
    page.wait_for_timeout(500)


def _collect_incomplete_images(page: Page, image_selector: str) -> list[dict[str, str]]:
    return list(
        page.evaluate(
            """
            (selector) => {
              return Array.from(document.querySelectorAll(selector))
                .filter((img) => !img.complete || img.naturalWidth === 0)
                .map((img) => ({
                  src: img.currentSrc || img.src || img.getAttribute("data-src") || "unknown-image",
                  reason: img.complete ? "naturalWidth=0" : "not-complete",
                }));
            }
            """,
            image_selector,
        )
    )


def _extract_title(page: Page, profile: SiteProfile) -> str:
    for selector in profile.title_selectors:
        locator = page.locator(selector)
        try:
            if locator.count() > 0:
                text = (locator.first.text_content() or "").strip()
                if text:
                    return text
        except Exception:
            logger.debug("Title selector failed: %s", selector, exc_info=True)
    return page.title().strip() or "substack-archive"


def _extract_archive_name_metadata(
    page: Page,
    profile: SiteProfile,
    publication_override: str | None,
) -> ArchiveNameMetadata:
    title = _extract_title(page, profile)
    candidates = _extract_naming_candidates(page, profile)
    publication_name = _normalize_publication_name(
        publication_override
    ) or _select_publication_name(
        candidates,
    )
    if publication_name and publication_name.casefold() == title.casefold():
        publication_name = None

    return ArchiveNameMetadata(
        title=title,
        publication_name=publication_name,
        published_at=_select_published_at(candidates),
    )


def _extract_naming_candidates(page: Page, profile: SiteProfile) -> dict[str, str | None]:
    return page.evaluate(
        """
        ({ articleSelectors, bylineSelectors }) => {
          const pick = (root, selectors) => {
            for (const selector of selectors) {
              const node = root.querySelector(selector);
              if (node) {
                return node;
              }
            }
            return null;
          };

          const textValue = (node) => {
            if (!node) {
              return null;
            }
            const text = (node.textContent || "").replace(/\\s+/g, " ").trim();
            return text || null;
          };

          const contentValue = (selectors) => {
            for (const selector of selectors) {
              const node = document.querySelector(selector);
              if (!node) {
                continue;
              }
              const value = node.getAttribute("content")
                || node.getAttribute("datetime")
                || textValue(node);
              if (value && value.trim()) {
                return value.trim();
              }
            }
            return null;
          };

          let jsonLdPublication = null;
          let jsonLdPublishedAt = null;
          const visit = (value) => {
            if (!value || typeof value !== "object") {
              return;
            }
            if (Array.isArray(value)) {
              for (const item of value) {
                visit(item);
              }
              return;
            }

            if (!jsonLdPublication) {
              const publisher = value.publisher || value.isPartOf;
              const publishers = Array.isArray(publisher) ? publisher : [publisher];
              for (const entry of publishers) {
                if (typeof entry === "string" && entry.trim()) {
                  jsonLdPublication = entry.trim();
                  break;
                }
                if (
                  entry
                  && typeof entry === "object"
                  && typeof entry.name === "string"
                  && entry.name.trim()
                ) {
                  jsonLdPublication = entry.name.trim();
                  break;
                }
              }
            }

            if (!jsonLdPublishedAt) {
              for (const key of ["datePublished", "dateCreated", "uploadDate", "dateModified"]) {
                if (typeof value[key] === "string" && value[key].trim()) {
                  jsonLdPublishedAt = value[key].trim();
                  break;
                }
              }
            }

            for (const nestedKey of ["@graph", "mainEntity"]) {
              if (value[nestedKey]) {
                visit(value[nestedKey]);
              }
            }
          };

          for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
            try {
              visit(JSON.parse(script.textContent || "null"));
            } catch (error) {
              continue;
            }
          }

          const article = pick(document, articleSelectors) || document;
          const bylineNode = pick(article, bylineSelectors) || pick(document, bylineSelectors);
          const visibleTimeNode = pick(article, ["time[datetime]", "time"])
            || pick(document, ["time[datetime]", "time"]);

          return {
            json_ld_publication: jsonLdPublication,
            meta_publication: contentValue([
              'meta[property="og:site_name"]',
              'meta[name="og:site_name"]',
              'meta[name="application-name"]',
            ]),
            visible_publication: contentValue([
              "[data-testid='navbar'] h1",
              "[data-testid='navbar'] a[href='/']",
              "header[role='banner'] h1",
              "header[role='banner'] a[rel='home']",
              "header[role='banner'] a[href='/']",
              "a[rel='home']",
            ]),
            json_ld_published_at: jsonLdPublishedAt,
            meta_published_at: contentValue([
              'meta[property="article:published_time"]',
              'meta[name="article:published_time"]',
              'meta[property="og:article:published_time"]',
              'meta[name="parsely-pub-date"]',
              'meta[itemprop="datePublished"]',
              'meta[name="pubdate"]',
            ]),
            visible_published_at: visibleTimeNode
              ? (visibleTimeNode.getAttribute("datetime") || textValue(visibleTimeNode))
              : null,
            byline_text: textValue(bylineNode),
          };
        }
        """,
        {
            "articleSelectors": list(profile.article_selectors),
            "bylineSelectors": list(profile.byline_selectors),
        },
    )


def _select_publication_name(candidates: dict[str, str | None]) -> str | None:
    for key in ("json_ld_publication", "meta_publication", "visible_publication"):
        publication_name = _normalize_publication_name(candidates.get(key))
        if publication_name:
            return publication_name
    return None


def _normalize_publication_name(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    if cleaned.casefold() == "substack":
        return None
    return cleaned


def _select_published_at(candidates: dict[str, str | None]) -> str | None:
    for key in (
        "json_ld_published_at",
        "meta_published_at",
        "visible_published_at",
        "byline_text",
    ):
        published_at = _normalize_published_at(candidates.get(key))
        if published_at:
            return published_at
    return None


def _normalize_published_at(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    if re.fullmatch(_PLAIN_DATE_PATTERN, cleaned):
        return cleaned

    if "T" in cleaned or "+" in cleaned[10:] or cleaned.endswith("Z"):
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass

    date_match = _PLAIN_DATE_PATTERN.search(cleaned)
    if date_match:
        return date_match.group(0)

    for date_format in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(cleaned, date_format).date().isoformat()
        except ValueError:
            continue

    match = _BYLINE_MONTH_DATE_PATTERN.search(cleaned)
    if not match:
        return None

    raw_date = match.group(0)
    for date_format in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw_date, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _prepare_clean_archive_dom(page: Page, profile: SiteProfile) -> None:
    page.evaluate(
        """
        ({
          articleSelectors,
          bodySelectors,
          headerSelectors,
          titleSelectors,
          bylineSelectors,
          removeSelectors
        }) => {
          const pick = (root, selectors) => {
            for (const selector of selectors) {
              const node = root.querySelector(selector);
              if (node) {
                return node;
              }
            }
            return null;
          };

          const removeMatches = (root, selectors) => {
            for (const selector of selectors) {
              for (const node of root.querySelectorAll(selector)) {
                node.remove();
              }
            }
          };

          const article = pick(document, articleSelectors);
          if (!article) {
            throw new Error(`Could not find article for selectors: ${articleSelectors.join(", ")}`);
          }

          const headerNode = pick(article, headerSelectors);
          const titleNode = pick(article, titleSelectors) || pick(document, titleSelectors);
          const bylineNode = pick(article, bylineSelectors) || pick(document, bylineSelectors);
          const bodyNode = pick(article, bodySelectors) || article;

          const root = document.createElement("main");
          root.id = "__archive_root__";

          const header = document.createElement("header");
          header.className = "archive-header";
          if (headerNode) {
            header.appendChild(headerNode.cloneNode(true));
          } else {
            if (titleNode) {
              header.appendChild(titleNode.cloneNode(true));
            }
            if (bylineNode) {
              header.appendChild(bylineNode.cloneNode(true));
            }
          }

          const bodyClone = bodyNode.cloneNode(true);
          if (bodyNode === article) {
            const duplicateHeader = pick(bodyClone, headerSelectors);
            if (duplicateHeader) {
              duplicateHeader.remove();
            } else {
              const duplicateTitle = pick(bodyClone, titleSelectors);
              if (duplicateTitle) {
                duplicateTitle.remove();
              }
              const duplicateByline = pick(bodyClone, bylineSelectors);
              if (duplicateByline) {
                duplicateByline.remove();
              }
            }
          }

          removeMatches(header, removeSelectors);
          removeMatches(bodyClone, removeSelectors);
          removeMatches(bodyClone, [
            "button",
            "[role='button']",
            ".floating",
            ".sticky",
            "[aria-label='Expand image']",
            "[aria-label='Open in popup']",
            "[data-testid='reaction-bar']",
            "[data-testid='post-footer']",
          ]);

          const meaningfulHeader = header.textContent && header.textContent.trim().length > 0;
          if (meaningfulHeader) {
            root.appendChild(header);
          }
          root.appendChild(bodyClone);

          document.body.replaceChildren(root);
          document.body.className = "";
          document.body.removeAttribute("style");
          document.documentElement.setAttribute("data-substack-archived", "true");

          for (const img of root.querySelectorAll("img")) {
            img.loading = "eager";
            img.decoding = "sync";
          }
        }
        """,
        {
            "articleSelectors": list(profile.article_selectors),
            "bodySelectors": list(profile.body_selectors),
            "headerSelectors": list(profile.header_selectors),
            "titleSelectors": list(profile.title_selectors),
            "bylineSelectors": list(profile.byline_selectors),
            "removeSelectors": list(profile.chrome_remove_selectors),
        },
    )
    page.wait_for_timeout(250)


def _download_attachments(
    page: Page, profile: SiteProfile, destination_root: Path
) -> list[AttachmentRecord]:
    destination_root = ensure_directory(destination_root.expanduser().resolve())
    links = _collect_attachment_links(page, profile)
    if not links:
        logger.info("No attachment links found")
        return []

    session = requests.Session()
    for cookie in page.context.cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain"),
            path=cookie.get("path", "/"),
        )

    saved_records: list[AttachmentRecord] = []
    for idx, link in enumerate(links, start=1):
        href = link["href"]
        logger.info("Downloading attachment %s", href)
        response = session.get(href, timeout=60)
        response.raise_for_status()
        fallback = filename_from_url(href, fallback=f"attachment-{idx}")
        filename = _filename_from_response(response, fallback=fallback)
        out_path = _unique_path(destination_root, _sanitize_filename(filename))
        out_path.write_bytes(response.content)
        saved_records.append(
            AttachmentRecord(
                url=href,
                filename=out_path.name,
                path=out_path,
                label=link["text"],
            )
        )

    return saved_records


def _collect_attachment_links(page: Page, profile: SiteProfile) -> list[dict[str, str]]:
    return list(
        page.evaluate(
            """
            ({ selectors, pageUrl }) => {
              const seen = new Set();
              const results = [];
              for (const selector of selectors) {
                for (const el of document.querySelectorAll(selector)) {
                  const rawHref = el.href || el.getAttribute("href");
                  if (!rawHref) continue;
                  const href = new URL(rawHref, pageUrl).toString();
                  if (seen.has(href)) continue;
                  seen.add(href);
                  results.push({
                    href,
                    text: (el.textContent || "").trim(),
                  });
                }
              }
              return results;
            }
            """,
            {"selectors": list(profile.attachment_selectors), "pageUrl": page.url},
        )
    )


def _filename_from_response(response: requests.Response, fallback: str) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    patterns = (
        r"filename\*=UTF-8''([^;]+)",
        r'filename="([^"]+)"',
        r"filename=([^;]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, content_disposition, flags=re.IGNORECASE)
        if match:
            candidate = unquote(match.group(1).strip().strip('"'))
            if candidate:
                return candidate
    return fallback


def _sanitize_filename(name: str) -> str:
    path_name = Path(name).name.strip()
    if not path_name:
        return "attachment"

    suffix = "".join(Path(path_name).suffixes)
    stem = path_name[: -len(suffix)] if suffix else path_name
    normalized_stem = slugify(stem, max_length=100).replace("-", "_") or "attachment"
    safe_suffix = re.sub(r"[^A-Za-z0-9.]+", "", suffix)
    return f"{normalized_stem}{safe_suffix}" if safe_suffix else normalized_stem


def _unique_path(root: Path, filename: str) -> Path:
    candidate = root / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        next_candidate = root / f"{stem}-{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def _resolve_debug_dir(debug_dir: Path | None) -> Path | None:
    if not debug_dir:
        return None
    return ensure_directory(debug_dir.expanduser().resolve())


def _save_screenshot(page: Page, path: Path) -> Path:
    page.screenshot(path=str(path), full_page=True)
    return path
