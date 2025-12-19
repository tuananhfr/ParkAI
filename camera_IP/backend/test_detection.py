"""
Test script for license plate detection API
"""
import requests
import cv2
import sys
from pathlib import Path


def test_upload_detection(image_path: str, base_url: str = "http://localhost:5000"):
    """Test detection with image upload"""
    print(f"\n[TEST] Testing upload detection with {image_path}")

    # Check if image exists
    if not Path(image_path).exists():
        print(f"[ERROR] Image not found: {image_path}")
        return

    # Read image file
    with open(image_path, 'rb') as f:
        files = {'file': f}
        params = {
            'conf_threshold': 0.25,
            'iou_threshold': 0.45
        }

        # Call API
        response = requests.post(
            f"{base_url}/api/detect/upload",
            files=files,
            params=params
        )

    if response.status_code == 200:
        result = response.json()
        print(f"[SUCCESS] Detection completed!")
        print(f"  - Count: {result['count']}")
        print(f"  - Processing time: {result['processing_time_ms']}ms")
        print(f"  - Detections:")
        for i, det in enumerate(result['detections'], 1):
            print(f"    {i}. BBox: {det['bbox']}, Confidence: {det['confidence']:.2f}")
    else:
        print(f"[ERROR] API returned {response.status_code}: {response.text}")


def test_upload_visualize(image_path: str, output_path: str = "output_detection.jpg",
                         base_url: str = "http://localhost:5000"):
    """Test detection with visualization"""
    print(f"\n[TEST] Testing upload detection with visualization")
    print(f"  Input: {image_path}")
    print(f"  Output: {output_path}")

    # Check if image exists
    if not Path(image_path).exists():
        print(f"[ERROR] Image not found: {image_path}")
        return

    # Read image file
    with open(image_path, 'rb') as f:
        files = {'file': f}
        params = {
            'conf_threshold': 0.25,
            'iou_threshold': 0.45,
            'color_r': 0,
            'color_g': 255,
            'color_b': 0,
            'thickness': 3
        }

        # Call API
        response = requests.post(
            f"{base_url}/api/detect/upload/visualize",
            files=files,
            params=params
        )

    if response.status_code == 200:
        # Save output image
        with open(output_path, 'wb') as f:
            f.write(response.content)

        detection_count = response.headers.get('X-Detection-Count', '0')
        print(f"[SUCCESS] Visualization saved!")
        print(f"  - Detections found: {detection_count}")
        print(f"  - Output saved to: {output_path}")

        # Display image
        img = cv2.imread(output_path)
        if img is not None:
            cv2.imshow('License Plate Detection', img)
            print(f"[INFO] Press any key to close the window...")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    else:
        print(f"[ERROR] API returned {response.status_code}: {response.text}")


def test_rtsp_detection(rtsp_url: str, base_url: str = "http://localhost:5000"):
    """Test detection from RTSP stream"""
    print(f"\n[TEST] Testing RTSP detection")
    print(f"  RTSP URL: {rtsp_url}")

    params = {
        'rtsp_url': rtsp_url,
        'conf_threshold': 0.25,
        'iou_threshold': 0.45
    }

    # Call API
    response = requests.post(
        f"{base_url}/api/detect/rtsp",
        params=params
    )

    if response.status_code == 200:
        result = response.json()
        print(f"[SUCCESS] Detection completed!")
        print(f"  - Count: {result['count']}")
        print(f"  - Processing time: {result['processing_time_ms']}ms")
        print(f"  - Detections:")
        for i, det in enumerate(result['detections'], 1):
            print(f"    {i}. BBox: {det['bbox']}, Confidence: {det['confidence']:.2f}")
    else:
        print(f"[ERROR] API returned {response.status_code}: {response.text}")


def test_health_check(base_url: str = "http://localhost:5000"):
    """Test health check endpoint"""
    print(f"\n[TEST] Testing health check")

    response = requests.get(f"{base_url}/health")

    if response.status_code == 200:
        print(f"[SUCCESS] Health check passed: {response.json()}")
    else:
        print(f"[ERROR] Health check failed: {response.status_code}")


if __name__ == "__main__":
    BASE_URL = "http://localhost:5000"

    print("=" * 60)
    print("License Plate Detection API Test")
    print("=" * 60)

    # Test health check
    test_health_check(BASE_URL)

    # Test with command line argument or default
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # Try to find a test image
        test_images = [
            "test_image.jpg",
            "test.jpg",
            "sample.jpg",
            "../test_image.jpg"
        ]

        image_path = None
        for test_img in test_images:
            if Path(test_img).exists():
                image_path = test_img
                break

        if image_path is None:
            print("\n[INFO] No test image found. Please provide an image path:")
            print("  python test_detection.py <path_to_image>")
            print("\n[INFO] You can also test with RTSP:")
            print("  Example: test_rtsp_detection('rtsp://username:password@ip/stream')")
            sys.exit(0)

    # Run tests
    test_upload_detection(image_path, BASE_URL)
    test_upload_visualize(image_path, "output_detection.jpg", BASE_URL)

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
