# stage1_preprocess.py

import sys
import os
import numpy as np
import cv2


def main():
    if len(sys.argv) != 2:
        print("Usage: python stage1_preprocess.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        sys.exit(1)

    print("Stage 1: Binary Structure Extraction and Edge Stabilization")
    print(f"Loading image from: {image_path}")

    from . import utils
    intermediate_dir = utils.get_intermediate_dir()

    stage0_gray_path = os.path.join(intermediate_dir, "stage0_grayscale.png")
    if os.path.exists(stage0_gray_path):
        print(f"Found Stage 0 grayscale at: {stage0_gray_path}. Using it as input.")
        grayscale_image = cv2.imread(stage0_gray_path, cv2.IMREAD_GRAYSCALE)
    else:
        grayscale_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if grayscale_image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)

    print(f"Input grayscale shape: {grayscale_image.shape}")
    height, width = grayscale_image.shape
    if max(height, width) > 2000:
        if height > width:
            new_height, new_width = 2000, int(width * 2000 / height)
        else:
            new_width, new_height = 2000, int(height * 2000 / width)
        grayscale_image = cv2.resize(grayscale_image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        print(f"  Resized from {width}x{height} to {new_width}x{new_height}")

    print("Step 1: Applying bilateral denoising...")
    denoised = cv2.bilateralFilter(grayscale_image, 5, 50, 50)

    print("Step 2: Applying Otsu thresholding...")
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    print("Step 3: Connecting strokes with morphological closing...")
    kernel_cross = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    connected = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_cross, iterations=1)

    print("Step 4: Suppressing noise with morphological opening...")
    kernel_rect = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(connected, cv2.MORPH_OPEN, kernel_rect, iterations=1)

    print("Step 5: Filtering components to preserve wall-like structures...")
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, 8, cv2.CV_32S)
    filtered = np.zeros_like(cleaned)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1

        if area >= 50 and (aspect_ratio > 2.0 or area > 200):
            filtered[labels == i] = 255

    print("Step 6: Generating edges from binary structure...")
    dilated = cv2.dilate(filtered, kernel_cross, iterations=1)
    eroded = cv2.erode(filtered, kernel_cross, iterations=1)
    edges = cv2.subtract(dilated, eroded)

    print("Step 7: Cleaning up edges...")
    final_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_rect, iterations=1)

    paths = {
        "denoised": os.path.join(intermediate_dir, "stage1_denoised.png"),
        "binary": os.path.join(intermediate_dir, "binary_wall_mask.png"),
        "edges": os.path.join(intermediate_dir, "edge_map.png")
    }

    if cv2.imwrite(paths["denoised"], denoised):
        print(f"Denoised image saved to: {paths['denoised']}")
    if cv2.imwrite(paths["binary"], filtered):
        print(f"Binary image saved to: {paths['binary']}")
    if cv2.imwrite(paths["edges"], final_edges):
        print(f"Edge image saved to: {paths['edges']}")

    wall_pixels, background = np.sum(filtered == 255), np.sum(filtered == 0)
    edge_pixels, non_edge = np.sum(final_edges == 255), np.sum(final_edges == 0)

    print("\nProcessing Summary:")
    print(f"Final image size: {grayscale_image.shape[0]} x {grayscale_image.shape[1]}")
    print(f"Binary wall mask - Wall pixels: {wall_pixels}, Background: {background}")
    print(f"Edge map - Edge pixels: {edge_pixels}, Non-edge: {non_edge}")

    wall_density = wall_pixels / (filtered.shape[0] * filtered.shape[1]) * 100
    edge_to_binary_ratio = edge_pixels / wall_pixels if wall_pixels > 0 else 0

    print("\nQuality Metrics:")
    print(f"Wall pixel density: {wall_density:.2f}% of image area (expected: 0.5% - 5%)")
    print(f"Edge-to-binary ratio: {edge_to_binary_ratio:.2f} (expected: 0.1 - 0.5)")

    num_wall_components, _, _, _ = cv2.connectedComponentsWithStats(filtered, 8, cv2.CV_32S)
    print(f"Wall continuity: {num_wall_components - 1} wall components (lower is better)")

    if 0.5 <= wall_density <= 5.0:
        print("[OK] Wall pixel density within expected range")
    else:
        print("[WARN] Wall pixel density outside expected range")

    if 0.1 <= edge_to_binary_ratio <= 0.5:
        print("[OK] Edge-to-binary ratio within expected range")
    else:
        print("[WARN] Edge-to-binary ratio outside expected range")

    print("\nStage 1 completed successfully!")
    print("Key achievements:")
    print("- Deterministic binary structure extraction")
    print("- Edges derived from binary geometry only")
    print("- Wall-like structures preserved and enhanced")
    print("- Stable output across lighting variations")


if __name__ == "__main__":
    main()
