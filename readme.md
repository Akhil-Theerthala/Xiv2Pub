
# `Xiv2Pub` 
## Convert arXiv LaTeX papers to readable EPUBs
 
### Prerequisites section
- Python ≥ 3.10
- Pandoc — `brew install pandoc`
- Python packages — `pip install requests ebooklib`
 
### Usage section
```bash
# arXiv URL
python -m tex2epub https://arxiv.org/abs/2602.03545
 
# Bare arXiv ID
python -m tex2epub 2602.03545
 
# Local .tar.gz
python -m tex2epub arXiv-2602.03545v1.tar.gz
 
# Custom output path
python -m tex2epub 2602.03545 -o my-paper.epub
```
 

### How it works (brief prose + numbered pipeline)
1. **Download** — fetches `arxiv.org/src/{id}` as `.tar.gz`
2. **Extract** — unpacks archive, finds main `.tex` via `00README.json`
3. **Preprocess** — strips conference macros, resolves `\input`, normalises environments
4. **Convert** — Pandoc with `--mathml --citeproc --epub3`
5. **Post-process** — embeds Latin Modern fonts, injects CSS, links citations
 
### Supported templates
ICML, NeurIPS, ACL/EMNLP, and plain `article` class. Any paper with LaTeX source on arXiv.
 
### Limitations section
- Papers with only a PDF source (no LaTeX) cannot be converted
- Heavy custom packages may produce partial output
- Optimised for Apple Books; Kindle untested


---
### AI USAGE
Used Claude Code powered by Sonnet to assist in developing this project.
