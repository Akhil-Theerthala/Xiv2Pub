"""CLI entry point for tex2epub."""

import argparse
import sys
import tempfile
from pathlib import Path

from tex2epub.downloader import parse_arxiv_id, download_source
from tex2epub.extractor import extract_archive, find_main_tex
from tex2epub.preprocessor import preprocess
from tex2epub.converter import convert_to_epub
from tex2epub.postprocessor import postprocess_epub


def _get_package_dir() -> Path:
    """Get the tex2epub package directory."""
    return Path(__file__).parent


def _get_fonts_dir() -> Path:
    """Get the fonts directory."""
    return _get_package_dir().parent / "fonts"


def _get_css_path() -> Path:
    """Get the path to the epub.css file."""
    return _get_package_dir() / "styles" / "epub.css"


def _slugify(title: str) -> str:
    """Convert a paper title to a filesystem-safe filename."""
    import re
    slug = title.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    # Truncate to reasonable length
    if len(slug) > 80:
        slug = slug[:80].rsplit("-", 1)[0]
    return slug


def main():
    parser = argparse.ArgumentParser(
        prog="tex2epub",
        description="Convert arXiv LaTeX papers to EPUB",
    )
    parser.add_argument(
        "input",
        help="arXiv URL (e.g., https://arxiv.org/abs/2602.03545), "
             "arXiv ID (e.g., 2602.03545), "
             "or path to a .tar.gz file",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output EPUB path (default: ./{paper_title}.epub)",
    )
    args = parser.parse_args()

    try:
        _run(args)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


def _run(args):
    input_str = args.input
    css_path = _get_css_path()
    fonts_dir = _get_fonts_dir()

    # Determine input mode
    arxiv_id = parse_arxiv_id(input_str)
    if arxiv_id:
        # Mode 1: Download from arXiv
        archive_path = download_source(arxiv_id)
    else:
        # Mode 2: Local file
        archive_path = Path(input_str)
        if not archive_path.exists():
            raise FileNotFoundError(f"File not found: {archive_path}")

    # Extract
    work_dir = extract_archive(archive_path)

    # Find main tex
    main_tex = find_main_tex(work_dir)

    # Preprocess
    print("Preprocessing LaTeX...")
    preprocessed, metadata = preprocess(main_tex)

    if not metadata.title:
        metadata.title = "Untitled Paper"
        print("  Warning: could not extract paper title")

    print(f"  Title: {metadata.title}")
    if metadata.authors:
        print(f"  Authors: {', '.join(metadata.authors)}")

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        slug = _slugify(metadata.title)
        output_path = Path.cwd() / f"{slug}.epub"

    # Convert with Pandoc
    convert_to_epub(preprocessed, metadata, work_dir, output_path, css_path)

    # Post-process: inject fonts and CSS
    if fonts_dir.exists() and any(fonts_dir.glob("*.otf")):
        print("Embedding fonts...")
        postprocess_epub(output_path, fonts_dir)
    else:
        print("  Fonts directory not found, skipping font embedding")

    print(f"\nDone! Output: {output_path}")


if __name__ == "__main__":
    main()
