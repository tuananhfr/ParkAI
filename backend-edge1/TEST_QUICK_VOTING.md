# 🧪 TESTING QUICK VOTING - STEP BY STEP

## 📋 PRE-DEPLOYMENT CHECKLIST

### **1. Verify Config**
```bash
cd backend-edge1
python -c "import config; print(f'Quick Open: {config.QUICK_OPEN_ENABLED}, Early Stop: {config.EARLY_STOP_ENABLED}')"
```

**Expected output:**
```
Quick Open: True, Early Stop: True
```

---

## 🎯 TEST CASES

### **Test 1: Quick Open (High Confidence)**

**Setup:**
- Xe với biển số RÕ, ánh sáng TỐT
- Expected: Confidence ≥ 90%

**Steps:**
1. Start app: `python app.py`
2. Đưa xe vào camera
3. Watch logs

**Expected logs:**
```
⚡ QUICK OPEN: 29A12345 (conf: 0.92)
🚪 [Cổng vào A] Barrier OPEN
```

**Expected timing:** < 0.3s từ detect → barrier open

---

### **Test 2: Early Stop (Medium Confidence)**

**Setup:**
- Xe với biển số hơi mờ
- Expected: Confidence 70-89%

**Steps:**
1. Start app
2. Đưa xe vào camera
3. Watch logs

**Expected logs:**
```
📊 Vote: 29A12345  (Vote 1)
📊 Vote: 29A12345  (Vote 2)
⚡ EARLY STOP: 29A12345 (2 votes in 0.15s)
🚪 [Cổng vào A] Barrier OPEN
```

**Expected timing:** 0.1-0.5s

---

### **Test 3: Full Voting (Conflicting Reads)**

**Setup:**
- Xe với biển số rất mờ hoặc góc nghiêng
- Expected: OCR không ổn định

**Steps:**
1. Start app
2. Đưa xe vào camera (góc xéo)
3. Watch logs

**Expected logs:**
```
📊 Vote: 29A1234   (Vote 1)
📊 Vote: 29A12345  (Vote 2)
📊 Vote: 29A12345  (Vote 3)
⚡ EARLY STOP: 29A12345 (2 votes in 0.25s)
🚪 [Cổng vào A] Barrier OPEN
```

**Expected timing:** 0.2-0.5s (still faster than old 1.5s!)

---

## 📊 METRICS TO COLLECT

### **During 1 Hour Test:**

Track these metrics:

```python
# Add vào detection_service.py (temporary)
quick_open_count = 0
early_stop_count = 0
full_voting_count = 0

# Tính average latency
latencies = []
```

### **Success Criteria:**

| Metric | Target | Actual |
|--------|--------|--------|
| Quick Open % | > 80% | ___ |
| Average latency | < 0.5s | ___ |
| Accuracy | > 90% | ___ |
| False negatives | < 5% | ___ |

---

## 🔧 TUNING GUIDE

### **If Quick Open rate < 80%:**

**Problem:** Hardware không đủ tốt (camera/lighting)

**Solution 1: Lower threshold (aggressive)**
```python
# config.py
QUICK_OPEN_CONFIDENCE = 0.85  # Giảm từ 0.90
```

**Solution 2: Improve hardware**
- Tăng độ sáng
- Điều chỉnh góc camera
- Thêm LED hỗ trợ

---

### **If Accuracy < 90%:**

**Problem:** Mở cửa với plates sai

**Solution: Increase threshold (conservative)**
```python
# config.py
QUICK_OPEN_CONFIDENCE = 0.95  # Tăng lên 0.95
PLATE_MIN_VOTES = 3           # Cần 3 votes
```

---

### **If Still slow (> 0.5s average):**

**Problem:** OCR hoặc preprocessing chậm

**Solution 1: Disable denoise**
```python
# detection_service.py:151
# COMMENT OUT denoise step
# crop = cv2.fastNlMeansDenoisingColored(crop, None, 10, 10, 7, 21)
```

**Solution 2: Increase FPS**
```python
# config.py
DETECTION_FPS = 25  # Tăng từ 18
```

**Solution 3: Reduce voting window**
```python
# config.py
PLATE_VOTE_WINDOW = 0.5  # Giảm từ 0.8
```

---

## ⚠️ COMMON ISSUES

### **Issue 1: Không thấy "⚡ QUICK OPEN"**

**Cause:** Confidence luôn < 90%

**Debug:**
```python
# detection_service.py:175 - Add debug log
print(f"🔍 Detection: {text}, confidence: {confidence:.2f}")
```

**Fix:** Lower `QUICK_OPEN_CONFIDENCE` to 0.85

---

### **Issue 2: Không thấy "⚡ EARLY STOP"**

**Cause:** Votes không giống nhau (normalization issue)

**Debug:**
```python
# plate_tracker.py:163 - Uncomment
print(f"Normalized votes: {normalized_votes}")
print(f"Vote counts: {vote_counts}")
```

**Fix:** Check if OCR returns consistent format

---

### **Issue 3: Vẫn chậm (> 1s)**

**Possible causes:**
1. OCR model quá nặng
2. Preprocessing quá nhiều
3. FPS quá thấp

**Debug:**
```python
# detection_service.py - Add timing
import time
start = time.time()
text = self.ocr_service.recognize(crop)
print(f"OCR took: {time.time() - start:.3f}s")
```

**Fix:** See tuning guide above

---

## ✅ ACCEPTANCE TEST

### **Final Test Before Production:**

**Test với 20 xe khác nhau:**
- [ ] 15+ xe: Quick Open (< 0.3s)
- [ ] 3-5 xe: Early Stop (< 0.5s)
- [ ] 0-2 xe: Full voting (< 0.8s)
- [ ] 0 xe: Failed to open (block)

**Average latency: ___s** (target: < 0.5s)

**Accuracy: ___%** (target: > 90%)

---

## 🎉 DEPLOY TO PRODUCTION

If all tests pass:

```bash
# 1. Backup current code
cp -r backend-edge1 backend-edge1.backup

# 2. Restart app
cd backend-edge1
python app.py

# 3. Monitor logs
tail -f logs/edge.log | grep "⚡"
```

**Watch for:**
- ⚡ QUICK OPEN (should be majority)
- ⚡ EARLY STOP (should be minority)
- ❌ Errors (should be none)

---

## 📈 PRODUCTION MONITORING

### **Daily metrics to track:**
```bash
# Count Quick Opens
grep "⚡ QUICK OPEN" logs/edge.log | wc -l

# Count Early Stops
grep "⚡ EARLY STOP" logs/edge.log | wc -l

# Average confidence
grep "⚡ QUICK OPEN" logs/edge.log | awk '{print $5}' | sed 's/)//' | awk '{sum+=$1; count++} END {print sum/count}'
```

### **Weekly review:**
- Check if Quick Open rate dropping → camera/lighting issue
- Check if accuracy dropping → retrain OCR model
- Check if latency increasing → hardware upgrade needed

---

## 🚨 ROLLBACK PLAN

If production has issues:

```bash
# Disable Quick Open (fallback to voting)
# config.py
QUICK_OPEN_ENABLED = False
EARLY_STOP_ENABLED = True

# Or full rollback
PLATE_VOTE_WINDOW = 1.5
EARLY_STOP_ENABLED = False
```

Restart app immediately!
