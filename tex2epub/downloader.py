"""Download arXiv paper source archives."""

import re
import tempfile
import urllib.request
from pathlib import Path


# Matches arxiv.org URLs like:
#   https://arxiv.org/abs/2602.03545
#   https://arxiv.org/pdf/2602.03545v1
#   http://arxiv.org/abs/2301.12345
#   arxiv.org/html/2602.03545
_ARXIV_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf|html|src)/(\d{4}\.\d{4,5}(?:v\d+)?)"
)

# Also match bare arxiv IDs like "2602.03545" or "2602.03545v1"
_ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5}(?:v\d+)?)$")


def parse_arxiv_id(input_str: str) -> str | None:
    """Extract an arXiv paper ID from a URL or bare ID string."""
    m = _ARXIV_URL_RE.search(input_str)
    if m:
        return m.group(1)
    m = _ARXIV_ID_RE.match(input_str.strip())
    if m:
        return m.group(1)
    return None


def download_source(arxiv_id: str, dest_dir: Path | None = None) -> Path:
    """Download the LaTeX source .tar.gz for a given arXiv paper ID.

    Returns the path to the downloaded file.
    """
    url = f"https://arxiv.org/src/{arxiv_id}"

    if dest_dir is None:
        dest_dir = Path(tempfile.mkdtemp(prefix="tex2epub_"))

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"arXiv-{arxiv_id}.tar.gz"

    print(f"Downloading {url} ...")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tex2epub/0.1 (academic paper converter)",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    dest_path.write_bytes(data)
    size_mb = len(data) / (1024 * 1024)
    print(f"Downloaded {dest_path.name} ({size_mb:.1f} MB)")
    return dest_path
