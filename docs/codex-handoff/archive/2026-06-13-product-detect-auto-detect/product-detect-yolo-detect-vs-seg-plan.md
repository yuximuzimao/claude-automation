# KGOS YOLO Detect vs Segment Pilot Plan

> From: Codex
> To: Claude Code
> Date: 2026-06-11
> Status: superseded by `docs/detect-vs-seg-pilot-plan-v2.md` and `docs/sam-auto-detect-runbook.md`

## Request

User wants Claude to review the model-route plan before Codex implements it.

Core user requirements:

- Compare YOLO detection and YOLO instance segmentation from the model-choice stage.
- Do not base the new candidate models on existing `train7` or future `train8`; COCO pretrained weights are acceptable.
- Configure automatic/interactive annotation, because manual Label Studio bbox drawing is too slow and inaccurate.
- Tell the user exactly which images to annotate.
- Use the same image set for both candidates, train both candidates, compare results, then choose the final route.

## Terminology Clarification

Use the user's wording in future discussion:

- **Label Studio ML Backend 自动标注** is the feature we are configuring.
- **SAM** is only one possible model running behind that ML Backend. It is not a separate labeling product.
- For this pilot, "SAM-assisted segmentation" means:

```text
Label Studio page
  -> sends image + user click/box prompt to ML Backend
  -> ML Backend runs a segmentation model such as SAM
  -> Label Studio receives a suggested product mask/outline
  -> user accepts, fixes, deletes, or relabels the suggestion
```

When explaining this to the user, say "Label Studio 的 ML Backend 自动轮廓标注" first, and mention SAM only as the model used inside that backend.

## Current Context

Project root:

```text
/Users/chat/claude/product-detect
```

Current real-image source:

```text
/Users/chat/claude/product-detect/datasets/kgos_real_all/images/
```

Existing Label Studio config only enables bbox annotation:

```text
/Users/chat/claude/product-detect/datasets/kgos_real_all/label_studio_config.xml
```

Current route in docs says `train8` should use 270 manually labeled real images with YOLO detection. This plan proposes a smaller pilot before committing to the final route.

Important business metric:

```text
recognition.items = [{ name: ERP标准商品名, qty }]
```

Model success is not just mAP. The final decision must use exact `商品名×数量` comparison on held-out real images.

## Recommendation

Use one segmentation annotation set as the source of truth, then derive both model datasets from it:

```text
Label Studio segmentation annotations
  ├─ YOLO-seg labels: class + polygon points
  └─ YOLO-detect labels: class + bbox derived from each polygon/mask
```

Why this matters:

- The detect and segment candidates train on the same images and same object decisions.
- Detection labels are automatically derived from the segmentation labels, so the user does not label twice.
- The comparison becomes fair: only model/task type changes, not human labeling differences.

## Pilot Image Set

Annotate exactly these 64 images first.

Rationale:

- Include all `gift_` images because previous train7 failed hardest on dense gift scenes.
- Include 40 `combo_` images for buy-gift/product-combination scenes.
- Include 11 `main_` images so the pilot still covers simpler single-product scenes.
- Keep annotation small enough to finish quickly, but large enough to reveal whether segmentation helps dense counting.

### Train Split: 50 Images

```text
gift_001.jpg
gift_002.jpg
gift_003.jpg
gift_004.jpg
gift_005.jpg
gift_006.jpg
gift_007.jpg
gift_008.jpg
gift_009.jpg
gift_010.jpg
combo_001.jpg
combo_002.jpg
combo_003.jpg
combo_004.jpg
combo_005.jpg
combo_006.jpg
combo_007.jpg
combo_008.jpg
combo_009.jpg
combo_010.jpg
combo_011.jpg
combo_012.jpg
combo_013.jpg
combo_014.jpg
combo_015.jpg
combo_016.jpg
combo_017.jpg
combo_018.jpg
combo_019.jpg
combo_020.jpg
combo_021.jpg
combo_022.jpg
combo_023.jpg
combo_024.jpg
combo_025.jpg
combo_026.jpg
combo_027.jpg
combo_028.jpg
combo_029.jpg
combo_030.jpg
combo_031.jpg
combo_032.jpg
main_001.jpg
main_002.jpg
main_003.jpg
main_004.jpg
main_005.jpg
main_006.jpg
main_007.jpg
main_008.jpg
```

### Val Split: 14 Images

```text
gift_011.jpg
gift_012.jpg
gift_013.jpg
combo_033.jpg
combo_034.jpg
combo_035.jpg
combo_036.jpg
combo_037.jpg
combo_038.jpg
combo_039.jpg
combo_040.jpg
main_009.jpg
main_010.jpg
main_011.jpg
```

