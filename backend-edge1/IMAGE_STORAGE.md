# Image Storage & Sync to Central

## ✅ Đã Implement

**Approach:** Edge lưu local + sync ảnh (base64) lên Central → Central lưu BLOB → Frontend fetch từ Central

---

## 📁 Architecture

```
Edge (Raspberry Pi)                Central Server               Frontend
─────────────────                 ──────────────               ─────────
1. Detect + Capture
   ↓
2. OCR Success
   ↓
3. Save local file
   data/plates/29A12345_xxx.jpg
   ↓
4. Encode base64
   ↓
5. Send to Central  ────────────→ 6. Receive event
                                      ↓
                                   7. Decode base64
                                      ↓
                                   8. Store BLOB
                                      in database
                                      ↓
                                   9. Serve via API  ─────────→ 10. Fetch & Display
                                      /api/plate-image/{id}        <img src="..." />
```

---

## 🔄 Detailed Flow

### **Edge (backend-edge1):**

```python
# 1. IMX500 detect → Confidence >= 0.60
# 2. CAPTURE ảnh tĩnh (crop)
# 3. OCR 1-2 lần
# 4. OCR SUCCESS → Process:

# A. Save local file
image_filename = self._save_plate_image(text, frame)
# → Saved: data/plates/29A12345_1732867234.jpg

# B. Encode to base64
import base64
_, buffer = cv2.imencode('.jpg', frame)
image_base64 = base64.b64encode(buffer).decode('utf-8')

# C. Send to Central
self.central_sync.send_event("DETECTION", {
    'plate_text': '29A12345',
    'confidence': 0.95,
    'bbox': [x, y, w, h],
    'plate_image': image_base64,  # ← Base64 string
    'camera_id': 1,
    'timestamp': time.time()
})
```

### **Central (backend-central):**

```python
# 1. Receive event at /api/edge/event
# 2. Extract data:
plate_image_base64 = data.get('plate_image')

# 3. Decode base64 → bytes
plate_image_bytes = base64.b64decode(plate_image_base64)

# 4. Store in database
db.add_vehicle_entry(
    plate_id='29A12345',
    plate_view='29A-123.45',
    entry_time='2025-11-29 10:30:00',
    camera_id=1,
    camera_name='Cổng vào A',
    confidence=0.95,
    source='auto',
    plate_image=plate_image_bytes  # ← BLOB
)

# 5. Serve via API
@app.get("/api/plate-image/{vehicle_id}")
async def get_plate_image(vehicle_id: int):
    # Query database
    result = db.query("SELECT plate_image FROM vehicles WHERE id = ?", vehicle_id)
    # Return JPEG
    return Response(content=result['plate_image'], media_type="image/jpeg")
```

### **Frontend:**

```jsx
// Fetch vehicle history
fetch('http://central:8000/api/parking/history')
  .then(res => res.json())
  .then(data => {
    const vehicles = data.history;

    vehicles.forEach(vehicle => {
      // Display plate image
      if (vehicle.id) {
        const imageUrl = `http://central:8000/api/plate-image/${vehicle.id}`;

        // Render
        <img
          src={imageUrl}
          alt={vehicle.plate_view}
          style={{ maxWidth: '200px' }}
        />
      }
    });
  });
```

---

## 💾 Database Schema

### **Central Database (SQLite):**

```sql
CREATE TABLE vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_id TEXT NOT NULL UNIQUE,
    plate_view TEXT NOT NULL,

    entry_time TEXT NOT NULL,
    entry_camera_id INTEGER,
    entry_camera_name TEXT,
    entry_confidence REAL,
    entry_source TEXT,

    exit_time TEXT,
    exit_camera_id INTEGER,
    exit_camera_name TEXT,
    exit_confidence REAL,
    exit_source TEXT,

    duration TEXT,
    fee INTEGER DEFAULT 0,
    status TEXT NOT NULL,

    plate_image BLOB,  -- ← Ảnh biển số (binary)

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📊 Storage Comparison

### **Edge Storage (Local Files):**
- **Purpose:** Backup & local debugging
- **Location:** `data/plates/29A12345_xxx.jpg`
- **Size:** ~20-50KB/image
- **Retention:** Can implement auto-cleanup (30 days)
- **Access:** Edge API only (not used by Frontend)

### **Central Storage (Database BLOB):**
- **Purpose:** Production serving to Frontend
- **Location:** SQLite database `data/central.db`
- **Size:** ~30-70KB/image (base64 → binary)
- **Retention:** Permanent (unless manual cleanup)
- **Access:** Central API `/api/plate-image/{id}`

