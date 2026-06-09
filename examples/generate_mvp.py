from pathlib import Path

from synthetic_pdf_bench.cli.generate import generate


if __name__ == "__main__":
    generate(Path("output/synthetic_000001"), seed=123)
