from matplotlib.figure import Figure

from synthetic_pdf_bench.generators import formulas


def test_two_workers_rendering_the_same_formula_do_not_clobber_each_other(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(formulas, "gettempdir", lambda: str(tmp_path))  # an empty cache, whatever earlier runs left in /tmp
    latex = r"\alpha_{7319} + \beta_{4027}"
    real_savefig = Figure.savefig
    nested = []

    def savefig_then_let_another_worker_finish(self, target, *args, **kwargs):
        real_savefig(self, target, *args, **kwargs)
        if not nested:  # the other worker renders the same formula while this one is between savefig and rename
            nested.append(None)
            nested[0] = formulas.render_formula(latex, 12)

    monkeypatch.setattr(Figure, "savefig", savefig_then_let_another_worker_finish)
    path = formulas.render_formula(latex, 12)  # raised FileNotFoundError when both used one temp name

    assert nested and path == nested[0] and path.exists()
