# DocLayNet and Docling research spike

Date: 2026-11-04. Read-only desk research. Everything below is from the cited sources unless marked **(unverified)** (not confirmed in a source I could open) or **(estimate)** (my own arithmetic or judgement). We do not repeat the known baselines (heron 0.705, YOLOX-Tiny synthetic-only 0.021); see `docs/layout-baselines.md`.

Sources used:

- [DocLayNet paper, arXiv 2206.01062](https://arxiv.org/abs/2206.01062) (KDD 2022)
- [DocLayNet Labeling Guide](https://github.com/DS4SD/DocLayNet/blob/main/assets/DocLayNet_Labeling_Guide_Public.pdf) (IBM, Aug 2022)
- [DocLayNet-v1.2 card](https://huggingface.co/datasets/docling-project/DocLayNet-v1.2), [DocLayNet card](https://huggingface.co/datasets/docling-project/DocLayNet)
- [Docling technical report, arXiv 2408.09869](https://arxiv.org/abs/2408.09869) and [Docling v2 report, arXiv 2501.17887](https://arxiv.org/abs/2501.17887)
- [Advanced Layout Analysis Models for Docling (heron/egret), arXiv 2509.11720](https://arxiv.org/abs/2509.11720); [heron model card](https://huggingface.co/docling-project/docling-layout-heron)
- [TableFormer, arXiv 2203.01017](https://arxiv.org/abs/2203.01017); [docling-ibm-models](https://github.com/docling-project/docling-ibm-models); [docling-models card](https://huggingface.co/ds4sd/docling-models)
- [Docling model catalog](https://docling-project.github.io/docling/usage/model_catalog/); [granite-docling-258M](https://huggingface.co/ibm-granite/granite-docling-258M)
- [DocLayout-YOLO, arXiv 2410.12628](https://arxiv.org/abs/2410.12628) and [its repo](https://github.com/opendatalab/DocLayout-YOLO)

## 1. Summary and top recommendations

DocLayNet is 80,863 human-annotated pages from six categories, deliberately chosen for layout variety (free-style annual reports, manuals) rather than template uniformity. Its labels follow a "how does it look, not what does it mean" rule with strict geometric conventions (hanging-indent list items, one box per footnote, footers vs footnotes, run-in bold is Text). Annotators disagree most on Title, Picture, Table and Caption, so per-class ceilings are low for those.

Docling's layout model is an RT-DETRv2 detector (heron, 42.9M params, Apache-2.0) trained at 640x640 on about 150k pages: a cleaned DocLayNet subset, WordScape, and proprietary pages. No synthetic layout data is mentioned for it. Synthetic data is used by Docling's other models (SynthTabNet for TableFormer; synthetic code/formula/chart sets for Granite-Docling). The only layout-detection evidence for synthetic data helping is DocLayout-YOLO: pre-training on DocSynth-300K and then fine-tuning on full real DocLayNet gave +2.0 mAP (77.7 to 79.7). I found no source showing a synthetic-only layout detector transferring well to real pages.

Recommendations, ordered by expected impact:

1. **Fix class coverage first.** Generate list-item, footnote, formula, page-header, page-footer and caption boxes following the DocLayNet guideline. Three of 11 classes are currently unlearnable; list-item alone is 17% of real boxes.
2. **Add real data.** Fine-tune on real DocLayNet train (CDLA-Permissive-1.0) and treat synthetic pages as pre-training or an additive mix. This is the single largest lever per the DocLayout-YOLO and Docling evidence; no source supports synthetic-only competitiveness.
3. **Vary layout templates and styles** (columns, page sizes, fonts, colour bands, sidebars, financial/manual/law/patent/tender look-alikes), not just topics. Add non-history content and some German/French/Japanese.
4. **Match DocLayNet box conventions exactly** (tight text-cell boxes, tables and pictures exclude captions, per-item list boxes, paragraphs that continue across columns are separate boxes).
5. **Match the class and density distribution** (about 12 boxes per page; text 46%, list-item 17%, section-header 13%, then footers/headers 6-7% and 5%) and include title pages.
6. **Model and input size.** For the budget, a COCO-pretrained small detector (YOLOX-S/M or D-FINE-M / RT-DETRv2-R50 if training time fits) at 640-1024 px. Heron's own setting is 640 px; DocLayNet baselines used 1025 px.
7. **Augmentation** like heron's (photometric distortion, zoom-out, resize, flips), kept mild; our scan degradations are low priority because DocLayNet excludes scans.
8. **Evaluation** on document-level splits, per-class AP50-95 against the human agreement ranges, same 500-page sample, and report real-only and mixed runs separately.

Realistic expectation under Apache-2.0 plus about $5: a synthetic-only model will stay far below heron. A real-data fine-tune of a small detector is the achievable route to a competitive number. The DocLayNet paper's fully trained 2022 baselines are 72.4 to 76.8 mAP50-95 on the test set (below), which is the order of magnitude to target; reaching it with a few GPU-hours is **(estimate)** optimistic, so plan for something lower and measure.

## 2. DocLayNet findings

### 2.1 Construction

- **Size.** 80,863 unique pages; 7,059 carry two annotations and 1,591 three, so 91,104 annotation instances (paper section 3). Boxes: 1,107,470 in Table 1, so about 12.2 per annotation instance **(estimate, my division)**.
- **Sources and categories.** Six categories: Financial Reports, Manuals, Scientific Articles, Laws & Regulations, Patents, Government Tenders. Sources include arXiv, government offices, company websites, and data directories for financial reports and patents (annualreports.com for free-style annual reports; SEC filings for formal ones). Financial Reports and Manuals contain many free-style layouts "to obtain maximum variability"; the other four mix independent providers. Fig. 2 shares: roughly 32% / 21% / 17% / 16% / 8% / 6%; Financial (32%) and Tenders (6%) are clear, the assignment of 21/17/16 to Manuals/Scientific/Laws is read from a garbled figure **(unverified)**. Exact pages per category are not in the paper or cards I opened.
- **Inclusion rules.** Free to use; mostly programmatic PDFs (scans excluded where possible because skew breaks rectangular boxes); medium to large documents (>10 pages) with technical content dense in tables, figures, captions. Excluded: receipts, invoices, handwriting, text in the wild.
- **Page selection.** Subsampled to balance categories; always include each document's title page and bias the rest toward pages with figures or tables (estimated with a PubLayNet detector).
- **Language.** Not controlled: about 95% English, German 2.5%, French 1.0%, Japanese 1.0%.
- **Page size.** Images are resized to 1025x1025 PNG for COCO. The v1.2 card keeps `original_width/height` and the PDF per page; I did not find an original page-size distribution in the sources **(unverified)**. The paper's Fig. 6 shows a Chinese patent with label confusion, so some CJK exists beyond the stated 1% Japanese.
- **Splits.** Fixed splits made on whole-document boundaries; rare labels balanced across train/test. v1.2 viewer counts: 69.4k train / 6.49k val / 5k test. Page-wise random splitting inflated mAP by about 10 points (Table 4: 72 vs 84 for 11 classes).
- **Tooling and process.** Four phases: data selection; label/guideline design; training of annotators; production. 40 annotators were trained and examined over 12 weeks (8 failed), then 32 annotated about 80k pages in roughly 3 months. Exam used 974 reference pages annotated by a core-team member. The tool (IBM Corpus Conversion Service) overlays parsed PDF text cells; a user-drawn rectangle snaps to the enclosed text cells for all text classes, while Table and Picture are drawn tight by hand (include gridlines, legends, arrows). Only non-overlapping, upright rectangles; annotators cannot see each other's work; pages that cannot be annotated validly are rejected and excluded. About 20-60 s per page.

### 2.2 Class definitions (Labeling Guide, 100+ pages; key rules)

Primary criterion: "How does it look?" not "What is the meaning?". Annotation is page by page without neighbours.

| Class | Rule |
|---|---|
| Text | Regular paragraphs and anything fitting no special class: authors, affiliations, abstracts, sidebars, quotes, theorems/proofs, code and algorithms, multi-line addresses/verses. Bold or italic run-in start of a paragraph stays Text. Text around a centered formula is two separate Text boxes. A paragraph continuing at top of a page or column is its own box. |
| List-item | One box per item, including the bullet/number. Key rule: hanging shape (continuation lines indented more than the first). One-line items count if neighbours hang, or if the list has clear bullets/numbers. Numbered multi-line section headers are not lists. No bullet is required. |
| Footnote | Usually smaller text at page bottom, below a horizontal line, with a superscript identifier referenced on the same page; does not repeat on every page. Several footnotes on a page are separate boxes. Not a page-footer. |
| Formula | Display math on its own line. The formula number is part of the box. Inline math is not a Formula. Successive lines are one box if linked (shared number, aligned `=`/`+`), else separate. |
| Page-header / Page-footer | Repeating elements at top/bottom outside the text flow: page number (even if alone), date, running title/section, confidentiality note; sideways text counts. Widely separated parts become separate boxes. A footer that sits close to the body but repeats on every page is still Page-footer. |
| Caption | Text introducing a picture or table, outside the figure/table, usually one paragraph. Exactly one Picture or Table per caption. |
| Picture | Graphic, plot, photo, logo, including legends and in-figure text; sub-pictures under a single caption are one box; separate captions mean separate pictures. Forms with checkboxes/blanks usually Picture unless a clear grid. |
| Table | Text arranged in a grid where the arrangement matters; with or without gridlines; includes spanning headers and column totals; excludes the caption; tight box. |
| Section-header | Any heading except the overall document title; visible emphasis (size, bold, caps); usually short, not full sentences; each hierarchy level its own box. Run-in emphasis is not a header. |
| Title | Overall document title only, almost exclusively on the first page, large font; a repeated title on later pages is Text. Title pages are annotated as a separate batch. |
| None | Initial state for empty/invisible cells; leftover cells should be rare. |

Part II of the guide has per-category special cases (US/British laws title pages and tables of contents, etc.).

### 2.3 Class statistics (paper Table 1)

| Class | Boxes | % of all | Human agreement mAP50-95 (all) | Worst category range |
|---|---|---|---|---|
| Text | 510,377 | 46.1 | 84-86 | Patents 71-79 |
| List-item | 185,660 | 16.8 | 87-88 | Financial 74-83 |
| Section-header | 142,884 | 12.9 | 83-84 | Patents 69-73 |
| Page-footer | 70,878 | 6.4 | 93-94 | Financial 88-90 |
| Page-header | 58,022 | 5.2 | 85-89 | Financial 66-76 |
| Picture | 45,976 | 4.2 | 69-71 | Financial 56-59 |
| Table | 34,733 | 3.1 | 77-81 | Laws 58-80 |
| Formula | 25,027 | 2.3 | 83-85 | n/a outside Sci/Law |
| Caption | 22,524 | 2.0 | 84-89 | Financial 40-61 |
| Footnote | 6,318 | 0.6 | 83-91 | Scientific 62-88 |
| Title | 5,071 | 0.5 | 60-72 | Tenders 24-56, Financial 24-63 |

Percentages are computed from counts **(estimate)**. Overall agreement is 82-83 mAP; Footnote and Formula appear only in some categories (Footnote n/a in Financial/Patents; Formula only Sci/Law in agreement data).

### 2.4 Baselines and ablations in the paper

- Test mAP50-95 (all classes), 1025x1025, COCO-pretrained: Mask R-CNN R50 72.4, R101 73.5; Faster R-CNN R101 73.4; YOLOv5x6 76.8. Per class (YOLOv5x6): Text 88.1, Table 86.3, List-item 86.2, Title 82.7, Caption 77.7, Footnote 77.2, Picture 77.1, Section-header 74.6, Page-header 67.9, Formula 66.2, Page-footer 61.1. Models land 6-10 points below human agreement; YOLO beats humans on Text, Table, Picture.
- Learning curve: flattens around 80% of the training set (about 1% error bar); the authors say more similar data will not help, but consistency, augmentation and new categories/styles would.
- Label set: merging classes barely changes the remaining per-class scores; dropping header/footer raises the macro-average by about 5.
- Cross-dataset robustness: the PubLayNet-trained model gets 93 total on its own test set but 30 on DocLayNet; the DocLayNet-trained model gets 78 on its own and 59 on PubLayNet, i.e. much smaller drops. Supports the claim that layout variety, not size, drives robustness. Data from templated sources (PubMed/arXiv-style) generalises badly, which is exactly the risk for single-topic synthetic pages.
- "Layout variety" statement: PubLayNet/DocBank are "severely lacking in layout variability" because they come from publisher templates; technical manuals, annual reports, legal text and tenders have very different, partly unique layouts.

### 2.5 What a realistic synthetic set needs (ordered by expected impact)

1. All 11 classes present with the guideline geometry (list-item hanging shape; footnote below a rule; formula with its number inside the box; header/footer incl. page-number-only; caption paired 1:1 with picture/table; title only on first page).
2. Real-looking class mix and density (table above), with title pages and table/figure-biased page selection.
3. Template diversity: 1-3 columns, margins, page sizes and orientation, font families and sizes, coloured backgrounds and bands, sidebars, multi-level headings, free-style annual-report pages, dense manual pages, numbered nested legal clauses, two-column patents.
4. Table variety: gridlines, horizontal-only, none; spanning headers; totals; dense numeric financial tables (Financial has the lowest human agreement on tables, captions and headers).
5. Picture variety: charts, photos, logos, multi-panel figures under one caption, small icons.
6. Content variety: many topics, number-heavy text, short lines (addresses, verse), code/algorithm blocks as Text, some non-English.
7. Annotation conventions replicated in export (tight boxes, non-overlapping, no caption in table/picture box, continued paragraphs as separate boxes).
8. Document-level train/val/test splits by template (not page) to avoid the ~10-point inflation.
9. Light photometric variation; scans are out of DocLayNet's scope.

## 3. Docling findings

### 3.1 Pipeline

Linear pipeline per document (2408.09869): PDF backend (docling-parse, a custom qpdf-based parser; pypdfium alternative) extracts text cells with coordinates and renders page bitmaps; per page models run: optional OCR, layout analysis, table structure; then aggregation and post-processing (language detection, reading-order correction, figure-caption matching, metadata labelling) into a `DoclingDocument` serialised to JSON/Markdown.

| Stage | Model | Notes and source |
|---|---|---|
| Layout | heron (default since Docling v2.50), egret-m/l/x, heron-101; older "docling-layout-v2" (RT-DETRv1 R50) is legacy | See 3.2 |
| Table structure | TableFormer (accurate/fast) on crops of detected tables; predictions matched back to PDF cells instead of re-OCR | ResNet-18 backbone, 2 encoder + 4 decoder layers (TableFormer paper); weights on `ds4sd/docling-models` (card tags cdla-permissive-2.0 and apache-2.0; which applies to what is not stated); code MIT. Trained on PubTabNet (509k tables), FinTabNet (112k), TableBank (145k, no cell boxes) per the TableFormer paper; docling-ibm-models README lists PubTabNet, FinTabNet, TableBank. SynthTabNet (600k synthetic tables, four 150k sets, browser-rendered) was introduced in the TableFormer paper "to fix an imbalance"; whether Docling's released weights include it is **(unverified)**. TEDS 95.4 simple / 90.1 complex / 93.6 all on the model card. |
| OCR | EasyOCR default originally; Tesseract, RapidOCR, macOS Vision, SuryaOCR options | Optional; the biggest CPU cost (about 13 s/page x86, 1.6 s on L4 GPU in the v2 report). Fed at 216 dpi vs layout at 72 dpi (v1 report). |
| Reading order | Rule-based post-processing in assembly; algorithm not detailed in the reports **(details unverified)** | Not a learned model in the reports I read. |
| Assembly | docling-core `DoclingDocument` | Matches captions to figures/tables, labels title/authors/references. |
| Picture classifier | DocumentFigureClassifier-v2.5 (ViT) | Catalog only; training data not stated. |
| Code and formula | CodeFormulaV2; also Granite-Docling-258M | Catalog; CodeFormulaV2 training data not stated **(unverified)**. |
| VLM alternative | Granite-Docling-258M (Apache-2.0; Idefics3 with SigLIP2-base-512 encoder + Granite 165M LM; trained on public data plus SynthCodeNet, SynthFormulaNet, SynthChartNet and DoclingMatix) and SmolDocling-256M | Outputs DocTags; Japanese/Arabic/Chinese experimental. |

Licences: Docling code MIT; heron Apache-2.0; Granite-Docling Apache-2.0; DocLayNet data CDLA-Permissive-1.0.

### 3.2 Layout models (heron report, 2509.11720)

- **Training data.** About 150k single-page documents, 2.3M layout elements in train: a "canonical-DocLayNet" (original 80,863 pages filtered with a small RT-DETRv2 filter at confidence 0.3, dropping 32% of samples, leaving 22,101 train / 2,804 val / 1,574 test), public WordScape (Word documents from Common Crawl, with table annotations removed because "Table" often covered full-page forms), and proprietary DocLayNet-v2 (test split 7,613 pages). No synthetic layout data is mentioned. Page images are 150 dpi PNG, resized to 640x640.
- **Label set.** 17 classes: the 11 DocLayNet classes plus Code, Document Index, Form, Key-Value Region, Checkbox-Selected, Checkbox-Unselected. These six were absent in original DocLayNet, so the authors filtered pages likely to contain them.
- **Models** (mAP on canonical DocLayNet, COCO tools; latency A100, batch 200):

| Model | Backbone | Params | mAP | s/img |
|---|---|---|---|---|
| old-docling (RT-DETRv1) | r50vd | 42.9M | 0.541 | 0.028 |
| heron | RT-DETRv2 r50vd | 42.9M | 0.776 | 0.031 |
| heron-101 | RT-DETRv2 r101vd | 76.7M | 0.780 | 0.028 |
| egret-m | D-FINE m | 19.5M | 0.765 | 0.024 |
| egret-l | D-FINE l | 31.2M | 0.747 | 0.026 |
| egret-x | D-FINE x | 62.7M | 0.753 | 0.031 |

  The 0.705 we measured for heron on a raw 500-page test sample is not comparable to these (different pages, canonical filtering, 11-class mapping).
- **Training recipe.** RT-DETRv2: 72 epochs, lr 1e-4; D-FINE: 80-132 epochs, lr 2e-4 to 2.5e-4; AdamW, weight decay about 1e-4; augmentation: photometric distortion, zoom-out, horizontal flip, resize; backbones pre-trained (on what is not stated); batch size and hardware not stated. Boosts attributed to cleaner/canonical data (+7.5 to 8.4% mAP on canonical vs original DocLayNet) and larger training mix.
- **Post-processing.** Per-label score floors, snapping boxes to PDF cells, removing overlapping clusters, dropping pictures covering over 90% of the page, nesting children inside Form/Key-Value/Table/Index, rule-based winner among overlaps.
- **Failure modes and caveats (from the report).** Post-processing and score filtering reduce COCO mAP by more than 10% yet look better visually; the authors conclude mAP may be a poor metric for layout because ambiguous layouts have several valid answers. On the proprietary DocLayNet-v2 test set heron scores 0.36 with docling-eval (0.61 on DocLayNet) at score >0.5, i.e. much harder pages are far from solved. Original DocLayNet labels conflict with the 17-class taxonomy; WordScape table labels are noisy. YOLO models were excluded for licensing reasons.
- **Versus earlier docling layout models.** Earlier: RT-DETRv1 R50 trained on DocLayNet plus proprietary data, 72 dpi input (v1 report). Heron: same parameter count (42.9M), RT-DETRv2, larger/cleaner data, 17 classes, post-processing; 0.541 to 0.776 on the canonical test set.

### 3.3 Evidence on synthetic and pre-training data for layout

- **DocLayout-YOLO / DocSynth-300K.** Synthetic pages made by a Mesh-candidate BestFit bin-packing layout algorithm. Pre-training then fine-tuning gives, on DocLayNet at 1120 px: mAP 77.7 to 79.7 (AP50 93.0 to 93.4); on D4LA: 69.8 to 70.3. So gains are real but modest and come after full real-data fine-tuning. Code is AGPL-3.0; weights licence not confirmed **(unverified)**, so use the idea, not the checkpoint, under our Apache-2.0 constraint.
- **TableFormer / SynthTabNet.** The authors argue lack of training diversity "damages the ability of the models to generalize" and built 600k synthetic tables with controllable structure and style; TEDS 96.7 on SynthTabNet itself. Evidence for synthetic tables as an addition to real sets, not a replacement.
- **Granite-Docling.** Synthetic sets are used for specific skills (code, formulas, charts), with real pages (DoclingMatix) for page structure.
- **SynthDoG (Donut) and other synthetic layout work.** Not opened in this spike; SynthDoG targets text reading pre-training, not box layouts **(unverified, from memory)**.
- **DocLayNet itself** shows the cost of template-uniform data (PubLayNet 93 to 30 cross-dataset). Our 0.021 result is consistent with that.

## 4. What our pipeline should do (reasoned from the above)

- **Model.** COCO-pretrained YOLOX (Apache-2.0; already used) is the cheapest path; heron's RT-DETRv2-R50 (42.9M) or D-FINE-m (19.5M, 0.765 in the report) are the modern Apache-2.0 targets **(D-FINE licence unverified)**. Avoid ultralytics/DocLayout-YOLO code (AGPL). Heron trained 72 epochs on about 22k+ pages; on an RTX A4000 at $0.17/h our YOLOX-Tiny 5,000 steps cost about $0.10, so about $5 buys roughly 30 A4000-hours **(estimate)**. A full RT-DETRv2 recipe may not fit; fewer epochs or a smaller model is realistic.
- **Resolution.** 640 minimum (heron). DocLayNet baselines used 1025, DocLayout-YOLO 1120. Small classes (footnote, page-number headers, formulas) likely benefit from 800-1024 **(estimate)**; test as one controlled run.
- **Mix.** Real DocLayNet train (a few thousand pages is enough to test) plus synthetic; compare real-only, synthetic-then-real, and mixed. The paper's learning curve says real data saturates near the full 69k pages, so a subset trades accuracy for cost.
- **Schedule.** Our own result shows more steps on synthetic-only data add nothing (0.060 at 100 steps vs 0.062 at 5,000). Spend steps on data coverage, not length.
- **Evaluation.** Keep the 500-page real sample; add per-class table against the human agreement ranges (Title, Picture, Page-footer ceilings are low); do not use random page splits.

## 5. Recommendation to repo change map

| # | Change | Where | Effort |
|---|---|---|---|
| 1 | Emit list-item (hanging indent, one box per item, bullet/number inside) | `generators/recipes.py`, `layout/flow_layout.py`, `schema/blocks.py`, `BLOCK_TYPE_TO_CATEGORY` in `export/coco.py` | M (2-3 days) |
| 2 | Footnotes (rule + small text + superscript refs, bottom of page) and page-header/footer variants (page number only, running title, sideways) | `layout/flow_layout.py`, renderer, export | M |
| 3 | Display formulas with number inside the box (LaTeX or math-font rendering) | `render`, `schema`, export | M-L (rendering dependency) |
| 4 | Caption 1:1 with picture/table, above or below; title only on page 1; run-in bold stays Text | generators + export checks; add to `quality.py` | S-M |
| 5 | Template library: columns, page sizes, fonts, colour bands, sidebars, category look-alikes (annual report, manual, law, patent, tender) | `generators/`, recipes (new canonical recipes with non-history content) | L |
| 6 | Content diversity: other domains, number-heavy tables, a few non-English recipes | `data/recipes/canonical/`, handbook docs | M |
| 7 | Box-convention audit vs the guideline (tight boxes, no captions inside table/picture, continued paragraphs separate) | export tests (seeded) | S |
| 8 | Class/density matching report: compare per-class counts and boxes per page against Table 1 | `quality.py` or a script | S |
| 9 | Training on mixed real+synthetic: accept several train JSONs with sampling weights; add real train sample prep | `scripts/train_layout.py`, `scripts/prepare_doclaynet.py` | S-M |
| 10 | Input size and augmentation options (size already exists; add zoom-out, photometric distortion) | `scripts/train_layout.py` | S |
| 11 | Optional model upgrade (RT-DETRv2 or D-FINE) after a CPU rehearsal | `scripts/train_layout.py`, `scripts/jobs/` | M-L |
| 12 | Evaluation: per-class table vs human agreement; document-level splits for any real data; record in docs | `scripts/eval_docling_layout.py`, `docs/layout-baselines.md` | S |

Effort key: S under a day, M 1-3 days, L about a week **(estimates)**.

## 6. Open items

- Confirm whether using DocLayNet-train in our training is acceptable for the project's goals (licence CDLA-Permissive-1.0 permits use; legal reading not checked).
- Verify D-FINE and any chosen detector's licence and weight terms before adopting.
- Read the TableFormer weights licence per file on `ds4sd/docling-models`.
- Reading-order algorithm and CodeFormula/figure-classifier training data are not documented in the reports I read.
- Page-size distribution of DocLayNet originals is not in the sources opened; it can be computed from the v1.2 `metadata` fields.
