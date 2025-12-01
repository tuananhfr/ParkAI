# Dev Mode Configuration (200 Image Calibration)

## ⚙️ Current Setup

**Model:** ONNX INT8 quantized với 200 ảnh calibration
**Hardware:** Raspberry Pi 5 + IMX500
**Expected Confidence:** 0.5-0.7 (bình thường cho 200 ảnh)

---

## 📊 Config Optimized for Dev Mode

### Detection Settings
```python
DETECTION_THRESHOLD = 0.50      # Thấp hơn để detect nhiều (model chưa tự tin)
PLATE_IMAGE_MIN_CONFIDENCE = 0.55  # Gửi ảnh khi conf >= 0.55
```

### Voting Settings (Real-time OCR + Voting)
```python
QUICK_OPEN_ENABLED = False      # TẮT - hiếm khi đạt 0.9
PLATE_VOTE_WINDOW = 1.2         # 1.2s để có đủ votes
PLATE_MIN_VOTES = 2             # Cần 2 votes giống nhau
EARLY_STOP_ENABLED = True       # Stop ngay khi đủ 2 votes
```

### OCR Settings
```python
ENABLE_OCR = True
OCR_FRAME_SKIP = 1              # Chạy mỗi frame để có nhiều votes
```

---

## 🎯 Approach: Real-time OCR + Voting

### Flow:
```
1. IMX500 detect liên tục (hardware)
2. Mỗi detection:
   - Nếu conf >= 0.55 → Crop & gửi ảnh 1 lần (track để không spam)
   - Chạy OCR real-time
   - Vote kết quả
3. Khi đủ 2 votes giống nhau → Finalize
4. Mở cửa
```

### Why This Approach for Dev Mode?
- ✅ Confidence thấp (0.5-0.7) → Cần voting để tin cậy
- ✅ Real-time OCR → Nhiều cơ hội để vote
- ✅ Gửi ảnh khi conf >= 0.55 → Người dùng thấy ảnh sớm
- ❌ Không dùng Quick Open → Model hiếm khi đạt 0.9

---

## 📈 Production Upgrade Plan

### Phase 1: Collect Data (1-2 tháng)
```bash
Thu thập 500-1000 ảnh diverse:
- Sáng/tối/hoàng hôn/mây mù
- Góc thẳng/nghiêng
- Biển 1 dòng/2 dòng
- Sạch/bẩn/cũ
- Gần/xa
```

### Phase 2: Re-quantize INT8
```bash
Quantize lại model với 500-1000 ảnh:
→ Confidence tăng lên 0.6-0.8
→ Model tự tin hơn
```

### Phase 3: Switch to Production Config
```python
DETECTION_THRESHOLD = 0.55
PLATE_IMAGE_MIN_CONFIDENCE = 0.70  # Tăng lên
QUICK_OPEN_ENABLED = True          # Bật lại
PLATE_VOTE_WINDOW = 0.8            # Giảm xuống - nhanh hơn
```

### Phase 4: Consider Trigger-based Approach
```
Chuyển sang Trigger-based (Capture then OCR):
- Chờ conf >= 0.7
- Capture ảnh tốt nhất
- OCR 1 lần
→ Tiết kiệm CPU hơn
```

---

## 🐛 Debug Logs

Current debug logs to monitor:
```
✅ Image OK to send: conf=0.XX, bbox_key=XXX_XXX
📸 Image sent! bbox=XXXxXXXpx, conf=0.XX
⏭️  Image skipped: duplicate (dist=X.Xpx from previous)
❌ Image skipped: conf=0.XX < 0.55
⚠️ Cannot send image: frame is None
```

---

## 📝 Notes

- **Dev mode này tối ưu cho 200 ảnh calibration**
- **Confidence 0.5-0.7 là bình thường**, không phải bug
- **Voting bù đắp** cho confidence thấp
- **Không nên tăng threshold lên 0.75** - model không thiết kế cho range đó
- **Thu thập data để upgrade lên production**

---

Last updated: 2025-11-29
