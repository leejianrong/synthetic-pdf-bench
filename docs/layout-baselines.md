# Layout baselines on real pages

Per-class AP and mAP on a fixed sample of real DocLayNet pages. Every row names its hardware and page list, and numbers from different machines are not compared.

## Page sets

- **DocLayNet test sample:** 500 pages from DocLayNet-v1.2 `test` (CDLA-Permissive-1.0), seed 0, drawn evenly from all 6 test shards by `scripts/prepare_doclaynet.py`. The page list is `pages_test.json` (sha256 prefix `69cd55fcdaa42184`). Categories: 176 financial reports, 87 scientific articles, 81 manuals, 76 laws, 48 patents, 32 government tenders. Shards are sorted by category, which is why the sample spans every shard.

## Docling layout model (baseline)

`docling-project/docling-layout-heron` (RT-DETRv2, Apache-2.0), revision `8f39ad3c0b4c`, run by `scripts/eval_docling_layout.py` with score floor 0.01, on an Intel i7-13620H CPU (614 s for 500 pages).

| | mAP50-95 | mAP50 |
|---|---|---|
| Docling heron, DocLayNet test sample | **0.705** | **0.883** |

Per-class AP50-95: caption 0.754, footnote 0.705, formula 0.692, list-item 0.781, page-footer 0.551, page-header 0.723, picture 0.826, section-header 0.641, table 0.862, text 0.843, title 0.376.

How the 17 heron classes map to DocLayNet's 11: labels 0-10 are DocLayNet's own. Document Index counts as table and Code as text. Checkbox-Selected, Checkbox-Unselected, Form and Key-Value Region have no DocLayNet equivalent, so those predictions are dropped; at score 0.6 that was 24 Key-Value Region and 2 Form predictions across the 500 pages.

**Read this as an upper reference.** Docling was trained on DocLayNet train, and these pages come from the same distribution, so this is its home set. A model trained on synthetic data is not expected to match it.

## YOLOX-Tiny, synthetic only (SYN-6)

COCO-pretrained YOLOX-Tiny (rtod `3751bc7`), 5,000 steps, batch 16, 640 px, lr 0.005, trained on 1,675 synthetic pages (100 documents from the 7 canonical recipes, variants `random` and `standard`, split by recipe, seed 0, repo `c75414c`). Run on a community NVIDIA RTX A4000 (RunPod, $0.17/hr): 1,671 s training, 28 s evaluation, about $0.10.

| Pages | mAP50-95 | mAP50 |
|---|---|---|
| Synthetic validation (50 pages, unseen recipes) | 0.986 | 1.000 |
| DocLayNet validation (50 pages) | 0.062 | 0.138 |
| DocLayNet test sample (500 pages) | 0.021 | 0.058 |

Per-class AP50-95 on the test sample: text 0.095, table 0.048, picture 0.044, title 0.035, caption 0.004, section-header 0.003, page-footer 0.002, footnote, formula, list-item and page-header 0.000.

**Reading it.** The model solves its own distribution and barely transfers. Real validation scored 0.060 after 100 steps and 0.062 after 5,000, so more steps on the same synthetic pages add nothing. Two causes are visible. First, the synthetic pages contain no `list-item`, `footnote` or `formula` boxes at all (counted on a 14-document regeneration of the same recipes and variants, 278 pages), so three of the 11 classes cannot be learned; list-items alone are 1,083 boxes in the real train sample. Second, the recipes are all Southeast Asia history, so the content and page furniture are narrow. More steps are not the next move; covering the missing classes, more varied pages and mixing in real ones are (SYN-7, SYN-8).

## Sim-to-real comparison (SYN-7)

