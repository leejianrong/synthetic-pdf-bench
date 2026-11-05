"""Baseline parser: pypdf's text extraction, page by page. Usage: pypdf_text.py PDF OUT_DIR"""
import sys
from pathlib import Path

from pypdf import PdfReader

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
pages = [(page.extract_text() or "").strip() for page in PdfReader(pdf).pages]
(out / "document.md").write_text("\n\n".join(p for p in pages if p) + "\n", encoding="utf-8")
