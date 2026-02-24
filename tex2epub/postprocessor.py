"""EPUB post-processing: inject fonts, fix CSS, and link citations."""

import re
import zipfile
import tempfile
import shutil
from pathlib import Path


# Font files to embed
FONT_FILES = [
    "lmroman10-regular.otf",
    "lmroman10-bold.otf",
    "lmroman10-italic.otf",
    "lmroman10-bolditalic.otf",
    "lmsans10-regular.otf",
    "lmsans10-bold.otf",
    "lmmono10-regular.otf",
]

# CSS @font-face declarations for embedded fonts
FONT_FACE_CSS = """
/* Latin Modern fonts (embedded) */
@font-face {
    font-family: 'Latin Modern Roman';
    src: url(../fonts/lmroman10-regular.otf) format('opentype');
    font-weight: normal;
    font-style: normal;
}
@font-face {
    font-family: 'Latin Modern Roman';
    src: url(../fonts/lmroman10-bold.otf) format('opentype');
    font-weight: bold;
    font-style: normal;
}
@font-face {
    font-family: 'Latin Modern Roman';
    src: url(../fonts/lmroman10-italic.otf) format('opentype');
    font-weight: normal;
    font-style: italic;
}
@font-face {
    font-family: 'Latin Modern Roman';
    src: url(../fonts/lmroman10-bolditalic.otf) format('opentype');
    font-weight: bold;
    font-style: italic;
}
@font-face {
    font-family: 'Latin Modern Sans';
    src: url(../fonts/lmsans10-regular.otf) format('opentype');
    font-weight: normal;
    font-style: normal;
}
@font-face {
    font-family: 'Latin Modern Sans';
    src: url(../fonts/lmsans10-bold.otf) format('opentype');
    font-weight: bold;
    font-style: normal;
}
@font-face {
    font-family: 'Latin Modern Mono';
    src: url(../fonts/lmmono10-regular.otf) format('opentype');
    font-weight: normal;
    font-style: normal;
}
"""

# CSS body styles (appended after font-face)
BODY_CSS = """
/* tex2epub typography */
body {
    font-family: 'Latin Modern Roman', 'Palatino', 'Georgia', serif;
    font-size: 1em;
    line-height: 1.5;
    color: #1a1a1a;
    margin: 0 1em;
    text-align: justify;
    hyphens: auto;
    -webkit-hyphens: auto;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Latin Modern Sans', 'Helvetica Neue', 'Helvetica', sans-serif;
    color: #000;
    line-height: 1.2;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    text-align: left;
}

h1 { font-size: 1.6em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
h2 { font-size: 1.3em; }
h3 { font-size: 1.1em; }

p { margin: 0.5em 0; text-indent: 1.5em; }
h1 + p, h2 + p, h3 + p, h4 + p, figure + p, blockquote + p { text-indent: 0; }

figure, div.figure { margin: 1em 0; text-align: center; page-break-inside: avoid; }
img { max-width: 100%; height: auto; }
figcaption { font-size: 0.85em; color: #333; margin-top: 0.5em; text-align: left; line-height: 1.3; padding: 0 0.5em; }

table { border-collapse: collapse; margin: 1em auto; font-size: 0.9em; }
thead { border-top: 2px solid #000; border-bottom: 1px solid #000; }
tbody { border-bottom: 2px solid #000; }
th, td { padding: 0.4em 0.8em; text-align: left; }

math[display="block"] { display: block; text-align: center; margin: 0.8em 0; }

code, pre { font-family: 'Latin Modern Mono', 'Menlo', 'Consolas', monospace; font-size: 0.85em; }
pre { background: #f5f5f5; padding: 0.8em; border-radius: 3px; overflow-x: auto; }

blockquote { margin: 1em 0; padding: 0.8em 1em; background: #fafafa; border-left: 3px solid #ddd; font-size: 0.92em; }
blockquote p { text-indent: 0; }

a { color: #1a5276; text-decoration: none; }
"""


def postprocess_epub(epub_path: Path, fonts_dir: Path) -> None:
    """Post-process an EPUB file: embed fonts, inject CSS, and link citations.

    Modifies the EPUB file in-place by:
    1. Adding Latin Modern font files to EPUB/fonts/
    2. Replacing/augmenting the CSS with our typography
    3. Updating the OPF manifest to include the fonts
    4. Converting citation <span>s to <a> links pointing to bibliography
    """
    if not epub_path.exists():
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="tex2epub_post_"))

    try:
        # Extract EPUB (it's a ZIP)
        with zipfile.ZipFile(epub_path, "r") as zf:
            zf.extractall(tmp_dir)

        # Find the EPUB content directory
        content_dir = _find_content_dir(tmp_dir)

        # 1. Add font files
        epub_fonts_dir = content_dir / "fonts"
        epub_fonts_dir.mkdir(exist_ok=True)
        for font_name in FONT_FILES:
            src = fonts_dir / font_name
            if src.exists():
                shutil.copy2(src, epub_fonts_dir / font_name)

        # 2. Inject CSS
        _inject_css(content_dir)

        # 3. Update OPF manifest with font entries
        _update_manifest(content_dir)

        # 4. Link inline citations to bibliography entries
        _link_citations(content_dir)

        # Repackage EPUB
        _repackage_epub(tmp_dir, epub_path)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    size_kb = epub_path.stat().st_size / 1024
    print(f"Post-processed: {epub_path.name} ({size_kb:.0f} KB)")