## Annotation Policy

User should annotate with Label Studio ML Backend assisted segmentation, not manual bbox-first annotation.

Label every visible real product instance:

- One instance = one physical product item that should count toward `recognition.items`.
- Use ERP standard label names exactly as in the existing 28-class config.
- Do not label activity text, price text, "赠" badges, background graphics, or package illustrations printed on boxes.
- If an object is partially occluded but still identifiable, label only the visible product region.
- If the visible region cannot identify the exact ERP item, skip it rather than guessing.

For segmentation:

- Prefer Label Studio ML Backend generated mask/brush output. The first backend to try is a SAM-based backend.
- Polygon is acceptable if SAM output is too noisy.
- The annotation does not need perfect product-edge cutout quality; it only needs to separate adjacent instances better than bbox labeling.
- Avoid masks that merge multiple same-class products into one region. Dense repeated products must be separate instances.

## Label Studio Setup Plan

Create a new temporary project. Do not mutate the existing bbox project until the pilot is reviewed.

Project name:

```text
KGOS Detect-vs-Seg Pilot
```

Create this config file:

```text
/Users/chat/claude/product-detect/datasets/kgos_real_all/label_studio_seg_pilot_config.xml
```

Recommended config shape:

```xml
<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>

  <Header value="KGOS 分割标注试验：优先用 SAM/智能工具生成轮廓；同一份轮廓会派生检测框和分割标签。"/>

  <BrushLabels name="mask" toName="image" showInline="true">
    <!-- Use the same 28 ERP labels from label_studio_config.xml. -->
  </BrushLabels>

  <RectangleLabels name="prompt_box" toName="image" smart="true" showInline="true">
    <!-- Same 28 ERP labels; used only as SAM prompt if the backend requires rectangle prompts. -->
  </RectangleLabels>

  <KeyPointLabels name="prompt_point" toName="image" smart="true" showInline="true">
    <!-- Same 28 ERP labels; used only as SAM positive/negative prompt if needed. -->
  </KeyPointLabels>
</View>
```

Implementation note:

- Fill all 28 ERP labels by copying from `label_studio_config.xml`.
- The persisted source-of-truth annotation should be `BrushLabels name="mask"` where possible.
- `prompt_box` and `prompt_point` are helper prompts for SAM and should not be treated as final training labels.

## ML Backend Plan

First try a Label Studio ML Backend that runs a SAM-family segmentation model because it is designed for interactive mask/outline suggestions.

Expected local backend:

```text
http://localhost:9090
```

Success criteria for backend setup:

```bash
curl --noproxy '*' http://localhost:9090/health
```

Expected response contains:

```json
{"status":"UP","v2":"true"}
```

Label Studio project settings:

- Connect model URL: `http://localhost:9090`
- Enable interactive preannotations / auto-annotation. In user-facing language, call this "Label Studio ML Backend 自动标注".
- Keep auto-accept disabled until the user sees that masks are sensible.

If Docker/model download is too slow or blocked:

- Do not abandon the pilot.
- Fall back to manual polygon/brush for the 64-image pilot.
- Continue with conversion and model comparison.

## Data Conversion Plan

Create conversion outputs:

```text
/Users/chat/claude/product-detect/datasets/kgos_seg_pilot/
/Users/chat/claude/product-detect/datasets/kgos_detect_from_seg_pilot/
```

Both datasets must use the same image files and the same split.

### YOLO-seg label format

Each object line:

```text
class_id x1 y1 x2 y2 x3 y3 ...
```

Coordinates are normalized to `[0, 1]`.

### YOLO-detect label format

Each object line derived from the polygon/mask extent:

```text
class_id x_center y_center width height
```

Coordinates are normalized to `[0, 1]`.

Important:

- Do not manually draw detection boxes.
- Detection boxes must be derived from segmentation labels so both models see the same object decisions.

## Proposed Files for Implementation

Create:

```text
/Users/chat/claude/product-detect/scripts/prepare_seg_pilot_import.py
/Users/chat/claude/product-detect/scripts/convert_labelstudio_seg_export.py
/Users/chat/claude/product-detect/scripts/train_seg_pilot.py
/Users/chat/claude/product-detect/scripts/evaluate_detect_vs_seg.py
/Users/chat/claude/product-detect/tests/test_convert_labelstudio_seg_export.py
/Users/chat/claude/product-detect/tests/test_evaluate_detect_vs_seg.py
/Users/chat/claude/product-detect/datasets/kgos_real_all/label_studio_seg_pilot_config.xml
/Users/chat/claude/product-detect/docs/detect-vs-seg-pilot-report.md
```

