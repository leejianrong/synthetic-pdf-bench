"""Docling (IBM, MIT): PDF to Markdown with its default pipeline on CPU. Usage: docling_md.py PDF OUT_DIR"""
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter

pdf, out = Path(sys.argv[1]), Path(sys.argv[2])
document = DocumentConverter().convert(pdf).document
(out / "document.md").write_text(document.export_to_markdown(), encoding="utf-8")