One pod, one seed per arm, a community NVIDIA RTX 3090 (RunPod, $0.22/hr, 0.95 h, $0.21 in all), repo `7344040`, rtod `3751bc7`. All arms start from COCO weights (except finetune), use batch 16, 640 px, the same 11-class head, and are scored on the same 500 DocLayNet test pages as Docling. Synthetic data is 150 documents (2,851 train pages, variants `random`, `standard` and `structured`, so all 11 classes occur). Real data is 2,000 DocLayNet train pages (seed 0, 24 evenly spaced shards; 671 financial, 404 manuals, 333 scientific, 309 laws, 154 patents, 129 tenders). The arms were fixed before the run, and the test pages were scored once per arm.

| Arm | Steps | Train pages | Test mAP50-95 | Test mAP50 | Real val (50) mAP50-95 | Synthetic val mAP50-95 |
|---|---|---|---|---|---|---|
| Synthetic only | 5,000 | 2,851 synthetic | 0.025 | 0.061 | 0.083 | 0.937 |
| Real only (+augment) | 3,000 | 2,000 real | **0.463** | 0.686 | 0.578 | 0.281 |
| Synthetic, then real (lr 0.002, +augment) | 5,000 + 3,000 | 2,851 + 2,000 | 0.436 | 0.656 | 0.556 | 0.313 |
| Mix 50/50 (+augment) | 4,000 | 2,000 real + 2,851 synthetic | 0.432 | 0.642 | 0.505 | 0.939 |
| Docling heron (reference, CPU) | none | DocLayNet train and more | 0.705 | 0.883 | n/a | n/a |

Test AP50-95 per class, real only: text 0.67, table 0.59, page-header 0.53, page-footer 0.53, picture 0.52, section-header 0.49, list-item 0.46, caption 0.41, formula 0.41, title 0.31, footnote 0.17.

**Reading it.**
- 2,000 real pages reach 0.463, about two thirds of Docling's 0.705 with a small model and nine minutes of training (531 s). This is the useful route.
- Synthetic-only is still near zero (0.025) even though every class now occurs, and list-item and formula score 0.00. So the gap is how the pages look, not only which classes exist.
- Synthetic pre-training did not help and may have hurt a little: finetune 0.436 and mix 0.432 against 0.463 for real only. These are single runs, and the 50-page validation scores differ by more (0.578, 0.556, 0.505), so treat gaps of this size as unproven rather than as a ranking. What is safe to say is that no arm beat real-only.
- Footnote is the weakest class for every arm that trained on real pages, and it is the rarest class: 6,318 boxes in all of DocLayNet, and 23 in the earlier 500-page train sample.