Modify only if needed:

```text
/Users/chat/claude/product-detect/CLAUDE.md
/Users/chat/claude/product-detect/SKILL.md
/Users/chat/claude/product-detect/tasks/todo.md
```

## Training Plan

Use COCO pretrained weights, not train7/train8 weights.

Detection candidate:

```bash
python -u scripts/train.py \
  --brand kgos_detect_from_seg_pilot \
  --model yolov8s \
  --name kgos_detect_from_seg_pilot_yolov8s
```

If `scripts/train.py` is too brand-specific, create a pilot-specific training command instead:

```bash
yolo detect train \
  model=yolov8s.pt \
  data=datasets/kgos_detect_from_seg_pilot/data.yaml \
  epochs=80 \
  imgsz=1280 \
  batch=4 \
  project=runs \
  name=kgos_detect_from_seg_pilot_yolov8s
```

Segmentation candidate:

```bash
yolo segment train \
  model=yolov8s-seg.pt \
  data=datasets/kgos_seg_pilot/data.yaml \
  epochs=80 \
  imgsz=1280 \
  batch=4 \
  project=runs \
  name=kgos_seg_pilot_yolov8s_seg
```

Fast smoke test before long runs:

```bash
yolo detect train model=yolov8n.pt data=datasets/kgos_detect_from_seg_pilot/data.yaml epochs=3 imgsz=640 batch=2 project=runs name=kgos_detect_pilot_smoke
yolo segment train model=yolov8n-seg.pt data=datasets/kgos_seg_pilot/data.yaml epochs=3 imgsz=640 batch=2 project=runs name=kgos_seg_pilot_smoke
```

## Evaluation Plan

Evaluate on the same held-out 14 validation images.

Metrics to report:

- Detection candidate:
  - `metrics.box.map50`
  - `metrics.box.map`
  - per-image exact `商品名×数量`
  - recall / precision by ERP item count
- Segmentation candidate:
  - `metrics.box.map50`
  - `metrics.box.map`
  - `metrics.seg.map50`
  - `metrics.seg.map`
  - per-image exact `商品名×数量`
  - recall / precision by ERP item count

Business decision table:

```text
model,image_exact,erp_item_recall,erp_item_precision,gift_exact,combo_exact,avg_infer_ms,notes
detect,...
segment,...
```

Decision rule:

- Choose segmentation only if it improves exact image accuracy or dense-scene recall materially on `gift_`/`combo_` images.
- "Materially" means at least one of:
  - +10 percentage points image exact accuracy on the 14-image val split.
  - +10 percentage points item recall with precision not worse by more than 3 percentage points.
  - At least 2 additional `gift_`/`combo_` validation images exact-match correctly.
- If segmentation improves mask mAP but not `商品名×数量`, do not switch main route.
- If results are close, prefer detection because it is simpler to export and maintain.

## Risks Claude Should Review

1. The 64-image pilot may not cover all 28 classes.
   - This is acceptable for model-route selection, but not final production training.
   - If Claude thinks class coverage matters more than density coverage, revise the image list before user starts annotation.

2. SAM masks may merge repeated same-class products.
   - This would harm counting.
   - The annotation guide must explicitly require one mask per physical product.

3. Label Studio BrushLabels export may need conversion from RLE.
   - The conversion script must support both BrushLabels RLE and PolygonLabels points.

4. The current `scripts/train.py` is brand-oriented and may not accept pilot dataset names cleanly.
   - Prefer direct `yolo detect train` / `yolo segment train` for the pilot if needed.

5. `imgsz=1280` is likely important because real images are 1200/1280 square and contain small dense products.
   - If memory is insufficient, reduce batch before reducing image size.

## User-Facing Annotation Instruction After Claude Review

Tell the user:

```text
先标 64 张：
gift_001 到 gift_013，
combo_001 到 combo_040，
main_001 到 main_011。

标注方式不是画方框，而是用 SAM/智能轮廓工具给每个真实商品实例单独生成一个 mask。
我会用同一份 mask 自动派生检测框，所以你不需要重复标检测框。
```

## Review Questions for Claude

Please review specifically:

1. Is the 64-image pilot split a good enough route-selection sample, or should it be adjusted for class coverage?
2. Should the pilot use `yolov8s/yolov8s-seg` as planned, or test `yolov8n/yolov8n-seg` first and only run `s` after conversion is proven?
3. Is deriving detection bbox from segmentation mask the right fairness strategy?
4. Any known Label Studio export gotchas for BrushLabels RLE in this installed version?
5. Should the acceptance threshold be stricter before switching to segmentation?