---

## 🚀 Network & Performance

### **Bandwidth Usage:**

```
1 xe:
- Ảnh crop: 800x300px
- JPEG quality 85: ~30-50KB
- Base64 overhead: +33% → ~40-70KB
- Edge → Central: ~70KB/vehicle

100 xe/ngày:
- Total: ~7MB/ngày
- Pi WiFi (54Mbps): Chỉ mất ~1s tổng
- Central bandwidth: ~210MB/tháng
```

### **Latency:**

```
Edge → Central (LAN):
- Encode base64: ~2-5ms
- Network transfer: ~10-50ms (7MB @ 54Mbps WiFi)
- Decode + DB insert: ~5-10ms
→ Total: ~20-65ms (acceptable!)

Frontend ← Central:
- DB query: ~1-3ms
- Network transfer: ~10-50ms (LAN)
→ Total: ~15-55ms (fast!)
```

### **Concurrent Access:**

```
FastAPI async:
- Central có thể serve 50+ images/s
- Database locking: SQLite handles well
- Frontend có thể load nhiều ảnh cùng lúc
```

---

## 🔒 Security

### **Path Traversal Prevention:**

```python
# Edge: Filename sanitization
filename = f"{plate_text}_{int(time.time())}.jpg"
# → Safe: No user input in path

# Central: ID-based lookup
vehicle_id = int(vehicle_id)  # Integer only
query = "SELECT plate_image FROM vehicles WHERE id = ?"
# → Safe: No path traversal possible
```

### **CORS:**

```python
# Both Edge & Central have CORS enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🧪 Testing

### **1. Test Edge → Central Sync:**

```bash
# Start Edge
cd backend-edge1
make run

# Start Central (separate terminal)
cd backend-central
python app.py

# Trigger detection:
# - Đưa biển số vào camera
# - Chờ capture (conf >= 0.60)
# - Chờ OCR success

# Check Edge logs:
📸 CAPTURED! bbox=355x101px, conf=0.65
🔍 OCR attempt 1/2 on captured frame...
✅ OCR SUCCESS: 29A12345
💾 Saved plate image: data/plates/29A12345_1732867234.jpg
📤 Sent plate image to Central: 29A12345

# Check Central logs:
✅ Received plate image: 45678 bytes
✅ Event processed: DETECTION from Camera 1 - Xe 29A-123.45 VÀO bãi
```

### **2. Test Central API:**

```bash
# Query vehicle ID
curl http://localhost:8000/api/parking/history | jq '.history[0].id'
# → 123

# Test image endpoint
curl http://localhost:8000/api/plate-image/123 --output test.jpg

# View image
open test.jpg  # macOS
xdg-open test.jpg  # Linux
start test.jpg  # Windows
```

### **3. Test Frontend:**

```jsx
// In CameraView or History component
const CENTRAL_URL = 'http://192.168.0.100:8000';

// Fetch history
fetch(`${CENTRAL_URL}/api/parking/history`)
  .then(res => res.json())
  .then(data => {
    console.log('Vehicles:', data.history);

    // First vehicle image
    const firstVehicle = data.history[0];
    if (firstVehicle?.id) {
      const imgUrl = `${CENTRAL_URL}/api/plate-image/${firstVehicle.id}`;
      console.log('Image URL:', imgUrl);
      // Test in browser DevTools → Network tab
    }
  });
```

---

## 🎯 Frontend Integration

### **React Example:**

```jsx
import { useState, useEffect } from 'react';

