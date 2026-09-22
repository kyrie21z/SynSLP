#!/usr/bin/env python3
"""
SynSLP AnyText2 Single-Image Edit Strength Tuning

Target: Find a usable AnyText2 edit configuration for exactly one representative
tight-crop SLP by isolating a single variable: edit strength (0.3, 0.5, 0.7, 1.0).

Inputs:
- Reference: /mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg
- Mask:      /mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png
- Target:    苏航268
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
import numpy as np
import cv2
import torch


def parse_args():
    parser = argparse.ArgumentParser(description="AnyText2 Edit Strength Tuning")
    parser.add_argument(
        "--ref_image",
        type=str,
        default="/mnt/data/zyx/SynSLP/reference/easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.jpg",
        help="Path to reference image",
    )
    parser.add_argument(
        "--mask_image",
        type=str,
        default="/mnt/data/zyx/SynSLP/mask/mask_easy&single&ng&nd&东泰168&8&1&T_20220519_11_29_59_740944.png",
        help="Path to mask image",
    )
    parser.add_argument("--target_text", type=str, default="苏航268")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--ddim_steps", type=int, default=20)
    parser.add_argument("--cfg_scale", type=float, default=9.0)
    parser.add_argument("--render_w", type=int, default=512)
    parser.add_argument("--render_h", type=int, default=128)
    parser.add_argument(
        "--output_dir",
        type=str,
        default="/mnt/data/zyx/SynSLP/outputs/single_image_tuning/dongtai168",
    )
    parser.add_argument("--device", type=str, default="cuda:0")
    return parser.parse_args()


def validate_inputs(ref_path: Path, mask_path: Path):
    print("=" * 60)
    print("Step 1: Validating Fixed Inputs")
    print("=" * 60)

    if not ref_path.exists():
        raise FileNotFoundError(f"Reference image not found: {ref_path}")
    if not mask_path.exists():
        raise FileNotFoundError(f"Mask image not found: {mask_path}")

    ref_bgr = cv2.imread(str(ref_path))
    if ref_bgr is None:
        raise ValueError(f"Failed to read reference image: {ref_path}")

    mask_bgr = cv2.imread(str(mask_path))
    if mask_bgr is None:
        raise ValueError(f"Failed to read mask image: {mask_path}")

    ref_h, ref_w = ref_bgr.shape[:2]
    mask_h, mask_w = mask_bgr.shape[:2]

    print(f"Reference path:   {ref_path}")
    print(f"Reference shape:  ({ref_h}, {ref_w}, {ref_bgr.shape[2]})")
    print(f"Mask path:        {mask_path}")
    print(f"Mask shape:       ({mask_h}, {mask_w}, {mask_bgr.shape[2]})")

    if (ref_h, ref_w) != (mask_h, mask_w):
        raise ValueError(
            f"Dimension mismatch! Reference is ({ref_w}x{ref_h}) but mask is ({mask_w}x{mask_h})"
        )

    # Check mask values
    unique_vals = np.unique(mask_bgr)
    print(f"Mask unique values: {unique_vals.tolist()}")
    if not set(unique_vals).issubset({0, 255}):
        print(f"WARNING: Mask contains non-binary values: {unique_vals}")

    editable_pixels = np.sum(mask_bgr[..., 0] > 0)
    total_pixels = ref_h * ref_w
    pct = (editable_pixels / total_pixels) * 100
    print(f"Editable text pixels (value 255): {editable_pixels}/{total_pixels} ({pct:.2f}%)")
    print("Input validation: PASS")

    return ref_bgr, mask_bgr, (ref_w, ref_h)


def create_comparison_grid(
    items: list,
    output_path: Path,
    img_size: tuple = None,
):
    """
    Creates a clean vertically stacked comparison with text label headers.
    items: list of (label, bgr_image)
    """
    card_list = []
    target_w = items[0][1].shape[1] if img_size is None else img_size[0]
    target_h = items[0][1].shape[0] if img_size is None else img_size[1]
    header_h = 28

    for label, img in items:
        if img.shape[:2] != (target_h, target_w):
            rendered = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            rendered = img.copy()

        # Create header bar
        header = np.full((header_h, target_w, 3), (35, 35, 35), dtype=np.uint8)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6 if target_w >= 400 else 0.45
        thickness = 1
        text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        text_x = 12
        text_y = (header_h + text_size[1]) // 2
        cv2.putText(header, label, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

        card = np.vstack([header, rendered])
        card_list.append(card)

    separator = np.full((10, target_w, 3), (20, 20, 20), dtype=np.uint8)
    grid_rows = []
    for i, card in enumerate(card_list):
        grid_rows.append(card)
        if i < len(card_list) - 1:
            grid_rows.append(separator)

    final_grid = np.vstack(grid_rows)
    cv2.imwrite(str(output_path), final_grid)
    print(f"Saved comparison grid: {output_path} ({final_grid.shape[1]}x{final_grid.shape[0]})")


def main():
    args = parse_args()

    ref_path = Path(args.ref_image)
    mask_path = Path(args.mask_image)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Validate inputs
    ref_bgr, mask_bgr, orig_dims = validate_inputs(ref_path, mask_path)
    orig_w, orig_h = orig_dims

    # Copy reference and mask into experiment directory for inspection
    shutil.copy2(ref_path, output_dir / "reference.jpg")
    shutil.copy2(mask_path, output_dir / "mask.png")

    # 2. Setup AnyText2 inference environment
    root_dir = Path(__file__).resolve().parent.parent
    anytext2_dir = root_dir / "third_party" / "AnyText2"
    if not anytext2_dir.exists():
        raise FileNotFoundError(f"AnyText2 directory not found: {anytext2_dir}")

    sys.path.insert(0, str(anytext2_dir))
    os.chdir(str(anytext2_dir))

    print("\n" + "=" * 60)
    print("Step 2: Initializing AnyText2 Model")
    print("=" * 60)

    from ms_wrapper import AnyText2Model

    t_start_load = time.time()
    model = AnyText2Model(
        model_dir="./models",
        use_fp16=True,
        use_translator=False,
        font_path="font/Arial_Unicode.ttf",
        model_path="models/anytext_v2.0.ckpt",
    ).cuda(0)
    t_load = time.time() - t_start_load
    print(f"AnyText2Model loaded on GPU in {t_load:.2f}s (FP16 mode, translator disabled).")

    # In-memory deterministic resolution adaptation to valid SD multiple of 64
    render_w = args.render_w
    render_h = args.render_h
    print(f"\nResolution policy: Scaling in-memory from ({orig_w}x{orig_h}) to ({render_w}x{render_h})")
    print(f"Original aspect ratio: {orig_w / orig_h:.3f}, Render aspect ratio: {render_w / render_h:.3f}")

    ref_rgb_scaled = cv2.resize(ref_bgr[..., ::-1], (render_w, render_h), interpolation=cv2.INTER_LANCZOS4)
    mask_scaled = cv2.resize(mask_bgr, (render_w, render_h), interpolation=cv2.INTER_NEAREST)

    # Fixed generation parameters across all runs
    strengths = [0.3, 0.5, 0.7, 1.0]
    fixed_base_params = {
        "mode": "edit",
        "sort_priority": "↔",
        "show_debug": False,
        "revise_pos": False,
        "image_count": 1,
        "ddim_steps": args.ddim_steps,
        "image_width": render_w,
        "image_height": render_h,
        "attnx_scale": 1.0,
        "font_hollow": False,
        "cfg_scale": args.cfg_scale,
        "eta": 0.0,
        "a_prompt": "a Chinese ship license plate, blue background, white clean text, realistic photo",
        "n_prompt": "low quality, blurry, noisy",
        "base_model_path": "",
        "lora_path_ratio": "",
        "glyline_font_path": ["None"] * 5,
        "font_hint_image": [None] * 5,
        "font_hint_mask": [None] * 5,
        "text_colors": "500,500,500 500,500,500 500,500,500 500,500,500 500,500,500",
    }

    input_data = {
        "img_prompt": "a Chinese ship license plate",
        "text_prompt": f'"{args.target_text}"',
        "seed": args.seed,
        "draw_pos": mask_scaled,
        "ori_image": ref_rgb_scaled,
    }

    print("\n" + "=" * 60)
    print(f"Step 3: Running 4 Edit Strength Values {strengths}")
    print(f"Target Text:    \"{args.target_text}\"")
    print(f"Fixed Seed:     {args.seed}")
    print(f"Fixed Steps:    {args.ddim_steps}")
    print(f"Fixed CFG:      {args.cfg_scale}")
    print("=" * 60)

    results_for_comparison = [("Reference (东泰168)", ref_bgr)]
    timing_records = {}

    for s in strengths:
        print(f"\n---> Running strength = {s} ...")
        curr_params = dict(fixed_base_params)
        curr_params["strength"] = s

        t0 = time.time()
        with torch.no_grad():
            results, rtn_code, rtn_warning, _ = model(input_data, **curr_params)
        elapsed = time.time() - t0
        timing_records[s] = elapsed

        if rtn_code < 0:
            raise RuntimeError(f"Inference failed for strength {s}: {rtn_warning}")

        out_bgr_512 = results[0][..., ::-1]
        out_path_512 = output_dir / f"strength_{s}.png"
        cv2.imwrite(str(out_path_512), out_bgr_512)

        # Scale back to original resolution (57x239)
        out_bgr_orig = cv2.resize(out_bgr_512, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
        out_path_orig = output_dir / f"strength_{s}_orig_res.png"
        cv2.imwrite(str(out_path_orig), out_bgr_orig)

        results_for_comparison.append((f"Strength {s} (Elapsed: {elapsed:.2f}s)", out_bgr_512))
        print(f"PASS: strength={s} finished in {elapsed:.2f}s")
        print(f"Saved: {out_path_512} ({render_w}x{render_h})")
        print(f"Saved: {out_path_orig} ({orig_w}x{orig_h})")

    # 4. Create comparison grids
    print("\n" + "=" * 60)
    print("Step 4: Creating Comparison Grids")
    print("=" * 60)

    grid_path_512 = output_dir / "comparison_grid.png"
    create_comparison_grid(results_for_comparison, grid_path_512, (render_w, render_h))

    orig_comparison = [(item[0], cv2.resize(item[1], (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4) if item[1].shape[:2] != (orig_h, orig_w) else item[1]) for item in results_for_comparison]
    grid_path_orig = output_dir / "comparison_grid_orig_res.png"
    create_comparison_grid(orig_comparison, grid_path_orig, (orig_w, orig_h))

    # Summary table
    print("\n" + "=" * 60)
    print("Summary of Tuning Execution")
    print("=" * 60)
    print(f"Target Text:       {args.target_text}")
    print(f"Seed:              {args.seed}")
    print(f"Steps:             {args.ddim_steps}")
    print(f"CFG Scale:         {args.cfg_scale}")
    print(f"Resolution Policy: {orig_w}x{orig_h} -> {render_w}x{render_h} (diffusion) -> {orig_w}x{orig_h}")
    for s in strengths:
        print(f"  strength={s:3.1f}: {timing_records[s]:.2f}s -> {output_dir}/strength_{s}.png")
    print(f"Comparison Grid:   {grid_path_512}")
    print("TUNING COMPLETED SUCCESSFULLY")


if __name__ == "__main__":
    main()
