"""LaTeX preprocessor: transform arXiv LaTeX into Pandoc-friendly LaTeX.

Multi-pass regex pipeline that strips conference macros, resolves includes,
converts custom environments, and extracts metadata.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PaperMetadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    date: str = ""


def preprocess(tex_path: Path) -> tuple[str, PaperMetadata]:
    """Run the full preprocessing pipeline on a .tex file.

    Returns (preprocessed_latex, metadata).
    """
    work_dir = tex_path.parent
    content = tex_path.read_text(errors="replace")

    content = _resolve_includes(content, work_dir)
    metadata = _extract_metadata(content)
    content = _strip_preamble(content)
    content = _strip_conference_commands(content, metadata)
    content = _convert_environments(content)
    content = _expand_simple_macros(content)
    content = _fix_image_paths(content, work_dir)
    content = _prepare_bibliography(content, work_dir)
    content = _final_cleanup(content)
    content = _rebuild_document(content, metadata)

    return content, metadata


def _resolve_includes(content: str, work_dir: Path, depth: int = 0) -> str:
    """Inline \\input{} and \\include{} commands recursively."""
    if depth > 10:
        return content

    def _replace_input(m: re.Match) -> str:
        filename = m.group(1)
        if not filename.endswith(".tex"):
            filename += ".tex"
        path = work_dir / filename
        if path.exists():
            sub = path.read_text(errors="replace")
            return _resolve_includes(sub, path.parent, depth + 1)
        return m.group(0)  # keep original if file not found

    content = re.sub(r"\\input\{([^}]+)\}", _replace_input, content)
    content = re.sub(r"\\include\{([^}]+)\}", _replace_input, content)
    return content


def _extract_metadata(content: str) -> PaperMetadata:
    """Extract title, authors, abstract from the LaTeX source."""
    meta = PaperMetadata()

    # Title — try conference-specific first, then standard
    for pattern in [
        r"\\icmltitle\{(.+?)\}",
        r"\\neurips.*?title\{(.+?)\}",
        r"\\title\{(.+?)\}",
    ]:
        m = re.search(pattern, content, re.DOTALL)
        if m:
            meta.title = _clean_tex(m.group(1))
            break

    # Authors — try conference-specific patterns
    # ICML style: \icmlauthor{Name}{affiliation}
    icml_authors = re.findall(r"\\icmlauthor\{([^}]+)\}", content)
    if icml_authors:
        meta.authors = [_clean_tex(a) for a in icml_authors]
    else:
        # Standard \author{...} — may contain \and separators
        m = re.search(r"\\author\{(.+?)\}", content, re.DOTALL)
        if m:
            author_block = m.group(1)
            parts = re.split(r"\\and\b", author_block)
            meta.authors = [_clean_tex(a) for a in parts if _clean_tex(a)]

    # Abstract
    m = re.search(
        r"\\begin\{abstract\}(.+?)\\end\{abstract\}", content, re.DOTALL
    )
    if m:
        meta.abstract = m.group(1).strip()

    return meta


def _strip_preamble(content: str) -> str:
    """Remove preamble lines that Pandoc can't handle."""
    # Remove \documentclass
    content = re.sub(r"\\documentclass(\[.*?\])?\{.*?\}\s*", "", content)

    # Remove \usepackage lines for problematic packages
    # Keep amsmath, amssymb, graphicx, hyperref (Pandoc handles these)
    problematic = [
        "icml2026", "neurips", "acl", "emnlp",  # conference styles
        "microtype", "placeins", "todonotes", "newfloat", "mdframed",
        "fancyhdr", "geometry", "titlesec", "titling",
        "subcaption", "caption", "float", "wrapfig",
        "algorithm", "algorithmic", "algpseudocode",
        "cleveref", "xcolor", "color", "colortbl",
        "tabularx", "multirow", "makecell",
        "enumitem", "paralist",
        "natbib", "biblatex",  # Pandoc handles bib its own way
    ]
    for pkg in problematic:
        content = re.sub(
            rf"\\usepackage(\[.*?\])?\{{{pkg}\}}\s*\n?", "", content
        )

    # Remove duplicate \usepackage for packages we keep
    seen_packages: set[str] = set()
    lines = content.split("\n")
    deduped = []
    for line in lines:
        m = re.match(r"\\usepackage(\[.*?\])?\{(\w+)\}", line.strip())
        if m:
            pkg = m.group(2)
            if pkg in seen_packages:
                continue
            seen_packages.add(pkg)
        deduped.append(line)
    content = "\n".join(deduped)

    # Remove layout commands
    layout_cmds = [
        r"\\setlength\{[^}]*\}\{[^}]*\}",
        r"\\captionsetup(\[.*?\])?\{[^}]*\}",
        r"\\setlist(\[.*?\])?\{[^}]*\}",
        r"\\pagestyle\{[^}]*\}",
        r"\\thispagestyle\{[^}]*\}",
    ]
    for pat in layout_cmds:
        content = re.sub(pat, "", content)

    # Remove theorem definitions (Pandoc doesn't need these)
    content = re.sub(r"\\theoremstyle\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\newtheorem(\*?)(\{[^}]*\})+\s*\n?", "", content)

    # Remove \DeclareFloatingEnvironment and \newmdenv blocks
    content = re.sub(
        r"\\DeclareFloatingEnvironment\[[\s\S]*?\]\{[^}]*\}\s*\n?", "", content
    )
    content = re.sub(
        r"\\newmdenv\[[\s\S]*?\]\{[^}]*\}\s*\n?", "", content
    )

    return content


