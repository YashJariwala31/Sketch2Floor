"""
Run batched inference on images and write door/window mask predictions.

Loads a trained U-Net checkpoint, iterates over images in `original/`, produces
door and window probability maps, thresholds/post-processes them, and saves
mask PNGs into `predictions/`.
"""

import argparse
import os
import random

import cv2
import numpy as np
import torch

try:
    import segmentation_models_pytorch as smp
except ModuleNotFoundError as e:
    raise SystemExit(
        "Missing dependency: segmentation_models_pytorch. "
        "Install it in your active environment, e.g. `python -m pip install segmentation-models-pytorch`."
    ) from e


def _configure_determinism(seed: int = 0) -> None:
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    cv2.setNumThreads(1)

    if hasattr(torch, "use_deterministic_algorithms"):
        torch.use_deterministic_algorithms(True, warn_only=True)

    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


_configure_determinism()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)


parser = argparse.ArgumentParser()
parser.add_argument("--image", type=str, default=None)
parser.add_argument("--door_thresh", type=float, default=0.85)
parser.add_argument("--window_thresh", type=float, default=0.85)
args = parser.parse_args()


INPUT_DIR = "original"
OUTPUT_DIR = os.environ.get("S2FP_PREDICTIONS_DIR", "predictions")
os.makedirs(OUTPUT_DIR, exist_ok=True)


model = smp.Unet(
    encoder_name="resnet18",
    encoder_weights=None,
    in_channels=3,
    classes=2,
).to(device)

model.load_state_dict(torch.load("models/fine_tuned_model.pth", map_location=device))
model.eval()


if args.image is not None:
    image_arg = args.image
    image_id = os.path.splitext(os.path.basename(image_arg))[0]

    if os.path.exists(image_arg) and os.path.isfile(image_arg):
        filepaths = [image_arg]
    else:
        candidates = [
            os.path.join(INPUT_DIR, f"{image_id}.jpeg"),
            os.path.join(INPUT_DIR, f"{image_id}.jpg"),
            os.path.join(INPUT_DIR, f"{image_id}.png"),
        ]
        filepaths = sorted(p for p in candidates if os.path.exists(p))
else:
    filepaths = [os.path.join(INPUT_DIR, f) for f in sorted(os.listdir(INPUT_DIR))]


def _save_required_mask(path, image, label):
    if not cv2.imwrite(path, image):
        raise RuntimeError(f"Failed to write {label} mask to {path}")

for filepath in filepaths:
    filename = os.path.basename(filepath)
    if not filename.lower().endswith((".jpeg", ".jpg", ".png")):
        continue

    print(f"\nProcessing: {filename}")

    img = cv2.imread(filepath)
    if img is None:
        raise FileNotFoundError(f"Failed to read input image: {filepath}")
    h, w = img.shape[:2]

    x = cv2.resize(img, (512, 512))
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB) / 255.0
    x = torch.tensor(x.transpose(2, 0, 1)).unsqueeze(0).float().to(device)

    with torch.inference_mode():
        pred = torch.sigmoid(model(x))[0].cpu().numpy()

    print("Door max:", pred[0].max())
    print("Window max:", pred[1].max())

    door = (pred[0] > float(args.door_thresh)).astype(np.uint8) * 255
    window = (pred[1] > float(args.window_thresh)).astype(np.uint8) * 255

    kernel = np.ones((3, 3), np.uint8)
    window = cv2.morphologyEx(window, cv2.MORPH_OPEN, kernel)

    num, labels, stats, _ = cv2.connectedComponentsWithStats(window)
    clean = np.zeros_like(window)

    component_ids = sorted(
        range(1, num),
        key=lambda index: (
            int(stats[index, cv2.CC_STAT_TOP]),
            int(stats[index, cv2.CC_STAT_LEFT]),
            int(stats[index, cv2.CC_STAT_AREA]),
            int(index),
        ),
    )

    for i in component_ids:
        comp = (labels == i).astype(np.uint8) * 255
        area = cv2.countNonZero(comp)

        if 50 < area < 5000:
            clean = cv2.bitwise_or(clean, comp)

    window = clean

    door = cv2.resize(door, (w, h))
    window = cv2.resize(window, (w, h))

    stem = os.path.splitext(filename)[0]
    _save_required_mask(f"{OUTPUT_DIR}/{stem}_door.png", door, "door")
    _save_required_mask(f"{OUTPUT_DIR}/{stem}_window.png", window, "window")


print("\nDone")
