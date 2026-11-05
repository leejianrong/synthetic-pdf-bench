"""Baseline parser: PyMuPDF's plain text layer, one paragraph per text block. Usage: pymupdf_text.py PDF OUT_DIR"""
import sys
from pathlib import Path

import pymupdf

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
blocks = [b[4].strip() for page in pymupdf.open(pdf) for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
(out / "document.md").write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
