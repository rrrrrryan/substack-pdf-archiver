# substack-pdf-archiver

A small Playwright-based starter for turning authenticated Substack articles into clean PDFs with the inline figures preserved in the right order.

The design goal is simple:

- log in once in a real browser
- save the authenticated browser profile locally
- open a Substack or custom-domain Substack article
- scroll until lazy-loaded images are actually fetched
- strip the surrounding app chrome
- print just the article header + article body to PDF
- optionally download embedded attachments beside the PDF

This tool is intentionally conservative about authentication:

- **it never asks for your Substack password**
- **it never stores credentials in code or config**
- **it uses a persistent Chromium profile directory instead**
- **it can archive local sanitized HTML fixtures without a logged-in profile**

## Why this approach works

Substack pages are easiest to archive with a real browser engine rather than by parsing HTML and rebuilding the article from scratch.

This repo uses Playwright + Chromium so the same layout engine that rendered the page can also print it. That usually gives you much better odds of keeping figures, widths, image ordering, and page flow intact.

## Repo status

The repo now includes:

- a CLI with `login` and `archive` subcommands
- persistent-profile authentication
- site-profile detection for canonical Substack, custom-domain Substack, and a generic article fallback
- auto-scroll, lazy-image hydration, and image retry logic
- DOM cleanup before printing with archive-only header/body extraction
- optional attachment download support with metadata sidecars
- optional debug artifacts (`screenshots` + `cleaned.html`)
- a helper script for sanitizing saved HTML fixtures before committing them to git
- Ruff + pytest-based development tooling

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
playwright install chromium
```

### 1) Log in once

```bash
substack-pdf login
```

This opens Chromium with a persistent profile directory. Log in manually, verify that your subscriptions are accessible, then return to the terminal and press Enter.

### 2) Archive an article

```bash
substack-pdf archive "https://www.commoditycontext.com/p/global-oil-data-deck-march-2026"
```

That will create a PDF and a JSON sidecar in `./output/`, using a readable default stem like `2026-03-23 - Commodity Context - Global Oil Data Deck (March 2026)`.

### 3) Pick a specific output path

```bash
substack-pdf archive \
  "https://www.commoditycontext.com/p/global-oil-data-deck-march-2026" \
  -o ./output/global-oil-data-deck-march-2026.pdf
```

### 4) Download embedded attachments too

```bash
substack-pdf archive \
  "https://www.commoditycontext.com/p/global-oil-data-deck-march-2026" \
  --download-attachments
```

The default attachment directory uses the same stem as the PDF.

### 5) Override the publication name used for naming/metadata

```bash
substack-pdf archive \
  "https://www.commoditycontext.com/p/global-oil-data-deck-march-2026" \
  --publication "Commodity Context"
```

### 6) Capture debug artifacts for cleanup/image issues

```bash
substack-pdf archive \
  "https://www.commoditycontext.com/p/global-oil-data-deck-march-2026" \
  --debug-dir ./.archive-debug/run-001
```

That writes:

- `before-cleanup.png`
- `after-cleanup.png`
- `cleaned.html`
- `archive.json`

## Local HTML input

If you already have a saved HTML file plus its asset folder, you can point the tool at the file path instead of a URL:

```bash
substack-pdf archive "/path/to/saved_article.html"
```

The CLI will convert a local path to a `file://` URL automatically.

Synthetic or sanitized local HTML fixtures are useful for DOM-cleanup regression tests. Local HTML input does not require a logged-in Substack profile.

## Important privacy note for fixtures

If you save Substack pages from your own account, the HTML may contain account/session metadata inside embedded preload JSON. Before checking any fixture into git, run:

```bash
python tools/sanitize_saved_html.py input.html sanitized.html
```

That helper strips the obvious preload blobs and masks common email/phone patterns. It is still worth reviewing the output manually.

## CLI reference

### `substack-pdf login`

```bash
substack-pdf login \
  --profile-dir ~/.substack-pdf-profile \
  --login-url https://substack.com/sign-in
```

### `substack-pdf archive`

```bash
substack-pdf archive TARGET \
  --profile-dir ~/.substack-pdf-profile \
  --output-dir ./output \
  --publication "Publication Name" \
  --paper Letter \
  --timeout-ms 60000 \
  --wait-ms 1500 \
  --download-attachments \
  --debug-dir ./.archive-debug/latest
```

Arguments:

- `TARGET`: an `https://...` URL, a `file://...` URL, or a local HTML path
- `--profile-dir`: Chromium profile used for login persistence
- `-o/--output`: explicit PDF output path
- `--output-dir`: directory for default PDF output when `-o` is omitted
- `--publication`: override the extracted publication name for default naming and manifest metadata
- `--paper`: `Letter` or `A4`
- `--timeout-ms`: navigation and selector timeout
- `--wait-ms`: extra settle time after initial article detection
- `--download-attachments`: save file-embed attachments in a sidecar directory
- `--attachments-dir`: override attachment destination
- `--debug-dir`: save before/after screenshots, cleaned HTML, and debug metadata
- `--headed`: open Chromium visibly during archive runs for debugging
- `--log-level`: `DEBUG`, `INFO`, `WARNING`, or `ERROR`

## Current implementation details

The archive flow is:

1. open the page in Chromium using the persistent profile
2. detect the best site profile for the page
3. wait for article selectors or stop with a clear `login` hint
4. scroll repeatedly to trigger lazy-loaded media
5. retry image completion and continue only when failures are a minority
6. optionally download deduplicated attachment links
7. clone the article header/body into a dedicated archive root and strip reader chrome
8. inject print CSS and render a PDF with backgrounds enabled
9. write an `.archive.json` manifest beside the PDF

## Development

Run tests:

```bash
pytest
```

Run lint:

```bash
ruff check .
```

Format:

```bash
ruff format .
```
