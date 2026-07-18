You are working in the `substack-pdf-archiver` repo.

Your task is to turn this starter into a reliable personal-archiving tool for authenticated Substack articles, especially paid posts on Substack custom domains.

## Product goal

Given a URL to a Substack article that the user is already authorized to view, produce a clean PDF that:

- preserves the article title, byline, and body
- preserves inline images in the correct order and approximate position
- strips the surrounding app chrome, nav, floating buttons, like bars, and other reader UI
- works with paid content by using the user's existing authenticated browser session
- optionally downloads embedded file attachments beside the PDF

This is for personal archiving of content the user is already entitled to access. Do **not** build credential scraping, paywall bypasses, or anything that tries to access content the user is not authorized to view.

## Non-negotiable constraints

1. **Do not ask for the user's Substack password.**
   Authentication must be based on a manual login flow that saves a persistent browser profile, or on an equivalent manual-cookie/session-state import flow.

2. **Prefer Playwright + Chromium.**
   Use a real browser engine for rendering and printing.

3. **Preserve images.**
   You must explicitly handle lazy-loaded images by scrolling and waiting for image completion before printing.

4. **Print only the article.**
   The PDF should not include the Substack inbox shell, floating toolbars, navigation, or reactions.

5. **Keep the code safe to commit.**
   Do not store credentials in repo files. Ignore browser profiles and output artifacts in git. Warn about fixture sanitization.

## Recommended architecture

Keep the current approach, but strengthen it:

- use a persistent Chromium profile directory for login state
- open the target article in that profile
- wait for article selectors
- auto-scroll until the page height stabilizes
- set all discovered images to eager loading when possible
- wait for all article images to complete
- clone only the article header + article body into a dedicated archive root
- inject dedicated print CSS
- print to PDF with backgrounds enabled

## Improvements to implement

### 1) Make selector handling more robust

Create a site-profile abstraction that can support:

- canonical Substack domains
- custom-domain Substack publications
- future generic article sites

Add better detection and fallback selectors for:

- article container
- title block
- body container
- image nodes
- file attachments

### 2) Make DOM cleanup safer

Right now the starter clones the first direct child of the article as the header and `.available-content` as the body. Improve that logic so it:

- gracefully handles layout variations
- avoids cloning reaction/footer sections
- removes anchor-link buttons, image expansion controls, and subscribe widgets from the archive DOM
- keeps links clickable in the resulting PDF where possible

### 3) Improve image reliability

Add:

- image completion retries
- per-image timeout logging
- a best-effort fallback mode when a minority of images fail
- optional debug screenshots before and after DOM cleanup

### 4) Improve attachment handling

- support file-embed downloads more cleanly
- infer filenames from `Content-Disposition` when available
- deduplicate duplicate file links

### 5) Add tests and fixtures

Add tests for:

- utility functions
- attachment filename resolution
- local sanitized HTML fixtures
- DOM cleanup logic where practical

Do **not** commit raw saved HTML from a real logged-in account unless sanitized first.

### 6) Developer experience

Add:

- Ruff or another linter/formatter
- clearer logging
- richer CLI help text
- better error messages when the user forgot to run `login`
- README examples for both URL input and local HTML input

## Acceptance criteria

A good result should let a user do this:

```bash
substack-pdf login
substack-pdf archive "https://www.somepaidpublication.com/p/some-post" --download-attachments
```

And get:

- a readable PDF with the article header and body only
- inline figures in the right order
- no obvious missing images from lazy loading
- no Substack chrome around the article
- optional downloaded attachment files next to the PDF

## Nice-to-have stretch goals

- optional EPUB export
- optional single-file HTML snapshot export
- optional `--debug-dir` with screenshots and saved cleaned HTML
- optional browser-cookie import from a manual export file

Start by improving the existing structure rather than rewriting everything from scratch.
