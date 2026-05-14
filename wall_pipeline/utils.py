import os
import json
import math
import numpy as np
import cv2

# --- Math & Geometry ---

def compute_length(x1, y1, x2, y2):
    return float(math.hypot(x2 - x1, y2 - y1))

def compute_angle_deg(x1, y1, x2, y2):
    return math.degrees(math.atan2(float(y2) - float(y1), float(x2) - float(x1))) % 180.0

def orientation_label(angle_deg):
    if angle_deg <= 10.0 or angle_deg >= 170.0:
        return "horizontal"
    if abs(angle_deg - 90.0) <= 10.0:
        return "vertical"
    return None

def compute_angle_between_vectors(v1, v2):
    v1_np = np.array(v1, dtype=float)
    v2_np = np.array(v2, dtype=float)
    magnitude_v1 = np.linalg.norm(v1_np)
    magnitude_v2 = np.linalg.norm(v2_np)
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    cos_angle = np.clip(np.dot(v1_np, v2_np) / (magnitude_v1 * magnitude_v2), -1.0, 1.0)
    return np.degrees(np.arccos(cos_angle))

def calculate_polygon_area(vertices):
    n = len(vertices)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0

# --- I/O Helpers ---

def get_intermediate_dir():
    return os.getenv("S2FP_INTERMEDIATE_DIR", os.path.join("data", "intermediate"))

def load_wall_mask(mask_path=None):
    if mask_path is None:
        mask_path = os.path.join(get_intermediate_dir(), "binary_wall_mask.png")
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"Binary wall mask not found: {mask_path}")
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"Failed to load wall mask: {mask_path}")
    return mask

def get_image_dimensions():
    try:
        mask = load_wall_mask()
        return mask.shape
    except (FileNotFoundError, ValueError):
        return (720, 1024)

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, 'r') as f:
        return json.load(f)

def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_scale_factors():
    try:
        factors = load_json(os.path.join(get_intermediate_dir(), "scale_factors.json"))
        return float(factors.get("scale_x", 1.0)), float(factors.get("scale_y", 1.0))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 1.0, 1.0
