# Text Correction Follow-up Plan

Date: 2026-06-07

## Previous Plan Coverage

The previous v2 plan at `~/.claude/plans/nested-mapping-trinket.md` already covered this direction:

- Stage 3: OCR verification layer
- Stage 4: anomaly pipeline plus multimodal fallback
- Stage 5: 100-image golden validation set
- Stage 6: TTA / YOLOv8m only if the pipeline still misses target accuracy

The plan was directionally correct, but one assumption must be revised. It said OCR quantity is usually more reliable and suggested taking `max(yolo, ocr)`. The gift13 text-correction experiment shows the safer rule is:

> YOLO decides concrete product identity. Text only corrects quantity when the concrete subtype is exact or already supported by YOLO detections.

Impact: vague text such as `玉米片 10` can correct counts only after YOLO has identified the actual flavors. It must not create ERP items or choose flavors by itself.

## Current Evidence

Trial report: `docs/text-correction-gift13-report.md`

On the gift13 trial subset, using train7 with `conf=0.25`, `iou=0.70`:

| Mode | Expected | Detected | Correct | Recall | Precision |
|---|---:|---:|---:|---:|---:|
| YOLO-only | 103 | 81 | 65 | 0.631 | 0.802 |
| text-only | 103 | 32 | 32 | 0.311 | 1.000 |
| YOLO+text | 103 | 119 | 103 | 1.000 | 0.866 |

This proves text correction is useful for dense count recovery. It does not prove production readiness because the expected set is caption-derived and unresolved caption parts are excluded from final truth.

Strict exact-match trial: `docs/text50-evaluation-report.md`

The initial text50 set has 50 candidate images, with 12 labeled, 1 ambiguous, and 37 pending. Pending/ambiguous samples are excluded from exact-match accuracy.

| Mode | Exact | Total | Accuracy |
|---|---:|---:|---:|
| YOLO-only | 3 | 12 | 0.250 |
| text-only | 5 | 12 | 0.417 |
| YOLO+text | 5 | 12 | 0.417 |
| YOLO+text gated | 11 | 12 | 0.917 |

Decision: raw YOLO+text merge is not enough. The route remains viable only with anomaly gating that blocks YOLO extras not supported by text and routes unresolved subtype cases to visual fallback.

## Follow-up Goal

Build a production-shaped evaluation pipeline that can answer one question:

> Can YOLO-first text correction plus anomaly fallback reach product-mapping exact-match accuracy on real KGOS SKU images?

Final acceptance must use product-mapping output:

```js
recognition.items = [{ name: "<ERP standard product name>", qty: <number> }]
```

Comparison must be exact by ERP standard `name × qty`.

## Phase A: Lock the Correction Policy

Status: mostly done.

Tasks:

1. Keep `scripts/ocr_verify.py` as the policy reference.
2. Maintain shorthand knowledge in `data/kgos_text_aliases.json`:
   - `exact_aliases`: shorthand with enough specificity to map directly to one ERP product.
   - `ambiguous_groups`: shorthand that maps to multiple ERP candidates and requires visual support.
3. Add group rules only when they are business-safe:
   - `玉米片 10` + YOLO sees both corn-chip flavors -> split 5/5.
   - `玉米片 10` + YOLO sees one flavor only -> correct that one flavor to 10 only if the image visibly has one flavor; otherwise unresolved.
   - `黑茶体验装 1` + YOLO sees two flavors -> unresolved, because text cannot decide flavor.
   - `营养粉 3` + YOLO sees no safe subtype -> unresolved.
   - `莓果营养粉 3` or `牛油果营养粉 3` -> exact alias, because the flavor is explicit.
4. Add more unit tests before expanding rules.

Acceptance:

- No vague text may create a concrete ERP product without visual support.
- No unresolved item is counted as success.
- Every newly encountered shorthand is added to `data/kgos_text_aliases.json` with either exact or ambiguous semantics.

## Phase B: Build a Real Text Extraction Path

Current script uses existing visible-caption text. It does not yet OCR the image.

Tasks:

1. Implement `extract_text(image_path)` behind a provider interface:
   - `manual`: existing report/caption text, for reproducible tests.
   - `ocr`: local OCR if installed.
   - `llm`: multimodal extraction fallback.
2. Start with bottom/title regions:
   - bottom 20% crop
   - top 25% crop
   - full image as fallback
