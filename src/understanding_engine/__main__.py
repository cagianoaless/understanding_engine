"""CLI exit codes: 0=text, 2=failure/usage, 3=valid but textless PDF."""

import argparse
import logging

from .contracts import ExtractionError
from .output import parse_to_directory

LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract local PDF characters and derived text offline")
    parser.add_argument("input_pdf", help="Local PDF path")
    parser.add_argument("--output-dir", required=True, help="New output directory (must not already exist)")
    parser.add_argument("--debug", action="store_true", help="Include tracebacks and backend diagnostics")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s %(name)s %(message)s", force=True)
    if not args.debug:
        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        logging.getLogger("pdfplumber").setLevel(logging.ERROR)
    try:
        run = parse_to_directory(args.input_pdf, args.output_dir)
    except ExtractionError as exc:
        LOGGER.error("%s: %s", exc.code, exc, exc_info=args.debug)
        return 2
    except Exception:
        LOGGER.error("internal_error: unexpected failure; use --debug for diagnostics", exc_info=args.debug)
        return 2
    LOGGER.info("published status=%s pages=%d characters=%d", run["status"],
                run["statistics"]["page_count"], run["statistics"]["character_count"])
    return 3 if run["status"] == "textless" else 0


if __name__ == "__main__":
    raise SystemExit(main())