function VehicleHistory() {
  const [vehicles, setVehicles] = useState([]);
  const CENTRAL_URL = 'http://192.168.0.100:8000';

  useEffect(() => {
    fetch(`${CENTRAL_URL}/api/parking/history`)
      .then(res => res.json())
      .then(data => setVehicles(data.history));
  }, []);

  return (
    <div>
      {vehicles.map(vehicle => (
        <div key={vehicle.id} className="vehicle-card">
          <h3>{vehicle.plate_view}</h3>
          <p>Vào: {vehicle.entry_time}</p>
          <p>Camera: {vehicle.entry_camera_name}</p>

          {/* Plate Image */}
          {vehicle.id && (
            <img
              src={`${CENTRAL_URL}/api/plate-image/${vehicle.id}`}
              alt={`Biển số ${vehicle.plate_view}`}
              style={{
                maxWidth: '300px',
                border: '2px solid #4CAF50',
                borderRadius: '8px'
              }}
              onError={(e) => {
                e.target.style.display = 'none';
                console.error(`Image not found for vehicle ${vehicle.id}`);
              }}
            />
          )}

          {vehicle.status === 'OUT' && (
            <>
              <p>Ra: {vehicle.exit_time}</p>
              <p>Thời gian: {vehicle.duration}</p>
              <p>Phí: {vehicle.fee.toLocaleString()} VNĐ</p>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## 📋 Complete Data Flow Example

### **Scenario: Xe 29A-123.45 vào bãi**

```
1. Edge Detection:
   - IMX500 detect @ confidence 0.67
   - Trigger capture (full frame)
   - OCR attempt 1: "29A12345" ✅
   - Save: data/plates/29A12345_1732867234.jpg

2. Edge → Central:
   POST http://central:8000/api/edge/event
   {
     "type": "DETECTION",
     "camera_id": 1,
     "camera_name": "Cổng vào A",
     "camera_type": "ENTRY",
     "data": {
       "plate_text": "29A12345",
       "confidence": 0.95,
       "source": "auto",
       "plate_image": "/9j/4AAQSkZJRgABAQEA..."  // base64
     }
   }

3. Central Processing:
   - Decode base64 → 45,678 bytes
   - Validate plate: 29A12345 → 29A-123.45 ✅
   - Check duplicate: None ✅
   - Insert database:
     INSERT INTO vehicles (
       plate_id, plate_view, entry_time,
       entry_camera_id, entry_camera_name,
       confidence, source, status, plate_image
     ) VALUES (
       '29A12345', '29A-123.45', '2025-11-29 10:30:00',
       1, 'Cổng vào A', 0.95, 'auto', 'IN', <BLOB>
     )
   - vehicle_id = 123

4. Frontend Query:
   GET http://central:8000/api/parking/history
   Response:
   {
     "success": true,
     "history": [
       {
         "id": 123,
         "plate_id": "29A12345",
         "plate_view": "29A-123.45",
         "entry_time": "2025-11-29 10:30:00",
         "entry_camera_name": "Cổng vào A",
         "status": "IN",
         ...
       }
     ]
   }

5. Frontend Image:
   GET http://central:8000/api/plate-image/123
   Response: <JPEG binary data>
   Display: <img src="http://central:8000/api/plate-image/123" />
```

---

## 🔧 Maintenance

### **Database Size Management:**

```python
# Check database size
import os
db_size = os.path.getsize('data/central.db')
print(f"Database size: {db_size / 1024 / 1024:.2f} MB")

# Estimate:
# 100 vehicles/day × 60KB/image × 30 days = ~180MB/month
# SQLite can handle GBs easily
```

### **Cleanup Old Images (Optional):**

```python
# Delete vehicles older than 90 days
import sqlite3
conn = sqlite3.connect('data/central.db')
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM vehicles
    WHERE created_at < DATE('now', '-90 days')
""")

rows_deleted = cursor.rowcount
conn.commit()
conn.close()

print(f"Deleted {rows_deleted} old vehicle records")
```

### **VACUUM Database:**

```bash
# Reclaim space after deletions
sqlite3 data/central.db "VACUUM;"
```

---

## ✅ Implementation Checklist

- [x] Edge: Save plate images to local files
- [x] Edge: Encode images to base64
- [x] Edge: Send images via central_sync service
- [x] Central: Receive events with image data
- [x] Central: Decode base64 to bytes
- [x] Central: Store images as BLOB in database
- [x] Central: Add migration for existing databases
- [x] Central: API endpoint `/api/plate-image/{vehicle_id}`
- [ ] Frontend: Fetch and display images from Central
- [ ] Frontend: Error handling for missing images
- [ ] Testing: End-to-end flow

---

## 🚀 Next Steps

### **Phase 1: Basic Display (Current)**
- ✅ Backend complete
- ⏳ Frontend integration
- ⏳ Testing

### **Phase 2: Advanced Features (Future)**
- Thumbnail generation (smaller images for list view)
- Image compression optimization
- Lazy loading for performance
- Zoom/lightbox for full-size view
- Export reports with images (PDF)

### **Phase 3: Analytics (Future)**
- Image quality metrics
- OCR confidence correlation
- Failed detection analysis
- Storage usage monitoring

---

Last updated: 2025-11-29
