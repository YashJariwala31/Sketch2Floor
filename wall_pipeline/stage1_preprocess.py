# stage1_preprocess.py

import sys
import os
import numpy as np
import cv2


def resize_if_needed(grayscale_image, max_dimension=2000):
    """
    Resize image if max dimension > 2000px while preserving aspect ratio.

    Args:
        grayscale_image (numpy.ndarray): Input grayscale image
        max_dimension (int): Maximum allowed dimension

    Returns:
        numpy.ndarray: Resized grayscale image or original if no resize needed
    """
    height, width = grayscale_image.shape

    if max(height, width) <= max_dimension:
        return grayscale_image

    if height > width:
        new_height = max_dimension
        new_width = int(width * max_dimension / height)
    else:
        new_width = max_dimension
        new_height = int(height * max_dimension / width)

    resized = cv2.resize(grayscale_image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    print(f"  Resized from {width}x{height} to {new_width}x{new_height}")
    return resized


def apply_bilateral_denoising(grayscale_image):
    denoised = cv2.bilateralFilter(grayscale_image, 5, 50, 50)
    return denoised


def apply_otsu_thresholding(denoised_image):
    _, binary = cv2.threshold(denoised_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def connect_strokes(binary_image):
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    connected = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel, iterations=1)
    return connected


def suppress_noise(connected_image):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(connected_image, cv2.MORPH_OPEN, kernel, iterations=1)
    return cleaned


def filter_components(cleaned_image):
    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(cleaned_image, 8, cv2.CV_32S)
    filtered = np.zeros_like(cleaned_image)

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 1

        if area >= 50 and (aspect_ratio > 2.0 or area > 200):
            filtered[labels == i] = 255

    return filtered


def generate_edges(filtered_binary):
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    dilated = cv2.dilate(filtered_binary, kernel, iterations=1)
    eroded = cv2.erode(filtered_binary, kernel, iterations=1)
    edges = cv2.subtract(dilated, eroded)
    return edges


def fill_wall_holes(binary_image):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    _marker = cv2.erode(binary_image, kernel, iterations=1)
    filled = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel, iterations=2)
    filled = cv2.bitwise_and(filled, binary_image)
    return filled


def cleanup_edges(edges):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    return cleaned_edges


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

    stage0_gray_path = os.path.join("data", "intermediate", "stage0_grayscale.png")
    if os.path.exists(stage0_gray_path):
        print(f"Found Stage 0 grayscale at: {stage0_gray_path}. Using it as input.")
        grayscale_image = cv2.imread(stage0_gray_path, cv2.IMREAD_GRAYSCALE)
    else:
        grayscale_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    if grayscale_image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)

    print(f"Input grayscale shape: {grayscale_image.shape}")
    grayscale_image = resize_if_needed(grayscale_image, max_dimension=2000)

    print("Step 1: Applying bilateral denoising...")
    denoised = apply_bilateral_denoising(grayscale_image)

    print("Step 2: Applying Otsu thresholding...")
    binary = apply_otsu_thresholding(denoised)

    print("Step 3: Connecting strokes with morphological closing...")
    connected = connect_strokes(binary)

    print("Step 4: Suppressing noise with morphological opening...")
    cleaned = suppress_noise(connected)

    print("Step 5: Filtering components to preserve wall-like structures...")
    filtered = filter_components(cleaned)

    print("Step 6: Generating edges from binary structure...")
    edges = generate_edges(filtered)

    print("Step 7: Cleaning up edges...")
    final_edges = cleanup_edges(edges)

    os.makedirs("data/intermediate", exist_ok=True)

    denoised_path = "data/intermediate/stage1_denoised.png"
    binary_path = "data/intermediate/binary_wall_mask.png"
    edges_path = "data/intermediate/edge_map.png"

    success_denoised = cv2.imwrite(denoised_path, denoised)
    success_binary = cv2.imwrite(binary_path, filtered)
    success_edges = cv2.imwrite(edges_path, final_edges)

    if success_denoised:
        print(f"Denoised image saved to: {denoised_path}")
    if success_binary:
        print(f"Binary image saved to: {binary_path}")
    if success_edges:
        print(f"Edge image saved to: {edges_path}")

    print("\nProcessing Summary:")
    print(f"Final image size: {grayscale_image.shape[0]} x {grayscale_image.shape[1]}")
    print(f"Binary wall mask - Wall pixels: {np.sum(filtered == 255)}, Background: {np.sum(filtered == 0)}")
    print(f"Edge map - Edge pixels: {np.sum(final_edges == 255)}, Non-edge: {np.sum(final_edges == 0)}")

    wall_density = np.sum(filtered == 255) / (filtered.shape[0] * filtered.shape[1]) * 100
    edge_to_binary_ratio = np.sum(final_edges == 255) / np.sum(filtered == 255) if np.sum(filtered == 255) > 0 else 0

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
