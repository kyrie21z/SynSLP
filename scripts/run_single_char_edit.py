#!/usr/bin/env python3
"""
SynSLP Order-Based Single-Character Edit with AnyText2.

Task:
  Run exactly one minimal AnyText2 single-character edit on server:
  东泰168 -> 东泰268
  Only character instance order=2 (text='1', bbox=[120, 3, 147, 52]) is masked and regenerated.
  Input uses aspect-ratio-preserving 512x512 letterbox.
  Font Mimic is disabled for this diagnostic experiment.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.generate_character_masks import generate_mask_for_orders, load_annotation


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run order-based single-character edit using AnyText2."
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=ROOT_DIR / "annotations" / "character_annotations.jsonl",
        help="Path to JSONL annotation file",
    )
    parser.add_argument(
        "--image",
        type=str,
        default="reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg",
        help="Image path in annotation file",
    )
    parser.add_argument(
        "--order",
        type=int,
        default=2,
        help="Character instance order to edit (default: 2 for glyph '1')",
    )
    parser.add_argument(
        "--replacement_text",
        type=str,
        default="2",
        help="Replacement text for the masked character box (default: '2')",
    )
    parser.add_argument(
        "--img_prompt",
        type=str,
        default="a realistic photo of a Chinese ship license plate",
        help="Image prompt for AnyText2 conditioning",
    )
    parser.add_argument(
        "--baseline_crop",
        type=Path,
        default=None,
        help="Path to baseline output crop for A/B comparison board",
    )
    parser.add_argument(
        "--baseline_prompt",
        type=str,
        default="a realistic photo of a Chinese ship license plate",
        help="Baseline image prompt text for comparison board legend",
    )
    parser.add_argument(
        "--font_mimic",
        action="store_true",
        default=False,
        help="Enable native AnyText2 Font Mimic conditioning using source glyph",
    )
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--ddim_steps", type=int, default=20)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--cfg_scale", type=float, default=7.5)
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=ROOT_DIR / "outputs" / "single_char_edit" / "dongtai168_order2_1_to_2",
        help="Output directory for results",
    )
    return parser.parse_args()


def create_letterbox(
    image_bgr: np.ndarray, mask_gray: np.ndarray, target_size: int = 512
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Uniformly scale image so its long side equals target_size,
    center on a target_size x target_size black canvas,
    and apply the exact same transformation to mask using nearest-neighbor interpolation.
    """
    h, w = image_bgr.shape[:2]
    scale = target_size / max(w, h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))

    # Center offsets
    pad_x = (target_size - new_w) // 2
    pad_y = (target_size - new_h) // 2

    # Scale reference with Lanczos4 and mask with Nearest
    scaled_img = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    scaled_mask = cv2.resize(mask_gray, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

    letterbox_img = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    letterbox_mask = np.zeros((target_size, target_size), dtype=np.uint8)

    letterbox_img[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = scaled_img
    letterbox_mask[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = scaled_mask

    geo_info = {
        "orig_w": w,
        "orig_h": h,
        "target_size": target_size,
        "scale": scale,
        "new_w": new_w,
        "new_h": new_h,
        "pad_x": pad_x,
        "pad_y": pad_y,
    }
    return letterbox_img, letterbox_mask, geo_info


def invert_letterbox(
    output_img: np.ndarray, geo_info: dict
) -> np.ndarray:
    """Crop the valid content region from letterbox and resize back to original resolution."""
    pad_x = geo_info["pad_x"]
    pad_y = geo_info["pad_y"]
    new_w = geo_info["new_w"]
    new_h = geo_info["new_h"]
    orig_w = geo_info["orig_w"]
    orig_h = geo_info["orig_h"]

    cropped = output_img[pad_y : pad_y + new_h, pad_x : pad_x + new_w]
    restored = cv2.resize(cropped, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
    return restored


def render_header_card(img: np.ndarray, label: str, header_h: int = 34, font_size: int = 18) -> np.ndarray:
    """Render a card with a top header bar containing cleanly rendered text."""
    card = np.full((img.shape[0] + header_h, img.shape[1], 3), (35, 35, 35), dtype=np.uint8)
    card_rgb = cv2.cvtColor(card, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(card_rgb)
    draw = ImageDraw.Draw(pil_img)
    font = None
    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/home/kyrie/.local/share/fonts/kymcm-lite/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        str(ROOT_DIR / "third_party" / "AnyText2" / "font" / "Arial_Unicode.ttf"),
    ]
    for fc in font_candidates:
        if os.path.exists(fc):
            try:
                font = ImageFont.truetype(fc, font_size)
                break
            except Exception:
                pass
    if font is not None:
        draw.text((10, 6), label, font=font, fill=(255, 255, 255))
        card = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    else:
        cv2.putText(card, label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
    card[header_h:, :] = img
    return card


def create_comparison_board(
    ref_orig: np.ndarray,
    mask_orig: np.ndarray,
    out_orig: np.ndarray,
    ref_512: np.ndarray,
    mask_512: np.ndarray,
    out_512: np.ndarray,
    output_path: Path,
):
    """Generate a clean side-by-side comparison board with clear annotations."""
    # Blend mask with ref for visualization
    red_overlay_orig = ref_orig.copy()
    red_overlay_orig[mask_orig > 0] = [0, 0, 255]
    blend_orig = cv2.addWeighted(ref_orig, 0.6, red_overlay_orig, 0.4, 0)

    # 1. Original Resolution strip (scale by 3x for clear legibility on display)
    scale_factor = 3
    disp_w = ref_orig.shape[1] * scale_factor
    disp_h = ref_orig.shape[0] * scale_factor

    col1 = cv2.resize(ref_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col2 = cv2.resize(blend_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col3 = cv2.resize(out_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)

    c1 = render_header_card(col1, "1. Reference (239x57 -> 东泰168)")
    c2 = render_header_card(col2, "2. Order-2 Edit Mask (Glyph '1')")
    c3 = render_header_card(col3, "3. Edited Output (239x57 -> 东泰268)")

    row_orig = np.hstack([c1, c2, c3])

    # 2. Letterbox 512 strip
    red_512 = ref_512.copy()
    red_512[mask_512 > 0] = [0, 0, 255]
    blend_512 = cv2.addWeighted(ref_512, 0.6, red_512, 0.4, 0)

    lb1 = render_header_card(ref_512, "Letterbox Reference (512x512)")
    lb2 = render_header_card(blend_512, "Letterbox Mask (Order 2)")
    lb3 = render_header_card(out_512, "AnyText2 Output (512x512)")

    # Resize letterbox cards to match row_orig width
    lb_combined = np.hstack([lb1, lb2, lb3])
    lb_resized = cv2.resize(lb_combined, (row_orig.shape[1], int(lb_combined.shape[0] * (row_orig.shape[1] / lb_combined.shape[1]))))

    sep = np.full((12, row_orig.shape[1], 3), (15, 15, 15), dtype=np.uint8)
    final_board = np.vstack([row_orig, sep, lb_resized])

    cv2.imwrite(str(output_path), final_board)
    print(f"Saved comparison board: {output_path} ({final_board.shape[1]}x{final_board.shape[0]})")


def create_prompt_ab_comparison_board(
    ref_orig: np.ndarray,
    baseline_orig: np.ndarray,
    ablation_orig: np.ndarray,
    baseline_prompt: str,
    ablation_prompt: str,
    output_path: Path,
    bbox: list[int] = [120, 3, 147, 52],
):
    """
    Generate an A/B comparison board showing:
    1. Full-plate crops (3x scale) for Reference, Baseline, and Ablation.
    2. Zoomed-in glyph region around order-2 bbox to evaluate the rectangular patch.
    3. Bottom text legend with exact prompts.
    """
    scale_full = 3
    h, w = ref_orig.shape[:2]
    disp_w = w * scale_full
    disp_h = h * scale_full

    col1 = cv2.resize(ref_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col2 = cv2.resize(baseline_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col3 = cv2.resize(ablation_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)

    c1 = render_header_card(col1, "1. Reference: 东泰168")
    c2 = render_header_card(col2, "2. Baseline (Prompt: 'ship license plate')")
    c3 = render_header_card(col3, "3. Ablation (Prompt: 'painted hull')")
    row_full = np.hstack([c1, c2, c3])

    # Zoomed-in crop around order-2 glyph
    pad_x = 18
    x1 = max(0, bbox[0] - pad_x)
    x2 = min(w, bbox[2] + pad_x)
    y1 = 0
    y2 = h

    crop_ref = ref_orig[y1:y2, x1:x2]
    crop_base = baseline_orig[y1:y2, x1:x2]
    crop_ab = ablation_orig[y1:y2, x1:x2]

    target_crop_w = row_full.shape[1] // 3
    crop_scale = target_crop_w / (x2 - x1)
    target_crop_h = int(round((y2 - y1) * crop_scale))

    z1_img = cv2.resize(crop_ref, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)
    z2_img = cv2.resize(crop_base, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)
    z3_img = cv2.resize(crop_ab, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)

    z1 = render_header_card(z1_img, "Reference Glyph '1' (Zoomed Detail)")
    z2 = render_header_card(z2_img, "Baseline Glyph '2' (Check Rectangular Border)")
    z3 = render_header_card(z3_img, "Ablation Glyph '2' (Check Rectangular Border)")
    row_zoom = np.hstack([z1, z2, z3])

    # Text legend at bottom
    banner_w = row_full.shape[1]
    banner_h = 100
    banner = np.full((banner_h, banner_w, 3), (25, 25, 25), dtype=np.uint8)
    banner_pil = Image.fromarray(cv2.cvtColor(banner, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(banner_pil)
    font = None
    for fc in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/home/kyrie/.local/share/fonts/kymcm-lite/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]:
        if os.path.exists(fc):
            try:
                font = ImageFont.truetype(fc, 15)
                break
            except Exception:
                pass
    if font is not None:
        draw.text((15, 10), f"[Baseline Prompt]: {baseline_prompt}", font=font, fill=(180, 200, 255))
        draw.text((15, 40), f"[Ablation Prompt]: {ablation_prompt}", font=font, fill=(160, 255, 180))
        draw.text((15, 70), f"[Controlled Variable]: img_prompt only (Seed=2026, Steps=20, CFG=7.5, Strength=1.0, FontMimic=Off)", font=font, fill=(200, 200, 200))
    banner = cv2.cvtColor(np.array(banner_pil), cv2.COLOR_RGB2BGR)

    sep1 = np.full((12, banner_w, 3), (15, 15, 15), dtype=np.uint8)
    sep2 = np.full((12, banner_w, 3), (15, 15, 15), dtype=np.uint8)

    final_board = np.vstack([row_full, sep1, row_zoom, sep2, banner])
    cv2.imwrite(str(output_path), final_board)
    print(f"Saved prompt A/B comparison board: {output_path} ({final_board.shape[1]}x{final_board.shape[0]})")


def create_font_mimic_ab_comparison_board(
    ref_orig: np.ndarray,
    baseline_orig: np.ndarray,
    font_mimic_orig: np.ndarray,
    output_path: Path,
    bbox: list[int] = [120, 3, 147, 52],
):
    """
    Generate Font Mimic A/B comparison board showing:
    1. Full-plate crops (3x scale) for:
       - 1. Reference: 东泰168
       - 2. Condition A: Painted Hull + Font Mimic OFF
       - 3. Condition B: Painted Hull + Font Mimic ON
    2. Zoomed-in glyph region around order-2 bbox (6x scale):
       - Reference Source Glyph '1' (Style Hint)
       - Condition A Glyph '2' (Font Mimic OFF)
       - Condition B Glyph '2' (Font Mimic ON)
    3. Bottom text legend with hypothesis, conditions, and parameter verification.
    """
    scale_full = 3
    h, w = ref_orig.shape[:2]
    disp_w = w * scale_full
    disp_h = h * scale_full

    col1 = cv2.resize(ref_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col2 = cv2.resize(baseline_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)
    col3 = cv2.resize(font_mimic_orig, (disp_w, disp_h), interpolation=cv2.INTER_NEAREST)

    c1 = render_header_card(col1, "1. Reference: 东泰168")
    c2 = render_header_card(col2, "2. Condition A (Font Mimic OFF)")
    c3 = render_header_card(col3, "3. Condition B (Font Mimic ON)")
    row_full = np.hstack([c1, c2, c3])

    # Zoomed-in crop around order-2 glyph
    pad_x = 18
    x1 = max(0, bbox[0] - pad_x)
    x2 = min(w, bbox[2] + pad_x)
    y1 = 0
    y2 = h

    crop_ref = ref_orig[y1:y2, x1:x2]
    crop_base = baseline_orig[y1:y2, x1:x2]
    crop_fm = font_mimic_orig[y1:y2, x1:x2]

    target_crop_w = row_full.shape[1] // 3
    crop_scale = target_crop_w / (x2 - x1)
    target_crop_h = int(round((y2 - y1) * crop_scale))

    z1_img = cv2.resize(crop_ref, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)
    z2_img = cv2.resize(crop_base, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)
    z3_img = cv2.resize(crop_fm, (target_crop_w, target_crop_h), interpolation=cv2.INTER_NEAREST)

    z1 = render_header_card(z1_img, "Reference Source Glyph '1' (Style Hint)")
    z2 = render_header_card(z2_img, "Condition A: Glyph '2' (Font Mimic OFF)")
    z3 = render_header_card(z3_img, "Condition B: Glyph '2' (Font Mimic ON)")
    row_zoom = np.hstack([z1, z2, z3])

    # Text legend at bottom
    banner_w = row_full.shape[1]
    banner_h = 100
    banner = np.full((banner_h, banner_w, 3), (25, 25, 25), dtype=np.uint8)
    banner_pil = Image.fromarray(cv2.cvtColor(banner, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(banner_pil)
    font = None
    for fc in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/home/kyrie/.local/share/fonts/kymcm-lite/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    ]:
        if os.path.exists(fc):
            try:
                font = ImageFont.truetype(fc, 15)
                break
            except Exception:
                pass
    if font is not None:
        draw.text((15, 10), "[Hypothesis]: Can native Font Mimic improve stroke/style consistency when source hint is glyph '1'?", font=font, fill=(255, 220, 160))
        draw.text((15, 40), "[Condition A]: Painted Hull Prompt, Font Mimic OFF", font=font, fill=(180, 200, 255))
        draw.text((15, 70), "[Condition B]: Painted Hull Prompt, Font Mimic ON (Hint Image: 512x512 Ref, Hint Mask: Order-2 Glyph '1')", font=font, fill=(160, 255, 180))
    banner = cv2.cvtColor(np.array(banner_pil), cv2.COLOR_RGB2BGR)

    sep1 = np.full((12, banner_w, 3), (15, 15, 15), dtype=np.uint8)
    sep2 = np.full((12, banner_w, 3), (15, 15, 15), dtype=np.uint8)

    final_board = np.vstack([row_full, sep1, row_zoom, sep2, banner])
    cv2.imwrite(str(output_path), final_board)
    print(f"Saved Font Mimic A/B comparison board: {output_path} ({final_board.shape[1]}x{final_board.shape[0]})")


def main():
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("SynSLP: Order-Based Single-Character Edit (东泰168 -> 东泰268)")
    print("=" * 65)

    # 1. Load canonical human annotation and select order 2
    record = load_annotation(args.annotations.resolve(), args.image)
    orig_w = record["width"]
    orig_h = record["height"]
    total_px = orig_w * orig_h

    print(f"\n[Step 1] Loading Human GT Annotation...")
    print(f"  Image:      {record['image']} ({orig_w}x{orig_h})")
    print(f"  Instances:  {len(record.get('instances', []))}")

    mask_img, matched_boxes = generate_mask_for_orders(record, [args.order])
    assert len(matched_boxes) == 1, f"Expected 1 box for order {args.order}, got {len(matched_boxes)}"
    ord_val, src_text, bbox = matched_boxes[0]
    expected_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

    mask_orig = np.array(mask_img, dtype=np.uint8)
    active_px = int(np.sum(mask_orig > 0))
    pct = (active_px / total_px) * 100

    print(f"  Selected:   Order {ord_val}, text='{src_text}', bbox={bbox}")
    print(f"  Target Text: '{args.replacement_text}' (Replacement for glyph '{src_text}')")
    print(f"  Active Pixels: {active_px}/{total_px} ({pct:.2f}%), expected {expected_area}px")
    assert active_px == expected_area, f"Active pixel mismatch: {active_px} vs expected {expected_area}"

    # 2. Locate and load reference image
    ref_file = (ROOT_DIR / args.image).resolve()
    if not ref_file.exists():
        # Fallback to server path if on server
        ref_file = Path("/mnt/data/zyx/SynSLP") / args.image

    if not ref_file.exists():
        raise FileNotFoundError(f"Reference image not found: {ref_file}")

    ref_orig = cv2.imread(str(ref_file))
    if ref_orig is None:
        raise ValueError(f"Failed to read reference image: {ref_file}")

    # 3. Create aspect-ratio-preserving 512x512 black letterbox
    print(f"\n[Step 2] Creating 512x512 Aspect-Ratio-Preserving Black Letterbox...")
    ref_512, mask_512, geo_info = create_letterbox(ref_orig, mask_orig, target_size=512)

    print(f"  Scale Factor: {geo_info['scale']:.6f} ({orig_w}x{orig_h} -> {geo_info['new_w']}x{geo_info['new_h']})")
    print(f"  Padding:      offset_x={geo_info['pad_x']}, offset_y={geo_info['pad_y']}")
    active_512 = int(np.sum(mask_512 > 0))
    print(f"  Mask 512x512 Active Pixels: {active_512} ({(active_512 / (512 * 512)) * 100:.2f}%)")

    # Save review copies of inputs
    ref_orig_path = output_dir / f"reference_original{ref_file.suffix}"
    mask_orig_path = output_dir / "mask_order2_original.png"
    ref_512_path = output_dir / "reference_letterbox_512.png"
    mask_512_path = output_dir / "mask_order2_letterbox_512.png"

    shutil.copy2(ref_file, ref_orig_path)
    cv2.imwrite(str(mask_orig_path), mask_orig)
    cv2.imwrite(str(ref_512_path), ref_512)
    cv2.imwrite(str(mask_512_path), mask_512)

    # 4. AnyText2 Server Model Execution
    print(f"\n[Step 3] Initializing AnyText2 Model...")
    anytext2_dir = ROOT_DIR / "third_party" / "AnyText2"
    if not anytext2_dir.exists():
        raise FileNotFoundError(f"AnyText2 directory not found at {anytext2_dir}")

    sys.path.insert(0, str(anytext2_dir))
    curr_cwd = os.getcwd()
    os.chdir(str(anytext2_dir))

    from ms_wrapper import AnyText2Model

    t_load_start = time.time()
    model = AnyText2Model(
        model_dir="./models",
        use_fp16=True,
        use_translator=False,
        font_path="font/Arial_Unicode.ttf",
        model_path="models/anytext_v2.0.ckpt",
    ).cuda(0)
    t_load = time.time() - t_load_start
    print(f"  -> AnyText2 loaded in {t_load:.2f}s (FP16, translator disabled)")

    # Define official-faithful parameters
    a_prompt = "best quality, extremely detailed,4k, HD, supper legible text,  clear text edges,  clear strokes, neat writing, no watermarks"
    n_prompt = "low-res, bad anatomy, extra digit, fewer digits, cropped, worst quality, low quality, watermark, unreadable text, messy words, distorted text, disorganized writing, advertising picture"
    img_prompt = args.img_prompt
    text_prompt = f'"{args.replacement_text}"'

    mask_512_3ch = cv2.cvtColor(mask_512, cv2.COLOR_GRAY2BGR)

    input_data = {
        "img_prompt": img_prompt,
        "text_prompt": text_prompt,
        "seed": args.seed,
        "draw_pos": mask_512_3ch,
        "ori_image": ref_512[..., ::-1],  # BGR to RGB
    }

    forward_params = {
        "mode": "edit",
        "sort_priority": "↔",
        "show_debug": True,
        "revise_pos": False,
        "image_count": 1,
        "ddim_steps": args.ddim_steps,
        "image_width": 512,
        "image_height": 512,
        "strength": args.strength,
        "attnx_scale": 1.0,
        "font_hollow": False,
        "cfg_scale": args.cfg_scale,
        "eta": 0.0,
        "a_prompt": a_prompt,
        "n_prompt": n_prompt,
        "base_model_path": "",
        "lora_path_ratio": "",
        "glyline_font_path": ["None"] * 5,
        "text_colors": "500,500,500 500,500,500 500,500,500 500,500,500 500,500,500",
        "font_hint_image": [ref_512[..., ::-1], None, None, None, None] if args.font_mimic else [None] * 5,
        "font_hint_mask": [mask_512, None, None, None, None] if args.font_mimic else [None] * 5,
    }

    print("\n[Step 4] Running AnyText2 Edit Inference...")
    print(f"  Mode:           edit")
    print(f"  Target Prompt:  {text_prompt}")
    print(f"  Img Prompt:     '{img_prompt}'")
    print(f"  CFG Scale:      {args.cfg_scale}")
    print(f"  DDIM Steps:     {args.ddim_steps}")
    print(f"  Strength:       {args.strength}")
    print(f"  Seed:           {args.seed}")
    print(f"  Font Mimic:     {'ENABLED (Source Hint: glyph ' + src_text + ')' if args.font_mimic else 'DISABLED'}")

    import torch

    t_infer_start = time.time()
    with torch.no_grad():
        results, rtn_code, rtn_warning, debug_info = model(input_data, **forward_params)
    t_infer = time.time() - t_infer_start
    print(f"  -> Inference completed in {t_infer:.2f}s (rtn_code={rtn_code})")
    if rtn_warning:
        print(f"  -> Warning: {rtn_warning}")
    if rtn_code < 0:
        raise RuntimeError(f"AnyText2 inference failed: {rtn_warning}")

    os.chdir(curr_cwd)

    # 5. Process outputs and reverse letterbox
    out_512_rgb = results[0]
    out_512_bgr = out_512_rgb[..., ::-1]

    out_512_path = output_dir / ("font_mimic_output_512.png" if args.font_mimic else "output_512.png")
    cv2.imwrite(str(out_512_path), out_512_bgr)
    if args.font_mimic:
        shutil.copy2(out_512_path, output_dir / "output_512.png")
    print(f"\n[Step 5] Saved 512x512 Output: {out_512_path}")

    # If debug glyph control image is present
    if len(results) > 1 and results[1] is not None:
        glyph_debug_bgr = results[1][..., ::-1]
        cv2.imwrite(str(output_dir / "glyph_control_debug_512.png"), glyph_debug_bgr)
        print(f"  -> Saved glyph control debug image: {output_dir / 'glyph_control_debug_512.png'}")

    # Invert letterbox back to original 239x57
    out_orig_bgr = invert_letterbox(out_512_bgr, geo_info)
    out_orig_path = output_dir / ("font_mimic_output_crop_original_res.png" if args.font_mimic else "output_crop_original_res.png")
    cv2.imwrite(str(out_orig_path), out_orig_bgr)
    if args.font_mimic:
        shutil.copy2(out_orig_path, output_dir / "output_crop_original_res.png")
    print(f"  -> Inverted Letterbox Crop: {out_orig_path} ({out_orig_bgr.shape[1]}x{out_orig_bgr.shape[0]})")

    # 6. Generate Side-by-Side Comparison Board
    comp_path = output_dir / "comparison.png"
    create_comparison_board(
        ref_orig=ref_orig,
        mask_orig=mask_orig,
        out_orig=out_orig_bgr,
        ref_512=ref_512,
        mask_512=mask_512,
        out_512=out_512_bgr,
        output_path=comp_path,
    )

    ab_comp_name = None
    if args.baseline_crop and Path(args.baseline_crop).exists():
        baseline_crop_path = Path(args.baseline_crop).resolve()
        baseline_orig_img = cv2.imread(str(baseline_crop_path))
        if baseline_orig_img is not None:
            if args.font_mimic:
                ab_comp_path = output_dir / "comparison_font_mimic_ab.png"
                create_font_mimic_ab_comparison_board(
                    ref_orig=ref_orig,
                    baseline_orig=baseline_orig_img,
                    font_mimic_orig=out_orig_bgr,
                    output_path=ab_comp_path,
                    bbox=bbox,
                )
            else:
                ab_comp_path = output_dir / "comparison_prompt_ab.png"
                create_prompt_ab_comparison_board(
                    ref_orig=ref_orig,
                    baseline_orig=baseline_orig_img,
                    ablation_orig=out_orig_bgr,
                    baseline_prompt=args.baseline_prompt,
                    ablation_prompt=img_prompt,
                    output_path=ab_comp_path,
                    bbox=bbox,
                )
            ab_comp_name = str(ab_comp_path.name)

    # 7. Write metadata
    task_name = "single_glyph_font_mimic_ablation" if args.font_mimic else ("single_character_edit_prompt_ablation" if ab_comp_name else "single_character_edit")
    metadata = {
        "task": task_name,
        "reference_image": str(args.image),
        "original_dimensions": [orig_w, orig_h],
        "selected_order": args.order,
        "source_glyph": src_text,
        "replacement_glyph": args.replacement_text,
        "bbox": bbox,
        "active_pixels_original": active_px,
        "active_percentage_original": pct,
        "letterbox_scale": geo_info["scale"],
        "letterbox_padding": [geo_info["pad_x"], geo_info["pad_y"]],
        "letterbox_dimensions": [512, 512],
        "inference_time_seconds": round(t_infer, 3),
        "parameters": {
            "mode": "edit",
            "seed": args.seed,
            "ddim_steps": args.ddim_steps,
            "strength": args.strength,
            "cfg_scale": args.cfg_scale,
            "img_prompt": img_prompt,
            "text_prompt": text_prompt,
            "a_prompt": a_prompt,
            "n_prompt": n_prompt,
            "font_mimic": args.font_mimic,
        },
        "output_files": {
            "reference_original": str(ref_orig_path.name),
            "mask_order2_original": str(mask_orig_path.name),
            "reference_letterbox_512": str(ref_512_path.name),
            "mask_order2_letterbox_512": str(mask_512_path.name),
            "output_512": str(out_512_path.name),
            "output_crop_original_res": str(out_orig_path.name),
            "comparison": str(comp_path.name),
        },
    }

    if args.font_mimic:
        metadata["font_hint_details"] = {
            "source_order": args.order,
            "source_glyph": src_text,
            "active_slot": 0,
            "font_hint_image_shape": [512, 512, 3],
            "font_hint_image_dtype": "uint8",
            "font_hint_image_channels": "RGB",
            "font_hint_mask_shape": [512, 512],
            "font_hint_mask_dtype": "uint8",
            "font_hint_mask_active_pixels": int(np.sum(mask_512 > 0)),
        }
        metadata["output_files"]["font_mimic_output_512"] = "font_mimic_output_512.png"
        metadata["output_files"]["font_mimic_output_crop_original_res"] = "font_mimic_output_crop_original_res.png"
        metadata["output_files"]["comparison_font_mimic_ab"] = "comparison_font_mimic_ab.png"

    if ab_comp_name:
        metadata["output_files"][ab_comp_name.replace(".png", "")] = ab_comp_name
        metadata["ablation_details"] = {
            "hypothesis": "Can AnyText2 native Font Mimic make generated 2 visually closer to original SLP glyph style when source hint is glyph 1?" if args.font_mimic else "Test if visible rectangular patch around generated digit is caused by physical license plate prior",
            "controlled_variable": "font_mimic (OFF -> ON)" if args.font_mimic else "img_prompt",
            "baseline_condition": "Painted Hull Prompt, Font Mimic OFF" if args.font_mimic else args.baseline_prompt,
            "ablation_condition": "Painted Hull Prompt, Font Mimic ON" if args.font_mimic else img_prompt,
            "frozen_parameters_identical_proof": {
                "seed": args.seed == 2026,
                "ddim_steps": args.ddim_steps == 20,
                "strength": args.strength == 1.0,
                "cfg_scale": args.cfg_scale == 7.5,
                "order": args.order == 2,
                "bbox": bbox == [120, 3, 147, 52],
            },
        }

    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved run metadata: {meta_path}")

    print("\n" + "=" * 65)
    print("SUCCESS: Single-character edit (东泰168 -> 东泰268) complete.")
    print("=" * 65)


if __name__ == "__main__":
    main()