def _strip_conference_commands(content: str, meta: PaperMetadata) -> str:
    """Remove conference-specific commands and environments."""

    # ICML commands
    content = re.sub(r"\\icmltitlerunning\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\icmlsetsymbol\{[^}]*\}\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\icmlkeywords\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\icmlaffiliation\{[^}]*\}\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\icmlcorrespondingauthor\{[^}]*\}\{[^}]*\}\s*\n?", "", content)
    content = re.sub(r"\\printAffiliationsAndNotice(\{[^}]*\})?\s*\n?", "", content)

    # Remove icmltitle (we already extracted it)
    content = re.sub(r"\\icmltitle\{[^}]*\}\s*", "", content)

    # Remove \begin{icmlauthorlist}...\end{icmlauthorlist}
    content = re.sub(
        r"\\begin\{icmlauthorlist\}[\s\S]*?\\end\{icmlauthorlist\}\s*",
        "",
        content,
    )

    # Remove \twocolumn[...] wrapper — extract the content inside
    # This is tricky because it can span multiple lines. We'll just remove it.
    content = re.sub(r"\\twocolumn\[", "", content)
    # Remove the matching ] — it's usually on its own line
    content = re.sub(r"^\]\s*$", "", content, flags=re.MULTILINE)

    # NeurIPS commands
    content = re.sub(r"\\neurips.*?\{[^}]*\}\s*\n?", "", content)

    return content


