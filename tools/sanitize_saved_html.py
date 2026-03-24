#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

PRELOAD_PATTERNS = [
    re.compile(r"<script>\s*window\._preloads.*?</script>", flags=re.DOTALL),
    re.compile(r"<script>\s*window\._analyticsConfig.*?</script>", flags=re.DOTALL),
]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d()\-\s]{7,}\d")


def sanitize_html(raw: str) -> str:
    cleaned = raw
    for pattern in PRELOAD_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = EMAIL_RE.sub("redacted@example.com", cleaned)
    cleaned = PHONE_RE.sub("+10000000000", cleaned)
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove obvious preload blobs and common PII from saved HTML."
    )
    parser.add_argument("input_html", help="Input HTML file")
    parser.add_argument("output_html", help="Output HTML file")
    args = parser.parse_args()

    input_path = Path(args.input_html).expanduser().resolve()
    output_path = Path(args.output_html).expanduser().resolve()

    raw = input_path.read_text(encoding="utf-8")
    cleaned = sanitize_html(raw)
    output_path.write_text(cleaned, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
