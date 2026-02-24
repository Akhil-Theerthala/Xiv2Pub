"""Pandoc-based LaTeX to EPUB3 conversion."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from tex2epub.preprocessor import PaperMetadata


def convert_to_epub(
    preprocessed_tex: str,
    metadata: PaperMetadata,
    work_dir: Path,
    output_path: Path,
    css_path: Path,
) -> Path:
    """Convert preprocessed LaTeX to EPUB3 using Pandoc.

    Returns the path to the generated EPUB.
    """
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError(
            "Pandoc not found. Install with: brew install pandoc"
        )

    # Write preprocessed tex to a temp file in the work dir
    tex_file = work_dir / "_preprocessed.tex"
    tex_file.write_text(preprocessed_tex)

    # Find bibliography file
    bib_files = list(work_dir.glob("*.bib"))

    # Build Pandoc command
    cmd = [
        pandoc,
        str(tex_file),
        "--from", "latex",
        "--to", "epub3",
        "--mathml",
        "--toc",
        "--toc-depth=2",
        "--split-level=1",
        f"--resource-path={work_dir}",
        f"--css={css_path}",
        "-o", str(output_path),
    ]

    # Add bibliography if available
    if bib_files:
        cmd.extend(["--citeproc", f"--bibliography={bib_files[0]}"])

    # Add metadata
    if metadata.title:
        cmd.extend(["--metadata", f"title={metadata.title}"])
    if metadata.authors:
        for author in metadata.authors:
            cmd.extend(["--metadata", f"author={author}"])

    print(f"Running Pandoc...")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=work_dir,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Pandoc often outputs warnings that aren't fatal
        if not output_path.exists():
            raise RuntimeError(f"Pandoc failed:\n{stderr}")
        if stderr:
            # Print warnings but continue
            warning_lines = [l for l in stderr.split("\n") if l.strip()]
            if len(warning_lines) <= 10:
                for line in warning_lines:
                    print(f"  [pandoc] {line}")
            else:
                print(f"  [pandoc] {len(warning_lines)} warnings (showing first 5)")
                for line in warning_lines[:5]:
                    print(f"  [pandoc] {line}")

    if not output_path.exists():
        raise RuntimeError("Pandoc produced no output file")

    size_kb = output_path.stat().st_size / 1024
    print(f"Pandoc output: {output_path.name} ({size_kb:.0f} KB)")
    return output_path