Open: more real pages and a longer schedule (the DocLayNet paper's learning curve flattens near 80% of the 69k training pages), a different synthetic generator that copies real layouts rather than SEA-history templates, and seeds to size the noise.


## Real-only learning curve, two seeds (SYN-27)

One pod, a community NVIDIA RTX 3090 (RunPod, $0.22/hr, 3.25 h, $0.71), repo `e6c4371`, rtod `3751bc7`. Real training pages are seeded random subsets of the first 12 of 24 DocLayNet train shards (so a different draw from the 2,000 pages in SYN-7). Every arm uses batch 16, 640 px, `--augment`, COCO start, and is scored on the same 500 test pages as above.

| Real pages | Steps | Seed 0 | Seed 1 | Mean | Spread |
|---|---|---|---|---|---|
| 2,000 | 3,000 | 0.506 | 0.562 | 0.534 | 0.056 |
| 5,000 | 6,000 | 0.592 | 0.591 | 0.592 | 0.001 |
| 10,000 | 10,000 | 0.630 | 0.629 | 0.630 | 0.001 |
| Docling heron (reference) | none | | | 0.705 | |

Per-class AP50-95 at 10,000 pages (mean of two seeds): text 0.855, table 0.779, picture 0.767, footnote 0.800, caption 0.773, list-item 0.651, section-header 0.628, page-footer 0.467, page-header 0.290, formula 0.286, title 0.000.

**Reading it.**
- More real pages keep helping: 0.534, 0.592, 0.630 for 2k, 5k, 10k. 10k pages reach 89% of Docling's 0.705. Each doubling adds less (+0.058, then +0.038 for 2x), consistent with a curve that flattens, but the 10k point is not yet on a plateau.
- Seed noise is large at 2k (0.056 between two seeds, as big as the SYN-7 gaps between arms) and small at 5k and 10k (0.001). Read the SYN-7 arm ranking with that in mind: the 0.463 there is one draw at 2k and sits below both new 2k seeds (0.506, 0.562), so differences of 0.03 at that size are within noise.
- Title scores 0.000 in all six runs here, against 0.31 for the SYN-7 real-only run. Title is 0.5% of DocLayNet boxes, so a model that never learns it moves the mean little, but it appeared at every seed and size, so it is worth a look and is not investigated here.
- Formula is the other weak class (0.28 at 10k) and the one that improves most with data (0.001, 0.16-0.24, 0.29).
- Page-header and page-footer stay low even at 10k (0.29, 0.47). The generator labels them exactly, so they are a candidate for synthetic data to help with; this is a hypothesis, not tested.

Spend to date for the project is about $1.3 of the $5 cap (the ledger over-counts by about $0.14 because the stopped first SYN-27 attempt was logged twice).

## Class mix against DocLayNet (SYN-25)

`scripts/layout_stats.py` prints each class's share of boxes and boxes per page. Sample: 14 documents (291 pages) from all seven recipes, variants `random standard structured`, seed start 500, next to the 500-page real test sample and the paper's Table 1 (1,107,470 boxes).

| class | DocLayNet | synthetic (14 documents) | real test sample (500 pages) |
|---|---:|---:|---:|
| Text | 46.1% | 27.4% | 38.9% |
| List-item | 16.8% | 0.0% | 9.8% |
| Section-header | 12.9% | 7.3% | 13.3% |
| Page-footer | 6.4% | 18.6% | 7.0% |
| Page-header | 5.2% | 9.3% | 6.1% |
| Picture | 4.2% | 8.0% | 11.0% |
| Table | 3.1% | 8.7% | 8.0% |
| Formula | 2.3% | 2.3% | 0.0% |
| Caption | 2.0% | 15.6% | 5.6% |
| Footnote | 0.6% | 2.4% | 0.2% |
| Title | 0.5% | 0.4% | 0.0% |
| **boxes per page** | 12.2 | 10.8 | 10.7 |

Reading it:

- **List-item is 0.0% of synthetic boxes against 16.8% in DocLayNet.** The `structured` variant only makes a list from a paragraph with at least 5 sentences, and 7 of the 429 recipe paragraphs have that many (230 have 3, 113 have 2). The "all 11 classes occur" test in SYN-22 passed on a small sample by luck of the draw. List-item is the second most common real class, so this is the largest gap.
- **Page-footer (18.6% vs 6.4%) and caption (15.6% vs 5.6% in the sample, 2.0% in the paper) are over-represented**, and text is under (27.4% vs 38.9% sampled, 46.1% in the paper).
- **Density is close** (10.8 boxes per page vs 10.7 in the real sample, 12.2 in the paper), so the page-level count is not the problem; the mix and the look are.
- Formula and footnote are over-represented too (2.3% and 2.4% against 0.0% and 0.2% in the real sample), though in the paper they are 2.3% and 0.6%.

**After SYN-29:** `structured` now makes a list from any paragraph of 3 or more sentences (60% of them, last 3 sentences as items). On the same 14-document sample list-item is 9.4% of boxes (real sample 9.8%, paper 16.8%) and boxes per page is 11.7. The SYN-6 and SYN-7 models were trained before this change.

## Why synthetic pages do not transfer: first look (SYN-28)

Four random real test pages next to four synthetic pages, both with their boxes drawn (14-document sample, `random standard structured`). What differs, by eye:

- **Real pages are mostly not white-on-black-text reports.** Of the four, two are full-bleed photo or colour pages with a few text boxes, one is a two-column magazine page with a portrait, one is a photo-and-charts page on a tinted background. Synthetic pages are always white with plain text, one table or one pale figure.
- **Pictures are photographs, charts with real colour, and logos.** Synthetic pictures are flat pale rectangles with a few labelled boxes. A detector trained on them has never seen a photo labelled `picture`.
- **Text is small, dense and in varied faces** (condensed bold, serif on dark backgrounds, text set in the image). Synthetic body text is large, loosely spaced and in three built-in fonts.
- **Page furniture is tiny and inconsistent** (a folio in a corner, a running head inside a colour band). Synthetic headers and footers are the same two strings on every page.
- **Boxes per page are similar (11.7 vs 10.7), but their sizes are not**: real pages have a few very large boxes (pictures) and many small ones; synthetic boxes are evenly sized.

This is a visual impression from eight pages, not a measurement. The largest gaps to try first, in order: photographic and coloured pictures, tinted or image backgrounds, denser and smaller type, then font variety. The SYN-28 done-when (re-run the synthetic-only arm on the same 500 pages) needs a GPU pod and waits for the SYN-27 run to clear the pod queue.

**First generator change (SYN-28).** Non-chart pictures are now continuous-tone, full-colour images (`make_photo_figure`: layered value noise, soft coloured blobs and grain, seeded per figure) instead of the same flat three-box diagram on every page. This addresses only the first gap, photographic and coloured pictures. Tinted backgrounds, denser type and font variety are not done. Whether it moves the synthetic-only score is not yet measured.

**Result of the first change (SYN-28).** Synthetic-only arm again, same settings as SYN-7 (5,000 steps, batch 16, 640 px, no augment), on a community RTX 3090 ($0.34/hr, 0.39 h, $0.13), repo `8bbef77`. Training set 2,911 synthetic pages from 150 documents. The generator now includes the list fix (SYN-29), the DocLayNet box conventions (SYN-24) and photo-like pictures together, so this measures all of them, not the photo change alone.

| | SYN-7 | Now |
|---|---|---|
| DocLayNet test (500 pages) mAP50-95 | 0.025 | **0.029** |
| DocLayNet validation (50 pages) mAP50-95 | 0.083 | 0.098 |
| Synthetic validation mAP50-95 | 0.937 | 0.914 |

Test AP50-95 per class: text 0.110, table 0.074, picture 0.050, formula 0.017, title 0.015, list-item 0.014, footnote 0.014, page-footer 0.009, section-header 0.005, caption 0.004, page-header 0.000.

Not a measurable improvement: 0.025 to 0.029 is a single seed on each side, and SYN-27 showed seed spread of 0.06 at small data sizes. Synthetic-only is still at about 4% of the real-only score (0.63 at 10k pages). What did change is that list-item is no longer 0.00 on the real validation pages (0.076), which is the expected effect of SYN-29. Pictures are no longer the obvious gap: the picture class scores 0.05, so the model does not find real photographs even after training on coloured images, which suggests the remaining gap is in page structure and typography, not picture content alone. That is an inference from one run, not tested. Next to try, in order: tinted backgrounds, denser and smaller type, font variety.

**Box size against DocLayNet (SYN-28, 500 test pages vs 14 synthetic documents).** Median box width and area as a share of the page:

| Class | Real width | Real area | Synthetic width | Synthetic area |
|---|---|---|---|---|
| text | 0.41 | 0.023 | 0.79 | 0.044 |
| list-item | 0.40 | 0.008 | 0.37 | 0.016 |
| section-header | 0.22 | 0.003 | 0.79 | 0.016 |
| picture | 0.33 | 0.145 tall, area 0.044 | 0.73 | area 0.137 |
| table | 0.75 | 0.099 | 0.79 | 0.101 |

Tables match. Section headers are drawn as full-column boxes while real header boxes hug the text (0.22 of page width), pictures are three times too large, and text blocks are about twice as wide as real ones (real pages are more often multi-column or have narrow blocks). These are the geometry gaps to close next; they are cheaper to act on than the typography guesses.

**Tinted backgrounds (SYN-31).** One page in five now has a pale background tint (every channel at least 0.85). It is drawn behind the page and is not a truth box.