3. Save extraction artifacts per image:
   - raw text
   - crop used
   - provider
   - parse result
   - unresolved items

Acceptance:

- At least 50 real images have extraction records.
- OCR/text extraction can be re-run without changing image data.

## Phase C: Create a 50-image Text Effectiveness Set

Purpose: measure whether text extraction is good enough before building full integration.

Tasks:

1. Select 50 real KGOS images from `datasets/kgos_real_golden_candidates_v1/images`.
2. Manually write ground truth in a structured file:

```json
{
  "real_001.jpg": {
    "items": [
      { "name": "KGOS玉米浓汤味玉米片 30g", "qty": 5 },
      { "name": "KGOS香菜牛肉味玉米片 30g", "qty": 5 }
    ],
    "notes": "caption says 玉米片10, visual shows two flavors"
  }
}
```

3. Evaluate:
   - text extraction recall
   - text parse precision
   - unresolved rate
   - YOLO-only exact image accuracy
   - YOLO+text exact image accuracy

Acceptance:

- Text extraction effective rate >= 90% on images with useful title/caption text.
- YOLO+text improves exact image accuracy over YOLO-only.
- Every unresolved item is visible in the report.

## Phase D: Add Anomaly Gating

Purpose: improve precision by preventing YOLO false positives from flowing into product matching.

Anomaly triggers:

- `TEXT_UNRESOLVED`: text mentions a product group but subtype cannot be resolved.
- `YOLO_EXTRA_NOT_IN_TEXT`: YOLO detects extra product categories not supported by title/caption.
- `LOW_CONFIDENCE`: class confidence below configured threshold.
- `COUNT_CONFLICT`: text count and YOLO count conflict beyond allowed correction policy.
- `NO_TEXT_SIGNAL`: no useful title/caption text found.

Actions:

- Low severity: keep YOLO result, mark warning.
- Medium severity: require LLM visual correction.
- High severity: block automatic product-mapping write.

Acceptance:

- False positives like extra coffee/lattes in gift13 are flagged.
- Pipeline output includes `needsReview` and `reasons`.
- On the labeled text50 subset, gated exact-match accuracy remains materially above raw YOLO+text.

## Phase E: Multimodal Fallback

Purpose: handle unresolved cases that text and YOLO cannot safely decide.

Tasks:

1. Create `scripts/codex_correct.py` or equivalent multimodal correction entry.
2. Prompt must require ERP standard names and quantities.
3. LLM may only fill unresolved or anomalous fields unless explicitly running full-image correction.
4. Store raw response and parsed result for audit.

Acceptance:

- `3.jpg` black-tea trial flavor and `11.jpg` nutrition powder ambiguity are resolved or explicitly rejected.
- LLM call rate target remains below 15% on the golden set.

## Phase F: 100-image Golden Validation

Purpose: decide whether the pipeline is production-safe.

Tasks:

1. Build 100-image ground truth:
   - 13 gift images
   - dense/combo images from `1/`
   - representative root images
2. Ground truth must be manually checked against product-mapping ERP names.
3. Evaluate three modes:
   - YOLO-only
   - YOLO+text
   - YOLO+text+fallback
4. Metrics:
   - exact image accuracy
   - item-level precision/recall
   - unresolved rate
   - LLM call rate
   - blocked-review rate

Acceptance:

- Exact image accuracy >= 98% for automatic pass.
- If accuracy is lower but review blocking catches all risky cases, integrate as assisted mode only.

## Phase G: Product-mapping Integration Gate

Only proceed after Phase F.

Tasks:

1. Export or choose runtime model path without overwriting production ONNX prematurely.
2. Add product-detect as a product-mapping recognition provider.
3. Preserve current manual/LLM flow as fallback.
4. Write comparison report before any production write.

Acceptance:

- No automatic ERP/product-mapping mutation from uncertain recognition.
- Existing product-mapping exact strings are preserved.

## Immediate Next Step

Do Phase C first:

1. Create `datasets/kgos_real_text50/ground_truth.json`.
2. Pick 50 images from `kgos_real_golden_candidates_v1`.
3. Add an evaluator that reads ground truth and runs current YOLO+text policy.

Why: without a manually checked text50 set, OCR/LLM/provider work can look good on gift13 but fail the real matching goal.
