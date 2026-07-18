from pathlib import Path

from substack_pdf_archiver.cli import build_parser
from substack_pdf_archiver.config import DEFAULT_OUTPUT_DIR


def test_archive_parser_defaults_output_dir_to_current_directory() -> None:
    args = build_parser().parse_args(["archive", "https://example.com/p/some-post"])
    assert args.output_dir == str(DEFAULT_OUTPUT_DIR)
    assert DEFAULT_OUTPUT_DIR == Path.cwd()