def _find_content_dir(epub_dir: Path) -> Path:
    """Find the EPUB content directory (usually EPUB/ or OEBPS/)."""
    for candidate in ["EPUB", "OEBPS", "OPS", "content"]:
        d = epub_dir / candidate
        if d.is_dir():
            return d
    # Fallback: look for .opf file
    for opf in epub_dir.rglob("*.opf"):
        return opf.parent
    raise FileNotFoundError("Cannot find EPUB content directory")


def _inject_css(content_dir: Path) -> None:
    """Replace or augment the main CSS file with our styles."""
    # Pandoc typically creates a stylesheet in the content dir
    css_files = list(content_dir.rglob("*.css"))

    full_css = FONT_FACE_CSS + BODY_CSS

    if css_files:
        # Replace the first CSS file
        css_files[0].write_text(full_css)
    else:
        # Create a new one
        css_dir = content_dir / "css"
        css_dir.mkdir(exist_ok=True)
        (css_dir / "style.css").write_text(full_css)


def _update_manifest(content_dir: Path) -> None:
    """Add font entries to the OPF manifest."""
    opf_files = list(content_dir.rglob("*.opf"))
    if not opf_files:
        return

    opf_path = opf_files[0]
    content = opf_path.read_text()

    # Check if fonts are already in the manifest
    if "lmroman10-regular.otf" in content:
        return

    # Add font items to the manifest
    font_items = ""
    for font_name in FONT_FILES:
        item_id = font_name.replace(".", "-").replace("-otf", "")
        font_items += f'    <item id="{item_id}" href="fonts/{font_name}" media-type="font/otf"/>\n'

    # Insert before </manifest>
    content = content.replace("</manifest>", font_items + "  </manifest>")
    opf_path.write_text(content)


def _link_citations(content_dir: Path) -> None:
    """Convert citation <span>s to <a> links pointing to bibliography entries.

    Pandoc's citeproc generates:
      - Inline: <span class="citation" data-cites="key">(Author Year)</span>
      - Bib:    <div id="ref-key" class="csl-entry">...</div>

    This converts inline spans to <a> links with href to the bib chapter.
    """
    text_dir = content_dir / "text"
    if not text_dir.is_dir():
        return

    xhtml_files = sorted(text_dir.glob("*.xhtml"))
    if not xhtml_files:
        return

    # 1. Find which chapter contains the bibliography (has id="ref-..." entries)
    bib_chapter = None
    bib_ids: set[str] = set()
    for xf in xhtml_files:
        content = xf.read_text()
        ids = re.findall(r'id="(ref-[^"]+)"', content)
        if len(ids) > 5:  # bibliography chapter has many ref- IDs
            bib_chapter = xf.name
            bib_ids = set(ids)
            break

    if not bib_chapter or not bib_ids:
        return

    # 2. In every XHTML file, wrap citation spans in <a> links.
    #    We wrap rather than replace to avoid breaking nested <span> tags
    #    that citeproc puts inside multi-cite references.
    linked = 0
    for xf in xhtml_files:
        content = xf.read_text()
        if 'data-cites=' not in content:
            continue

        # Find each citation span opening tag and wrap the whole span in <a>
        result = []
        pos = 0
        marker = '<span class="citation" data-cites="'
        while True:
            idx = content.find(marker, pos)
            if idx == -1:
                result.append(content[pos:])
                break

            # Emit everything before this citation
            result.append(content[pos:idx])

            # Extract data-cites value
            q_start = idx + len(marker)
            q_end = content.index('"', q_start)
            cites_str = content[q_start:q_end]

            # Find the matching </span> by counting nesting
            span_start = idx
            tag_end = content.index('>', q_end) + 1
            depth = 1
            scan = tag_end
            while depth > 0 and scan < len(content):
                next_open = content.find('<span', scan)
                next_close = content.find('</span>', scan)
                if next_close == -1:
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    scan = next_open + 5
                else:
                    depth -= 1
                    if depth == 0:
                        span_end = next_close + len('</span>')
                    scan = next_close + 7

            full_span = content[span_start:span_end]

            # Build the link target from the first cite key
            first_key = cites_str.split()[0]
            ref_id = f"ref-{first_key}"

            if ref_id in bib_ids:
                href = f"{bib_chapter}#{ref_id}"
                result.append(f'<a href="{href}">{full_span}</a>')
                linked += 1
            else:
                result.append(full_span)

            pos = span_end

        content = "".join(result)
        xf.write_text(content)

    if linked:
        print(f"  Linked {linked} citations to bibliography")


def _repackage_epub(epub_dir: Path, output_path: Path) -> None:
    """Repackage an extracted EPUB directory into a .epub file."""
    # EPUB spec requires mimetype to be first, uncompressed
    with zipfile.ZipFile(output_path, "w") as zf:
        mimetype_path = epub_dir / "mimetype"
        if mimetype_path.exists():
            zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)

        for path in sorted(epub_dir.rglob("*")):
            if path.is_file() and path.name != "mimetype":
                arcname = str(path.relative_to(epub_dir))
                zf.write(path, arcname, compress_type=zipfile.ZIP_DEFLATED)
