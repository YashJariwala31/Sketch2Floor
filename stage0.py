#!/usr/bin/env python3
"""
Stage 0: Ground Check
Sketch2Floor Project - Convert hand-drawn sketches to floor plans

This stage verifies fundamental understanding of image representation and vector math.
"""

import sys
import os
import numpy as np
import cv2


def compute_angle_between_vectors(v1, v2):
    """
    Compute the angle (in degrees) between two 2D vectors using dot product.
    
    Mathematical formula:
    angle = arccos((v1 · v2) / (|v1| * |v2|))
    
    where:
    - v1 · v2 is the dot product
    - |v1| and |v2| are the magnitudes of the vectors
    
    Args:
        v1 (tuple): First 2D vector as (x, y)
        v2 (tuple): Second 2D vector as (x, y)
    
    Returns:
        float: Angle in degrees between the two vectors
    """
    # Convert to numpy arrays for easier computation
    v1_np = np.array(v1, dtype=float)
    v2_np = np.array(v2, dtype=float)
    
    # Calculate dot product: v1 · v2 = v1.x * v2.x + v1.y * v2.y
    dot_product = np.dot(v1_np, v2_np)
    
    # Calculate magnitudes: |v| = sqrt(x^2 + y^2)
    magnitude_v1 = np.linalg.norm(v1_np)
    magnitude_v2 = np.linalg.norm(v2_np)
    
    # Handle edge case of zero-length vectors
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    
    # Calculate cosine of the angle
    cos_angle = dot_product / (magnitude_v1 * magnitude_v2)
    
    # Clamp to [-1, 1] to handle floating point precision issues
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    
    # Calculate angle in radians and convert to degrees
    angle_rad = np.arccos(cos_angle)
    angle_deg = np.degrees(angle_rad)
    
    return angle_deg


def main():
    """Main function to execute Stage 0 tasks."""
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python stage0.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Check if image file exists
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        sys.exit(1)
    
    print(f"Loading image from: {image_path}")
    
    # Task 1: Load image from file path
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)
    
    print("Image loaded successfully!")
    
    original_shape = image.shape
    original_dtype = image.dtype
    h, w = image.shape[:2]
    if max(h, w) > 2000:
        if h > w:
            new_h = 2000
            new_w = int(w * 2000 / h)
        else:
            new_w = 2000
            new_h = int(h * 2000 / w)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"Resized image to: {image.shape[1]}x{image.shape[0]}")
    
    # Task 2: Convert to grayscale
    # Grayscale conversion: gray = 0.299*R + 0.587*G + 0.114*B
    grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Task 3: Print image dimensions and datatype
    print(f"\nOriginal image shape: {original_shape}")
    print(f"Original image datatype: {original_dtype}")
    print(f"Grayscale image shape: {grayscale_image.shape}")
    print(f"Grayscale image datatype: {grayscale_image.dtype}")
    
    # Task 4: Print pixel values of a small 5x5 region
    print(f"\nPixel values of 5x5 region (top-left corner):")
    height, width = grayscale_image.shape
    region_size = min(5, height, width)  # Ensure we don't go out of bounds
    region = grayscale_image[0:region_size, 0:region_size]
    
    print("5x5 pixel matrix:")
    for row in region:
        print(" ".join(f"{val:3d}" for val in row))
    
    # Task 5: Demonstrate vector angle calculation
    print(f"\nVector Angle Calculations:")
    print("=" * 40)
    
    # Example 1: Orthogonal vectors (should be 90 degrees)
    v1 = (1, 0)  # Unit vector along x-axis
    v2 = (0, 1)  # Unit vector along y-axis
    angle1 = compute_angle_between_vectors(v1, v2)
    print(f"Angle between {v1} and {v2}: {angle1:.2f}°")
    
    # Example 2: Same direction vectors (should be 0 degrees)
    v3 = (2, 3)
    v4 = (4, 6)  # Same direction as v3, scaled by 2
    angle2 = compute_angle_between_vectors(v3, v4)
    print(f"Angle between {v3} and {v4}: {angle2:.2f}°")
    
    # Example 3: Opposite direction vectors (should be 180 degrees)
    v5 = (1, 1)
    v6 = (-1, -1)  # Opposite direction
    angle3 = compute_angle_between_vectors(v5, v6)
    print(f"Angle between {v5} and {v6}: {angle3:.2f}°")
    
    # Example 4: 45-degree angle
    v7 = (1, 0)
    v8 = (1, 1)
    angle4 = compute_angle_between_vectors(v7, v8)
    print(f"Angle between {v7} and {v8}: {angle4:.2f}°")
    
    # Task 6: Save grayscale image
    output_path = "data/intermediate/stage0_grayscale.png"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the grayscale image
    success = cv2.imwrite(output_path, grayscale_image)
    
    if success:
        print(f"\nGrayscale image saved to: {output_path}")
    else:
        print(f"\nError: Could not save grayscale image to {output_path}")
    
    print("\nStage 0 completed successfully!")


if __name__ == "__main__":
    main()

