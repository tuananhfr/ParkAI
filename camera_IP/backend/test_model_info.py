"""
Kiểm tra thông tin model YOLO để debug
"""
from ultralytics import YOLO
from pathlib import Path

def main():
    model_path = "models/license_plate.pt"

    print("=" * 60)
    print("YOLO Model Information")
    print("=" * 60)

    # Load model
    print(f"\n[LOADING] Loading model from {model_path}...")
    model = YOLO(model_path)
    print("[OK] Model loaded successfully!\n")

    # Get model info
    print("-" * 60)
    print("MODEL DETAILS:")
    print("-" * 60)

    # Class names
    if hasattr(model, 'names'):
        print(f"\nClass Names ({len(model.names)} classes):")
        for idx, name in model.names.items():
            print(f"  [{idx}] {name}")
    else:
        print("\n[WARNING] No class names found in model!")

    # Model type
    print(f"\nModel Type: {model.task}")

    # Model architecture
    if hasattr(model, 'model'):
        print(f"Model Architecture: {type(model.model).__name__}")

    # Input shape
    if hasattr(model.model, 'yaml'):
        yaml_info = model.model.yaml
        print(f"\nModel Config:")
        if 'nc' in yaml_info:
            print(f"  Number of classes: {yaml_info['nc']}")
        if 'names' in yaml_info:
            print(f"  Class names: {yaml_info['names']}")

    # Test inference
    print("\n" + "-" * 60)
    print("TESTING INFERENCE:")
    print("-" * 60)

    import cv2
    import numpy as np

    # Create dummy image
    test_img = np.zeros((640, 640, 3), dtype=np.uint8)

    print("\nRunning test inference on dummy image...")
    results = model.predict(test_img, conf=0.01, verbose=False)

    print(f"[OK] Inference successful!")
    print(f"Number of detections: {len(results[0].boxes) if len(results) > 0 else 0}")

    # Test với ảnh thật nếu có
    print("\n" + "-" * 60)
    print("RECOMMENDATIONS:")
    print("-" * 60)

    print("\n1. Make sure model was trained for license plate detection")
    print("2. Expected class name should be 'license_plate' or similar")
    print("3. If model shows wrong classes, you need to retrain or use correct model")
    print("4. Test with actual license plate image to verify")

    # Tìm ảnh test nếu có
    test_images_dir = Path("test_images")
    if test_images_dir.exists():
        test_images = list(test_images_dir.glob("*.jpg")) + list(test_images_dir.glob("*.png"))
        if test_images:
            print(f"\n[FOUND] {len(test_images)} test images in test_images/")
            print("Testing on first image...")

            img = cv2.imread(str(test_images[0]))
            results = model.predict(img, conf=0.25, verbose=False)

            detections = results[0].boxes
            print(f"Detections found: {len(detections)}")

            for i, box in enumerate(detections):
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                print(f"  Detection {i+1}: {model.names[cls]} ({conf:.2f})")

if __name__ == "__main__":
    main()
