# stage0.py

import sys
import os
import cv2
from . import utils

def main():
    """Main function to execute Stage 0 tasks."""
    if len(sys.argv) != 2:
        print("Usage: python stage0.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        sys.exit(1)
    
    print(f"Loading image from: {image_path}")
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from '{image_path}'.")
        sys.exit(1)
    print("Image loaded successfully!")
    
    original_shape = image.shape
    original_dtype = image.dtype
    h, w = image.shape[:2]
    scale_x, scale_y = 1.0, 1.0
    
    if max(h, w) > 2000:
        if h > w:
            new_h = 2000
            new_w = int(w * 2000 / h)
        else:
            new_w = 2000
            new_h = int(h * 2000 / w)
        scale_x = w / new_w
        scale_y = h / new_h
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"Resized image to: {image.shape[1]}x{image.shape[0]}")
        print(f"Scale factors: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}")
    
    grayscale_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    print(f"\nOriginal image shape: {original_shape}")
    print(f"Original image datatype: {original_dtype}")
    print(f"Grayscale image shape: {grayscale_image.shape}")
    print(f"Grayscale image datatype: {grayscale_image.dtype}")
    
    print(f"\nPixel values of 5x5 region (top-left corner):")
    region_size = min(5, grayscale_image.shape[0], grayscale_image.shape[1])
    region = grayscale_image[0:region_size, 0:region_size]
    print("5x5 pixel matrix:")
    for row in region:
        print(" ".join(f"{val:3d}" for val in row))
    
    print(f"\nVector Angle Calculations:")
    print("=" * 40)
    for v1, v2 in [((1, 0), (0, 1)), ((2, 3), (4, 6)), ((1, 1), (-1, -1)), ((1, 0), (1, 1))]:
        angle = utils.compute_angle_between_vectors(v1, v2)
        print(f"Angle between {v1} and {v2}: {angle:.2f}°")
    
    output_path = os.path.join(utils.get_intermediate_dir(), "stage0_grayscale.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if cv2.imwrite(output_path, grayscale_image):
        print(f"\nGrayscale image saved to: {output_path}")
    else:
        print(f"\nError: Could not save grayscale image to {output_path}")
    
    scale_factors_path = os.path.join(utils.get_intermediate_dir(), "scale_factors.json")
    utils.save_json({"scale_x": scale_x, "scale_y": scale_y}, scale_factors_path)
    print(f"\nScale factors saved to: {scale_factors_path}")
    print("\nStage 0 completed successfully!")

if __name__ == "__main__":
    main()
