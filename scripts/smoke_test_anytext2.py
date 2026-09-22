#!/usr/bin/env python3
"""
SynSLP AnyText2 Minimal Deployment Acceptance Test (Stage 4)

Verifies:
1. AnyText2 checkpoint loads successfully.
2. CUDA inference runs successfully.
3. A stock/example inference produces an output image.
4. One Chinese ship-license-plate-oriented reference edit smoke test succeeds.
"""

import os
import sys
import time
import argparse
from pathlib import Path
import numpy as np
import cv2
import torch

def parse_args():
    parser = argparse.ArgumentParser(description="AnyText2 Stage 4 Acceptance Smoke Test")
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--ddim_steps", type=int, default=20)
    parser.add_argument("--output_dir", type=str, default=None)
    parser.add_argument("--slp_ref_image", type=str, default=None)
    return parser.parse_args()

def main():
    args = parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    anytext2_dir = root_dir / "third_party" / "AnyText2"
    if not anytext2_dir.exists():
        raise FileNotFoundError(f"AnyText2 directory not found: {anytext2_dir}")

    output_dir = Path(args.output_dir) if args.output_dir else root_dir / "outputs" / "smoke_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(anytext2_dir))
    os.chdir(str(anytext2_dir))

    print("=" * 60)
    print("SynSLP AnyText2 Deployment Acceptance Test")
    print("=" * 60)

    # 1. Environment and Hardware Inspection
    print("[1/5] Inspecting environment and GPU...")
    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        raise SystemExit("ERROR: CUDA is not available.")

    gpu_name = torch.cuda.get_device_name(0)
    vram_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    vram_free = torch.cuda.mem_get_info()[0] / (1024 ** 3)
    print(f"GPU: {gpu_name}")
    print(f"Total VRAM: {vram_total:.2f} GB | Free VRAM: {vram_free:.2f} GB")

    # 2. Check 1 & 2: Load Model and Checkpoint
    print("\n[2/5] Check 1 & 2: Loading AnyText2 checkpoint on GPU...")
    from ms_wrapper import AnyText2Model
    from util import check_channels, resize_image

    ckpt_path = anytext2_dir / "models" / "anytext_v2.0.ckpt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    start_time = time.time()
    model = AnyText2Model(
        model_dir=str(anytext2_dir / "models"),
        use_fp16=True,
        use_translator=False,
        font_path="font/Arial_Unicode.ttf",
        model_path=str(ckpt_path),
    ).cuda(0)
    load_time = time.time() - start_time
    print(f"PASS: AnyText2Model loaded in {load_time:.2f}s (FP16, translator disabled).")

    # Common inference parameters
    a_prompt = "best quality, extremely detailed, 4k, HD, legible text, clear text, high-resolution"
    n_prompt = "low quality, blurry, deformed text"

    # 3. Check 3: Stock Example Inference
    print("\n[3/5] Check 3: Running stock example inference...")
    stock_ref = anytext2_dir / "example_images" / "ref2.jpg"
    stock_edit = anytext2_dir / "example_images" / "edit2.png"
    if not stock_ref.exists() or not stock_edit.exists():
        raise FileNotFoundError(f"Missing stock example files in {anytext2_dir / 'example_images'}")

    ori_stock_img = cv2.imread(str(stock_ref))[..., ::-1]
    ref_stock_img = cv2.imread(str(stock_edit))[..., ::-1]

    # Mask in AnyText2 demo: 255 - edit_image
    pos_stock = (255 - ref_stock_img).clip(0, 255).astype(np.uint8)

    stock_params = {
        "mode": "edit",
        "sort_priority": "left-to-right",
        "show_debug": False,
        "revise_pos": False,
        "image_count": 1,
        "ddim_steps": args.ddim_steps,
        "image_width": 768,
        "image_height": 768,
        "strength": 1.0,
        "attnx_scale": 1.0,
        "font_hollow": False,
        "cfg_scale": 9.0,
        "eta": 0.0,
        "a_prompt": a_prompt,
        "n_prompt": n_prompt,
        "base_model_path": "",
        "lora_path_ratio": "",
        "glyline_font_path": ["None"] * 5,
        "font_hint_image": [None] * 5,
        "font_hint_mask": [None] * 5,
        "text_colors": "500,500,500 500,500,500 500,500,500 500,500,500 500,500,500",
    }
    stock_input = {
        "img_prompt": "a cartoon pig expression",
        "text_prompt": '"下班"',
        "seed": 43304008,
        "draw_pos": pos_stock,
        "ori_image": ori_stock_img,
    }

    t0 = time.time()
    with torch.no_grad():
        stock_results, rtn_code, rtn_warning, _ = model(stock_input, **stock_params)
    t_stock = time.time() - t0

    if rtn_code < 0:
        raise RuntimeError(f"Stock example inference failed: {rtn_warning}")

    stock_output_path = output_dir / "stock_example_result.png"
    cv2.imwrite(str(stock_output_path), stock_results[0][..., ::-1])
    print(f"PASS: Stock example inference generated in {t_stock:.2f}s.")
    print(f"Saved to: {stock_output_path}")

    # 4. Check 4: Chinese Ship License Plate Reference Edit
    print("\n[4/5] Check 4: Chinese ship-license-plate reference edit smoke test...")
    slp_img_path = None
    candidate_paths = [
        args.slp_ref_image,
        "/mnt/data/zyx/SLP34K/ocr_training/data/pairs/target_2_High_quality_categorized/7755/O_20190510_13_26_50_516000.jpg&&&&7755&&&&5-浙绍兴货0668.jpg",
    ]
    for p in candidate_paths:
        if p and Path(p).exists():
            slp_img_path = Path(p)
            break

    if slp_img_path is not None:
        print(f"Using SLP reference plate from: {slp_img_path}")
        plate_bgr = cv2.imread(str(slp_img_path))
    else:
        print("Creating synthetic blue ship license plate template...")
        plate_bgr = np.full((128, 768, 3), (180, 80, 20), dtype=np.uint8)  # blue plate BGR

    # Pad/resize plate to valid dimensions for diffusion (multiple of 64)
    ph, pw = plate_bgr.shape[:2]
    # Resize to standard height 128, width 768
    plate_rgb = cv2.resize(plate_bgr, (768, 128))[..., ::-1]

    # Create mask: white rectangle covering text area
    pos_slp = np.zeros((128, 768, 3), dtype=np.uint8)
    pos_slp[20:108, 60:708, :] = 255  # Text region mask

    target_chinese_text = "皖宣城货0188"
    slp_params = {
        "mode": "edit",
        "sort_priority": "left-to-right",
        "show_debug": False,
        "revise_pos": False,
        "image_count": 1,
        "ddim_steps": args.ddim_steps,
        "image_width": 768,
        "image_height": 128,
        "strength": 1.0,
        "attnx_scale": 1.0,
        "font_hollow": False,
        "cfg_scale": 9.0,
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
    slp_input = {
        "img_prompt": "a Chinese ship license plate",
        "text_prompt": f'"{target_chinese_text}"',
        "seed": 2026,
        "draw_pos": pos_slp,
        "ori_image": plate_rgb,
    }

    t0 = time.time()
    with torch.no_grad():
        slp_results, rtn_code, rtn_warning, _ = model(slp_input, **slp_params)
    t_slp = time.time() - t0

    if rtn_code < 0:
        raise RuntimeError(f"SLP edit inference failed: {rtn_warning}")

    slp_output_path = output_dir / "slp_reference_edit_result.png"
    cv2.imwrite(str(slp_output_path), slp_results[0][..., ::-1])
    print(f"PASS: Chinese SLP reference edit generated in {t_slp:.2f}s.")
    print(f"Target text: {target_chinese_text}")
    print(f"Saved to: {slp_output_path}")

    # 5. Summary and Acceptance Sign-off
    print("\n[5/5] Stage 4 Acceptance Test Summary")
    print("-" * 40)
    print(f"GPU: {gpu_name} (Total: {vram_total:.2f} GB)")
    print(f"Stock output: {stock_output_path} (exists={stock_output_path.exists()})")
    print(f"SLP output:   {slp_output_path} (exists={slp_output_path.exists()})")
    print(f"Peak VRAM used: {torch.cuda.max_memory_allocated() / (1024**3):.2f} GB")
    print("-" * 40)
    print("STAGE 4 VERIFIED: ALL CHECKS PASSED (PASS)")

if __name__ == "__main__":
    main()
