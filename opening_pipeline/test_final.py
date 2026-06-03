"""
Run inference on images and write door/window mask predictions.
Supports both CLI usage and in-process calling via MaskGenerator for caching.
"""

import argparse
import gc
import os
import random
import cv2
import numpy as np
import torch
from pathlib import Path

try:
    import segmentation_models_pytorch as smp
except ModuleNotFoundError as e:
    # Only raise if we are actually trying to use the generator
    smp = None

_CACHED_GENERATOR = None

def _configure_determinism(seed: int = 0) -> None:
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    cv2.setNumThreads(1)

    if hasattr(torch, "use_deterministic_algorithms"):
        torch.use_deterministic_algorithms(True, warn_only=True)

    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

class MaskGenerator:
    def __init__(self, model_path="models/fine_tuned_model.pth", device=None):
        if smp is None:
            raise ImportError("segmentation_models_pytorch is required for MaskGenerator")

        _configure_determinism()
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Initializing MaskGenerator on {self.device}")

        self.model = smp.Unet(
            encoder_name="resnet18",
            encoder_weights=None,
            in_channels=3,
            classes=2,
        ).to(self.device)

        # Handle relative paths if called from different CWD
        if not os.path.isabs(model_path):
            possible_paths = [
                Path(model_path),
                Path(__file__).parent.parent / model_path,
                Path.cwd() / model_path
            ]
            for p in possible_paths:
                if p.exists():
                    model_path = str(p)
                    break

        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

        # Warm-up inference
        self.warmup()

    def warmup(self):
        """Perform a dummy inference to initialize CUDA kernels and internal buffers."""
        print("Warming up model...")
        dummy_input = torch.zeros((1, 3, 512, 512)).to(self.device)
        with torch.inference_mode():
            self.model(dummy_input)
        print("Warm-up complete.")

    def process_image(self, image_path, output_dir, door_thresh=0.85, window_thresh=0.85):
        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"Failed to read input image: {image_path}")
        h, w = img.shape[:2]

        x = cv2.resize(img, (512, 512))
        x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB) / 255.0
        x = torch.tensor(x.transpose(2, 0, 1)).unsqueeze(0).float().to(self.device)

        with torch.inference_mode():
            pred = torch.sigmoid(self.model(x))[0].cpu().numpy()

        door = (pred[0] > float(door_thresh)).astype(np.uint8) * 255
        window = (pred[1] > float(window_thresh)).astype(np.uint8) * 255

        # Post-processing
        kernel = np.ones((3, 3), np.uint8)
        window = cv2.morphologyEx(window, cv2.MORPH_OPEN, kernel)

        num, labels, stats, _ = cv2.connectedComponentsWithStats(window)
        clean = np.zeros_like(window)
        component_ids = sorted(range(1, num), key=lambda i: stats[i, cv2.CC_STAT_AREA], reverse=True)

        for i in component_ids:
            if 50 < stats[i, cv2.CC_STAT_AREA] < 5000:
                clean[labels == i] = 255
        window = clean

        door = cv2.resize(door, (w, h), interpolation=cv2.INTER_NEAREST)
        window = cv2.resize(window, (w, h), interpolation=cv2.INTER_NEAREST)

        os.makedirs(output_dir, exist_ok=True)
        stem = Path(image_path).stem
        door_path = os.path.join(output_dir, f"{stem}_door.png")
        window_path = os.path.join(output_dir, f"{stem}_window.png")

        cv2.imwrite(door_path, door)
        cv2.imwrite(window_path, window)
        del img, x, pred, door, window
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return door_path, window_path

def get_generator():
    global _CACHED_GENERATOR
    if _CACHED_GENERATOR is None:
        _CACHED_GENERATOR = MaskGenerator()
    return _CACHED_GENERATOR

def release_cached_generator():
    global _CACHED_GENERATOR
    _CACHED_GENERATOR = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default=os.environ.get("S2FP_PREDICTIONS_DIR", "predictions"))
    parser.add_argument("--door_thresh", type=float, default=0.85)
    parser.add_argument("--window_thresh", type=float, default=0.85)
    args = parser.parse_args()

    gen = MaskGenerator()
    gen.process_image(args.image, args.output_dir, args.door_thresh, args.window_thresh)
    print("Done")

if __name__ == "__main__":
    main()
