"""Extract arXiv .tar.gz source bundles and find the main .tex file."""

import json
import tarfile
import tempfile
from pathlib import Path


def extract_archive(archive_path: Path, dest_dir: Path | None = None) -> Path:
    """Extract a .tar.gz archive to a directory.

    Returns the extraction directory.
    """
    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="tex2epub_src_"))
    dest_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        # Security: filter out absolute paths and path traversal
        members = []
        for m in tar.getmembers():
            if m.name.startswith("/") or ".." in m.name:
                continue
            members.append(m)
        tar.extractall(dest_dir, members=members)

    print(f"Extracted to {dest_dir}")
    return dest_dir


def find_main_tex(work_dir: Path) -> Path:
    """Find the main .tex file in an extracted arXiv source directory.

    Strategy:
    1. Check 00README.json for the toplevel source
    2. Look for a file named main.tex
    3. Scan all .tex files for \\documentclass
    """
    # Strategy 1: 00README.json
    readme = work_dir / "00README.json"
    if readme.exists():
        try:
            data = json.loads(readme.read_text())
            for source in data.get("sources", []):
                if source.get("usage") == "toplevel":
                    candidate = work_dir / source["filename"]
                    if candidate.exists():
                        print(f"Main file (from 00README.json): {candidate.name}")
                        return candidate
        except (json.JSONDecodeError, KeyError):
            pass

    # Strategy 2: main.tex
    main_tex = work_dir / "main.tex"
    if main_tex.exists():
        print(f"Main file: main.tex")
        return main_tex

    # Strategy 3: scan for \documentclass
    for tex_file in sorted(work_dir.glob("*.tex")):
        content = tex_file.read_text(errors="replace")
        if r"\documentclass" in content:
            print(f"Main file (has \\documentclass): {tex_file.name}")
            return tex_file

    raise FileNotFoundError(f"No main .tex file found in {work_dir}")
