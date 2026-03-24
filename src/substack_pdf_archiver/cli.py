from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .archiver import ArchiveError, ArchiveOptions, archive_target, run_login
from .config import DEFAULT_OUTPUT_DIR, DEFAULT_PROFILE_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="substack-pdf",
        description=(
            "Archive authenticated Substack articles and local HTML snapshots to clean PDFs."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser(
        "login",
        help="Open Chromium with a persistent profile so you can log in manually.",
    )
    login_parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Chromium profile directory.",
    )
    login_parser.add_argument(
        "--login-url",
        default="https://substack.com/sign-in",
        help="Login URL to open.",
    )
    login_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    archive_parser = subparsers.add_parser(
        "archive",
        help="Archive an authenticated article URL or local HTML file to PDF.",
    )
    archive_parser.add_argument(
        "target",
        help="Article URL, file:// URL, or local HTML path.",
    )
    archive_parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help="Persistent Chromium profile directory used for auth.",
    )
    archive_parser.add_argument(
        "-o",
        "--output",
        help="Explicit PDF output path.",
    )
    archive_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Default PDF output directory when --output is omitted.",
    )
    archive_parser.add_argument(
        "--paper",
        default="Letter",
        choices=["Letter", "A4"],
        help="Paper format for the generated PDF.",
    )
    archive_parser.add_argument(
        "--timeout-ms",
        type=int,
        default=60_000,
        help="Navigation and selector timeout in milliseconds.",
    )
    archive_parser.add_argument(
        "--wait-ms",
        type=int,
        default=1_500,
        help="Extra settle time after the article selector appears.",
    )
    archive_parser.add_argument(
        "--download-attachments",
        action="store_true",
        help="Download detected file attachments next to the PDF.",
    )
    archive_parser.add_argument(
        "--attachments-dir",
        help="Override attachment download directory.",
    )
    archive_parser.add_argument(
        "--debug-dir",
        help="Write before/after screenshots, cleaned HTML, and debug metadata to this directory.",
    )
    archive_parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the archive browser visibly for debugging.",
    )
    archive_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(levelname)s %(message)s",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    try:
        if args.command == "login":
            run_login(
                user_data_dir=Path(args.profile_dir),
                login_url=args.login_url,
            )
            return

        if args.command == "archive":
            result = archive_target(
                target=args.target,
                options=ArchiveOptions(
                    user_data_dir=Path(args.profile_dir),
                    output_dir=Path(args.output_dir),
                    output_path=args.output,
                    paper_format=args.paper,
                    timeout_ms=args.timeout_ms,
                    wait_ms=args.wait_ms,
                    download_attachments=args.download_attachments,
                    attachments_dir=Path(args.attachments_dir) if args.attachments_dir else None,
                    debug_dir=Path(args.debug_dir) if args.debug_dir else None,
                    headed=args.headed,
                ),
            )
            print(result.pdf_path)
            print(result.metadata_path)
            if result.attachment_paths:
                for path in result.attachment_paths:
                    print(path)
            return
    except ArchiveError as exc:
        parser.exit(1, f"ERROR {exc}\n")

    parser.error(f"Unknown command: {args.command}")
