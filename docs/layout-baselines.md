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

