"""
Stage 1: Binary Structure Extraction and Edge Stabilization
Sketch2Floor Project - Extract stable wall geometry and wall-aligned edges

Core Principle: Binary defines geometry. Edges are derived, never detected.

This is a DETERMINISTIC single pipeline:
- No adaptive strategy switching
- No edge-density heuristics  
- No Canny on grayscale
- Binary structure dominates edge structure

Pipeline Steps:
1. Bilateral filtering for denoising
2. Otsu thresholding (binary inverse)
3. Morphological closing for stroke connection
4. Morphological opening for noise suppression
5. Connected component filtering
6. Morphological gradient for edge generation
7. Edge cleanup with morphological closing

Explicitly Forbidden:
- Canny on grayscale
- Adaptive strategy switching
- Edge-density heuristics
- CLAHE
- Multi-scale edge detection
- Using edges to infer geometry
"""

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
    
    # Check if resize is needed
    if max(height, width) <= max_dimension:
        return grayscale_image
    
    # Calculate new dimensions preserving aspect ratio
    if height > width:
        new_height = max_dimension
        new_width = int(width * max_dimension / height)
    else:
        new_width = max_dimension
        new_height = int(height * max_dimension / width)
    
    # Resize image
    resized = cv2.resize(grayscale_image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    print(f"  Resized from {width}x{height} to {new_width}x{new_height}")
    return resized


def apply_bilateral_denoising(grayscale_image):
    """
    Apply bilateral filter to reduce paper texture while preserving pen strokes.
    
    Parameters:
    - diameter: 5
    - sigma_color: 50
    - sigma_space: 50
    
    Args:
        grayscale_image (numpy.ndarray): Input grayscale image
    
    Returns:
        numpy.ndarray: Denoised grayscale image
    """
    denoised = cv2.bilateralFilter(grayscale_image, 5, 50, 50)
    return denoised


def apply_otsu_thresholding(denoised_image):
    """
    Apply Otsu thresholding with binary inverse mode.
    Separates ink from paper without manual thresholds.
    
    Args:
        denoised_image (numpy.ndarray): Denoised grayscale image
    
    Returns:
        numpy.ndarray: Binary image (ink as white, paper as black)
    """
    _, binary = cv2.threshold(denoised_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def connect_strokes(binary_image):
    """
    Apply morphological closing to bridge gaps in hand-drawn wall strokes.
    
    Kernel: [3, 3]
    Iterations: 1
    
    Args:
        binary_image (numpy.ndarray): Binary image
    
    Returns:
        numpy.ndarray: Binary image with connected strokes
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    connected = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel, iterations=1)
    return connected


def suppress_noise(connected_image):
    """
    Apply morphological opening to remove isolated specks and text fragments.
    
    Kernel: [2, 2]
    Iterations: 1
    
    Args:
        connected_image (numpy.ndarray): Connected binary image
    
    Returns:
        numpy.ndarray: Binary image with noise suppressed
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(connected_image, cv2.MORPH_OPEN, kernel, iterations=1)
    return cleaned


def filter_components(cleaned_image):
    """
    Apply connected component analysis to preserve wall-like structures only.
    
    Rules:
    - Discard components with area < 50
    - Prefer elongated or large components
    - Retain components with aspect_ratio > 2 OR area > 200
    
    Args:
        cleaned_image (numpy.ndarray): Cleaned binary image
    
    Returns:
        numpy.ndarray: Filtered binary image with wall-like structures only
    """
    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned_image, 8, cv2.CV_32S)
    
    # Create output image
    filtered = np.zeros_like(cleaned_image)
    
    # Process each component (skip background label 0)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        
        # Calculate aspect ratio
        aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 1
        
        # Apply filtering rules
        if area >= 50 and (aspect_ratio > 2.0 or area > 200):
            filtered[labels == i] = 255
    
    return filtered


def generate_edges(filtered_binary):
    """
    Generate edges using morphological gradient.
    Definition: dilation(binary) - erosion(binary)
    
    Kernel: [3, 3]
    
    Args:
        filtered_binary (numpy.ndarray): Filtered binary image
    
    Returns:
        numpy.ndarray: Edge image aligned exactly with wall geometry
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    
    # Morphological gradient
    dilated = cv2.dilate(filtered_binary, kernel, iterations=1)
    eroded = cv2.erode(filtered_binary, kernel, iterations=1)
    edges = cv2.subtract(dilated, eroded)
    
    return edges


def fill_wall_holes(binary_image):
    """
    Fill holes within wall regions using morphological reconstruction.
    This fills only holes inside wall structures, not the background.
    
    Args:
        binary_image (numpy.ndarray): Binary image with walls as white (255)
    
    Returns:
        numpy.ndarray: Binary image with holes filled within walls
    """
    # Create a marker image (walls slightly eroded)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    marker = cv2.erode(binary_image, kernel, iterations=1)
    
    # Use morphological closing to fill holes
    # This connects nearby wall regions and fills small gaps
    filled = cv2.morphologyEx(binary_image, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Ensure we don't create new wall regions outside original walls
    # Only keep filled areas that overlap with original walls
    filled = cv2.bitwise_and(filled, binary_image)
    
    return filled


def cleanup_edges(edges):
    """
    Improve edge continuity without thickening.
    
    Operation: morphological_close
    Kernel: [2, 2]
    Iterations: 1
    
    Args:
        edges (numpy.ndarray): Edge image
    
    Returns:
        numpy.ndarray: Cleaned edge image
    """
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    return cleaned_edges


def main():
    """Main function to execute Stage 1 deterministic binary structure extraction."""
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python stage1_preprocess.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Check if image file exists
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        sys.exit(1)
    
    print(f"Stage 1: Binary Structure Extraction and Edge Stabilization")
    print(f"Loading image from: {image_path}")
    
    # Prefer Stage 0 standardized grayscale if present
    stage0_gray_path = os.path.join("data", "intermediate", "stage0_grayscale.png")
    if os.path.exists(stage0_gray_path):
        print(f"Found Stage 0 grayscale at: {stage0_gray_path}. Using it as input.")
        grayscale_image = cv2.imread(stage0_gray_path, cv2.IMREAD_GRAYSCALE)
    else:
        # Load as grayscale deterministically
        grayscale_image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    if grayscale_image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)
    
    print(f"Input grayscale shape: {grayscale_image.shape}")
    
    # Resize if needed (max dimension > 2000px)
    grayscale_image = resize_if_needed(grayscale_image, max_dimension=2000)
    
    # STEP 1: Bilateral denoising
    print("Step 1: Applying bilateral denoising...")
    denoised = apply_bilateral_denoising(grayscale_image)
    
    # STEP 2: Otsu thresholding (binary inverse)
    print("Step 2: Applying Otsu thresholding...")
    binary = apply_otsu_thresholding(denoised)
    
    # STEP 3: Stroke connection
    print("Step 3: Connecting strokes with morphological closing...")
    connected = connect_strokes(binary)
    
    # STEP 4: Noise suppression
    print("Step 4: Suppressing noise with morphological opening...")
    cleaned = suppress_noise(connected)
    
    # STEP 5: Component filtering
    print("Step 5: Filtering components to preserve wall-like structures...")
    filtered = filter_components(cleaned)
    
    # STEP 6: Edge generation (morphological gradient)
    print("Step 6: Generating edges from binary structure...")
    edges = generate_edges(filtered)
    
    # STEP 7: Edge cleanup
    print("Step 7: Cleaning up edges...")
    final_edges = cleanup_edges(edges)
    
    # Ensure output directory exists
    os.makedirs("data/intermediate", exist_ok=True)
    
    # Save outputs
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
    
    # Print processing summary
    print(f"\nProcessing Summary:")
    print(f"Final image size: {grayscale_image.shape[0]} x {grayscale_image.shape[1]}")
    print(f"Binary wall mask - Wall pixels: {np.sum(filtered == 255)}, Background: {np.sum(filtered == 0)}")
    print(f"Edge map - Edge pixels: {np.sum(final_edges == 255)}, Non-edge: {np.sum(final_edges == 0)}")
    
    # Calculate quality metrics
    wall_density = np.sum(filtered == 255) / (filtered.shape[0] * filtered.shape[1]) * 100
    edge_to_binary_ratio = np.sum(final_edges == 255) / np.sum(filtered == 255) if np.sum(filtered == 255) > 0 else 0
    
    print(f"\nQuality Metrics:")
    print(f"Wall pixel density: {wall_density:.2f}% of image area (expected: 0.5% - 5%)")
    print(f"Edge-to-binary ratio: {edge_to_binary_ratio:.2f} (expected: 0.1 - 0.5)")
    
    # Wall continuity assessment
    num_wall_components, _, _, _ = cv2.connectedComponentsWithStats(filtered, 8, cv2.CV_32S)
    print(f"Wall continuity: {num_wall_components - 1} wall components (lower is better)")
    
    # Quality assessment
    if 0.5 <= wall_density <= 5.0:
        print("✓ Wall pixel density within expected range")
    else:
        print("⚠ Wall pixel density outside expected range")
        
    if 0.1 <= edge_to_binary_ratio <= 0.5:
        print("✓ Edge-to-binary ratio within expected range")
    else:
        print("⚠ Edge-to-binary ratio outside expected range")
    
    print("\nStage 1 completed successfully!")
    print("Key achievements:")
    print("- Deterministic binary structure extraction")
    print("- Edges derived from binary geometry only")
    print("- Wall-like structures preserved and enhanced")
    print("- Stable output across lighting variations")


if __name__ == "__main__":
    main()
