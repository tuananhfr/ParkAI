"""
Test script để verify TFLite OCR setup
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import config
from ocr_service import OCRService
import numpy as np

def test_ocr_service():
    """Test OCRService initialization"""
    print("=" * 60)
    print("🧪 Testing OCR Service Setup")
    print("=" * 60)

    print(f"\n📋 Current Config:")
    print(f"   OCR_TYPE: {config.OCR_TYPE}")
    print(f"   TFLITE_OCR_MODEL_PATH: {config.TFLITE_OCR_MODEL_PATH}")
    print(f"   ONNX_OCR_MODEL_PATH: {config.ONNX_OCR_MODEL_PATH}")
    print(f"   ENABLE_OCR: {config.ENABLE_OCR}")

    print(f"\n🔧 Initializing OCRService...")
    try:
        ocr_service = OCRService()
        print(f"\n✅ OCRService initialized successfully!")
        print(f"   Active OCR engine: {ocr_service.ocr_type}")

        # Test với dummy image
        print(f"\n🖼️  Testing with dummy plate image...")
        dummy_plate = np.random.randint(0, 255, (100, 300, 3), dtype=np.uint8)

        result = ocr_service.recognize(dummy_plate)

        if result is None:
            print(f"✅ OCR trả về None (expected vì chưa có model hoặc dummy image)")
            print(f"   Khi bạn add model TFLite và config đường dẫn, OCR sẽ hoạt động!")
        else:
            print(f"✅ OCR result: {result}")

        print(f"\n" + "=" * 60)
        print("🎉 TEST PASSED!")
        print("=" * 60)
        print("\n📝 Next steps:")
        print("   1. Tìm hoặc train TFLite OCR model (.tflite)")
        print("   2. Copy model vào thư mục, ví dụ: backend/models/plate_ocr.tflite")
        print("   3. Update config.py:")
        print('      TFLITE_OCR_MODEL_PATH = "backend/models/plate_ocr.tflite"')
        print("   4. Restart app.py và OCR sẽ hoạt động!")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED!")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ocr_service()
    sys.exit(0 if success else 1)