def _convert_environments(content: str) -> str:
    """Convert custom environments into Pandoc-friendly equivalents."""

    # subfigure environment → strip wrapper, keep \includegraphics inside
    content = re.sub(r"\\begin\{subfigure\}(?:\[[^\]]*\])?\{[^}]*\}", "", content)
    content = re.sub(r"\\end\{subfigure\}", "", content)

    # Remove \hfill between subfigures
    content = re.sub(r"\\hfill\b", "", content)

    # prompt environment → blockquote
    content = re.sub(
        r"\\begin\{prompt\}(\[.*?\])?",
        r"\\begin{quote}",
        content,
    )
    content = re.sub(r"\\end\{prompt\}", r"\\end{quote}", content)

    # mymessagebox → blockquote, extract frametitle as bold header
    def _replace_msgbox(m: re.Match) -> str:
        opts = m.group(1) or ""
        title_m = re.search(r"frametitle=([^,\]]+)", opts)
        prefix = ""
        if title_m:
            prefix = f"\\textbf{{{title_m.group(1).strip()}}}\n\n"
        return prefix + "\\begin{quote}"

    content = re.sub(
        r"\\begin\{mymessagebox\}(\[.*?\])?",
        _replace_msgbox,
        content,
    )
    content = re.sub(r"\\end\{mymessagebox\}", r"\\end{quote}", content)

    # algorithm environment → keep as-is but wrap algorithmic in verbatim-like
    # Pandoc can handle basic algorithm environments
    # Convert \begin{algorithmic} content to a more readable form
    content = re.sub(
        r"\\begin\{algorithm\}(\[.*?\])?",
        r"\\begin{quote}",
        content,
    )
    content = re.sub(r"\\end\{algorithm\}", r"\\end{quote}", content)

    # Algorithmic pseudo-code commands → plain text approximation
    content = re.sub(r"\\REQUIRE\b", r"\\textbf{Require:}", content)
    content = re.sub(r"\\ENSURE\b", r"\\textbf{Ensure:}", content)
    content = re.sub(r"\\STATE\b", r"", content)
    content = re.sub(r"\\IF\{([^}]*)\}", r"\\textbf{if} \\(\\1\\) \\textbf{then}", content)
    content = re.sub(r"\\ELSIF\{([^}]*)\}", r"\\textbf{else if} \\(\\1\\) \\textbf{then}", content)
    content = re.sub(r"\\ELSE\b", r"\\textbf{else}", content)
    content = re.sub(r"\\ENDIF\b", r"\\textbf{end if}", content)
    content = re.sub(r"\\FOR\{([^}]*)\}", r"\\textbf{for} \\(\\1\\) \\textbf{do}", content)
    content = re.sub(r"\\ENDFOR\b", r"\\textbf{end for}", content)
    content = re.sub(r"\\WHILE\{([^}]*)\}", r"\\textbf{while} \\(\\1\\) \\textbf{do}", content)
    content = re.sub(r"\\ENDWHILE\b", r"\\textbf{end while}", content)
    content = re.sub(r"\\RETURN\b", r"\\textbf{return}", content)
    content = re.sub(r"\\begin\{algorithmic\}(\[.*?\])?", "", content)
    content = re.sub(r"\\end\{algorithmic\}", "", content)

    # figure* → figure (no two-column in EPUB)
    content = content.replace(r"\begin{figure*}", r"\begin{figure}")
    content = content.replace(r"\end{figure*}", r"\end{figure}")
    content = content.replace(r"\begin{table*}", r"\begin{table}")
    content = content.replace(r"\end{table*}", r"\end{table}")

    # Theorem-like environments → bold labels
    for env in ["theorem", "lemma", "proposition", "corollary", "definition",
                "assumption", "remark"]:
        content = re.sub(
            rf"\\begin\{{{env}\}}(\[.*?\])?",
            rf"\\textbf{{{env.capitalize()}.}} ",
            content,
        )
        content = re.sub(rf"\\end\{{{env}\}}", "\n", content)

    return content


def _expand_simple_macros(content: str) -> str:
    """Expand simple \\newcommand definitions (no arguments)."""
    # Find \newcommand{\name}{replacement} with 0 args
    macros: dict[str, str] = {}
    for m in re.finditer(
        r"\\(?:new|renew)command\{(\\[a-zA-Z]+)\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
        content,
    ):
        cmd = m.group(1)
        replacement = m.group(2)
        # Only expand truly simple macros (no # arguments)
        if "#" not in replacement:
            macros[cmd] = replacement

    # Remove the definitions
    content = re.sub(
        r"\\(?:new|renew)command\{\\[a-zA-Z]+\}(?:\[\d+\])?\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*\n?",
        "",
        content,
    )

    # Expand the macros in the body
    for cmd, replacement in macros.items():
        # Escape the backslash for regex
        pattern = re.escape(cmd) + r"(?![a-zA-Z])"
        content = re.sub(pattern, replacement, content)

    # Remove known no-op / comment commands that take one argument
    # (like \davide{...}, \sasha{...}, \todo{...})
    content = re.sub(r"\\(?:todo|davide|sasha|joel|logan|wil|vezhnick)\{[^}]*\}", "", content)
    content = re.sub(r"\\(?:todo|davide|sasha|joel|logan|wil|vezhnick)\[[^\]]*\]\{[^}]*\}", "", content)

    return content


