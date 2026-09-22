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
from PIL import Image

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
    # Convert mask to 3-channel
    mask_orig_3ch = cv2.cvtColor(mask_orig, cv2.COLOR_GRAY2BGR)
    mask_512_3ch = cv2.cvtColor(mask_512, cv2.COLOR_GRAY2BGR)

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

    def add_card(img, label):
        header_h = 32
        card = np.full((img.shape[0] + header_h, img.shape[1], 3), (35, 35, 35), dtype=np.uint8)
        cv2.putText(card, label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
        card[header_h:, :] = img
        return card

    c1 = add_card(col1, "1. Reference (239x57 -> 东泰168)")
    c2 = add_card(col2, "2. Order-2 Edit Mask (Glyph '1')")
    c3 = add_card(col3, "3. Edited Output (239x57 -> 东泰268)")

    row_orig = np.hstack([c1, c2, c3])

    # 2. Letterbox 512 strip
    red_512 = ref_512.copy()
    red_512[mask_512 > 0] = [0, 0, 255]
    blend_512 = cv2.addWeighted(ref_512, 0.6, red_512, 0.4, 0)

    lb1 = add_card(ref_512, "Letterbox Reference (512x512)")
    lb2 = add_card(blend_512, "Letterbox Mask (Order 2)")
    lb3 = add_card(out_512, "AnyText2 Output (512x512)")

    # Resize letterbox cards to match row_orig width
    lb_combined = np.hstack([lb1, lb2, lb3])
    lb_resized = cv2.resize(lb_combined, (row_orig.shape[1], int(lb_combined.shape[0] * (row_orig.shape[1] / lb_combined.shape[1]))))

    sep = np.full((12, row_orig.shape[1], 3), (15, 15, 15), dtype=np.uint8)
    final_board = np.vstack([row_orig, sep, lb_resized])

    cv2.imwrite(str(output_path), final_board)
    print(f"Saved comparison board: {output_path} ({final_board.shape[1]}x{final_board.shape[0]})")


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
    img_prompt = "a realistic photo of a Chinese ship license plate"
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
        "font_hint_image": [None] * 5,
        "font_hint_mask": [None] * 5,
    }

    print("\n[Step 4] Running AnyText2 Edit Inference...")
    print(f"  Mode:           edit")
    print(f"  Target Prompt:  {text_prompt}")
    print(f"  Img Prompt:     '{img_prompt}'")
    print(f"  CFG Scale:      {args.cfg_scale}")
    print(f"  DDIM Steps:     {args.ddim_steps}")
    print(f"  Strength:       {args.strength}")
    print(f"  Seed:           {args.seed}")
    print(f"  Font Mimic:     DISABLED")

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

    out_512_path = output_dir / "output_512.png"
    cv2.imwrite(str(out_512_path), out_512_bgr)
    print(f"\n[Step 5] Saved 512x512 Output: {out_512_path}")

    # If debug glyph control image is present
    if len(results) > 1 and results[1] is not None:
        glyph_debug_bgr = results[1][..., ::-1]
        cv2.imwrite(str(output_dir / "glyph_control_debug_512.png"), glyph_debug_bgr)
        print(f"  -> Saved glyph control debug image: {output_dir / 'glyph_control_debug_512.png'}")

    # Invert letterbox back to original 239x57
    out_orig_bgr = invert_letterbox(out_512_bgr, geo_info)
    out_orig_path = output_dir / "output_crop_original_res.png"
    cv2.imwrite(str(out_orig_path), out_orig_bgr)
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

    # 7. Write metadata
    metadata = {
        "task": "single_character_edit",
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
            "font_mimic": False,
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

    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"Saved run metadata: {meta_path}")

    print("\n" + "=" * 65)
    print("SUCCESS: Single-character edit (东泰168 -> 东泰268) complete.")
    print("=" * 65)


if __name__ == "__main__":
    main()
