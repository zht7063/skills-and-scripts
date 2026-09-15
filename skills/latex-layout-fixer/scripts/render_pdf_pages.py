#!/usr/bin/env python3
"""Render selected PDF pages to PNG using pdftoppm or mutool."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path


def page_count(pdf: Path) -> int:
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        raise SystemExit("Rendering all pages requires pdfinfo; pass --pages explicitly instead.")
    result = subprocess.run([pdfinfo, str(pdf)], check=True, capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise SystemExit("Could not read page count from pdfinfo output.")
    return int(match.group(1))


def parse_pages(spec: str, maximum: int | None = None) -> list[int]:
    if spec.lower() == "all":
        if maximum is None:
            raise ValueError("Maximum page count is required for 'all'.")
        return list(range(1, maximum + 1))
    pages: set[int] = set()
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"Invalid descending range: {item}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(item))
    if not pages or min(pages) < 1:
        raise ValueError("Pages must be positive integers.")
    if maximum is not None and max(pages) > maximum:
        raise ValueError(f"Requested page {max(pages)} but the PDF has {maximum} pages.")
    return sorted(pages)


def render_with_pdftoppm(executable: str, pdf: Path, output_dir: Path, pages: list[int], dpi: int) -> list[Path]:
    outputs: list[Path] = []
    for page in pages:
        prefix = output_dir / f"page-{page:03d}"
        subprocess.run(
            [executable, "-f", str(page), "-l", str(page), "-r", str(dpi), "-png", "-singlefile", str(pdf), str(prefix)],
            check=True,
        )
        outputs.append(prefix.with_suffix(".png"))
    return outputs


def render_with_mutool(executable: str, pdf: Path, output_dir: Path, pages: list[int], dpi: int) -> list[Path]:
    outputs: list[Path] = []
    for page in pages:
        output = output_dir / f"page-{page:03d}.png"
        subprocess.run([executable, "draw", "-q", "-F", "png", "-r", str(dpi), "-o", str(output), str(pdf), str(page)], check=True)
        outputs.append(output)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="PDF to render")
    parser.add_argument("--pages", default="all", help="Page list such as 4-6,9; default: all")
    parser.add_argument("--output-dir", default="layout-renders", help="Directory for PNG files")
    parser.add_argument("--dpi", type=int, default=144, help="Raster resolution; default: 144")
    args = parser.parse_args()

    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")
    if args.dpi < 72:
        raise SystemExit("Use at least 72 DPI for meaningful visual inspection.")
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    maximum = page_count(pdf) if args.pages.lower() == "all" else None
    try:
        pages = parse_pages(args.pages, maximum)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    pdftoppm = shutil.which("pdftoppm")
    mutool = shutil.which("mutool")
    if pdftoppm:
        outputs = render_with_pdftoppm(pdftoppm, pdf, output_dir, pages, args.dpi)
    elif mutool:
        outputs = render_with_mutool(mutool, pdf, output_dir, pages, args.dpi)
    else:
        raise SystemExit("Neither pdftoppm nor mutool is available.")

    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