def _fix_image_paths(content: str, work_dir: Path) -> str:
    """Ensure image paths are correct and extensions are present."""

    def _fix_path(m: re.Match) -> str:
        opts = m.group(1) or ""
        path_str = m.group(2)

        # Add extension if missing
        img_path = Path(path_str)
        if not img_path.suffix:
            for ext in [".png", ".jpg", ".jpeg", ".pdf", ".svg"]:
                if (work_dir / (path_str + ext)).exists():
                    path_str = path_str + ext
                    break

        # Simplify width options for Pandoc
        opts = re.sub(r"width\s*=\s*\\(?:line|text|column)width", "width=\\\\textwidth", opts)
        opts = re.sub(r"width\s*=\s*[\d.]+\\(?:line|text|column)width", "width=\\\\textwidth", opts)

        if opts:
            return f"\\includegraphics[{opts}]{{{path_str}}}"
        return f"\\includegraphics{{{path_str}}}"

    content = re.sub(
        r"\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}",
        _fix_path,
        content,
    )
    return content


def _prepare_bibliography(content: str, work_dir: Path) -> str:
    """Ensure bibliography is ready for Pandoc's --citeproc."""
    # Pandoc's citeproc uses @key citations, but it also understands
    # \cite, \citep, \citet from natbib — we just need to make sure
    # the bib file is findable.

    # Find the bibliography file name
    m = re.search(r"\\bibliography\{([^}]+)\}", content)
    if m:
        bib_name = m.group(1)
        if not bib_name.endswith(".bib"):
            bib_name += ".bib"
        # Verify it exists
        if not (work_dir / bib_name).exists():
            # Try to find any .bib file
            bib_files = list(work_dir.glob("*.bib"))
            if bib_files:
                bib_name = bib_files[0].name

    # Remove \bibliographystyle{} — not needed for citeproc
    content = re.sub(r"\\bibliographystyle\{[^}]*\}\s*\n?", "", content)

    return content


def _final_cleanup(content: str) -> str:
    """Final pass: remove remaining problematic commands."""
    # Remove float specifiers [ht], [htp], [!ht], etc.
    content = re.sub(
        r"(\\begin\{(?:figure|table)\})\s*\[[^\]]*\]",
        r"\1",
        content,
    )

    # Remove spacing/layout commands
    removals = [
        r"\\vskip\s+[\d.]+(?:in|pt|em|cm|mm)\s*",
        r"\\vspace\*?\{[^}]*\}\s*",
        r"\\hspace\*?\{[^}]*\}\s*",
        r"\\FloatBarrier\s*",
        r"\\clearpage\s*",
        r"\\newpage\s*",
        r"\\noindent\s*",
        r"\\centering\s*",
        r"\\raggedright\s*",
        r"\\small\b\s*",
        r"\\footnotesize\b\s*",
        r"\\scriptsize\b\s*",
        r"\\tiny\b\s*",
        r"\\large\b\s*",
        r"\\Large\b\s*",
        r"\\LARGE\b\s*",
        r"\\huge\b\s*",
        r"\\Huge\b\s*",
        r"\\normalsize\b\s*",
        r"\\fontfamily\{[^}]*\}\\selectfont\s*",
        r"\\selectfont\s*",
    ]
    for pat in removals:
        content = re.sub(pat, "", content)

    # Remove \cref → \ref (Pandoc doesn't know cleveref)
    content = re.sub(r"\\[Cc]ref\{", r"\\ref{", content)

    # Remove empty lines clusters (more than 2 consecutive)
    content = re.sub(r"\n{3,}", "\n\n", content)

    return content


def _rebuild_document(content: str, meta: PaperMetadata) -> str:
    """Rebuild a clean LaTeX document structure for Pandoc."""
    # Strip everything outside \begin{document}...\end{document}
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", content, re.DOTALL)
    if m:
        body = m.group(1)
    else:
        body = content

    # Build a clean document
    preamble = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{booktabs}
"""

    # Add title/author metadata
    if meta.title:
        preamble += f"\\title{{{meta.title}}}\n"
    if meta.authors:
        author_str = " \\and ".join(meta.authors)
        preamble += f"\\author{{{author_str}}}\n"

    doc = preamble + "\n\\begin{document}\n"
    if meta.title:
        doc += "\\maketitle\n"
    doc += body
    doc += "\n\\end{document}\n"

    return doc


def _clean_tex(text: str) -> str:
    """Remove LaTeX commands from a string, leaving plain text."""
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\textit\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
