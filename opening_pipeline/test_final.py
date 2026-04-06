"""
Run batched inference on images and write door/window mask predictions.

Loads a trained U-Net checkpoint, iterates over images in `original/`, produces
door and window probability maps, thresholds/post-processes them, and saves
mask PNGs into `predictions/`.
"""

import argparse
import os, cv2, torch, numpy as np
try:
    import segmentation_models_pytorch as smp
except ModuleNotFoundError as e:
    raise SystemExit(
        "Missing dependency: segmentation_models_pytorch. "
        "Install it in your active environment, e.g. `python -m pip install segmentation-models-pytorch`."
    ) from e


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)


parser = argparse.ArgumentParser()
parser.add_argument('--image', type=str, default=None)
parser.add_argument('--door_thresh', type=float, default=0.85)
parser.add_argument('--window_thresh', type=float, default=0.85)
args = parser.parse_args()


INPUT_DIR = "original"
OUTPUT_DIR = "predictions"
os.makedirs(OUTPUT_DIR, exist_ok=True)


model = smp.Unet(
    encoder_name="resnet18",
    encoder_weights=None,
    in_channels=3,
    classes=2
).to(device)

model.load_state_dict(torch.load("models/fine_tuned_model.pth", map_location=device))
model.eval()


if args.image is not None:
    image_arg = args.image
    image_id = os.path.splitext(os.path.basename(image_arg))[0]

    if os.path.exists(image_arg) and os.path.isfile(image_arg):
        filepaths = [image_arg]
    else:
        candidates = [os.path.join(INPUT_DIR, f"{image_id}.jpeg"), os.path.join(INPUT_DIR, f"{image_id}.jpg")]
        filepaths = [p for p in candidates if os.path.exists(p)]
else:
    filepaths = [os.path.join(INPUT_DIR, f) for f in sorted(os.listdir(INPUT_DIR))]

for filepath in filepaths:
    filename = os.path.basename(filepath)
    if not (filename.endswith(".jpeg") or filename.endswith(".jpg")):
        continue

    print(f"\nProcessing: {filename}")

    img = cv2.imread(filepath)
    h, w = img.shape[:2]

    x = cv2.resize(img, (512, 512))
    x = cv2.cvtColor(x, cv2.COLOR_BGR2RGB) / 255.0
    x = torch.tensor(x.transpose(2, 0, 1)).unsqueeze(0).float().to(device)

    with torch.no_grad():
        pred = torch.sigmoid(model(x))[0].cpu().numpy()

    print("Door max:", pred[0].max())
    print("Window max:", pred[1].max())

    # ---------------- SMART THRESHOLD ----------------
    door = (pred[0] > float(args.door_thresh)).astype(np.uint8) * 255
    window = (pred[1] > float(args.window_thresh)).astype(np.uint8) * 255

    # ---------------- BREAK MERGED WINDOWS ----------------
    kernel = np.ones((3, 3), np.uint8)
    window = cv2.morphologyEx(window, cv2.MORPH_OPEN, kernel)

    # ---------------- SPLIT OBJECTS ----------------
    num, labels = cv2.connectedComponents(window)
    clean = np.zeros_like(window)

    for i in range(1, num):
        comp = (labels == i).astype(np.uint8) * 255
        area = cv2.countNonZero(comp)

        if 50 < area < 5000:   # tune if needed
            clean = cv2.bitwise_or(clean, comp)

    window = clean

    # ---------------- RESIZE BACK ----------------
    door = cv2.resize(door, (w, h))
    window = cv2.resize(window, (w, h))

    stem = os.path.splitext(filename)[0]
    cv2.imwrite(f"{OUTPUT_DIR}/{stem}_door.png", door)
    cv2.imwrite(f"{OUTPUT_DIR}/{stem}_window.png", window)


print("\n✅ Done")