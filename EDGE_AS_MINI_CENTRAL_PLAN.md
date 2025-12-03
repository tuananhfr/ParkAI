# 🎯 EDGE AS MINI CENTRAL - Implementation Plan

## Mục tiêu

Biến **Backend-Edge** thành **Mini Central** để:
- ✅ Có thể dùng standalone với Frontend (không cần Central)
- ✅ Đơn giản hóa setup lần đầu
- ✅ Sau đó có thể kết nối lên Central khi cần

## 🏗️ Kiến trúc

### Mode 1: Standalone (Setup)
```
Frontend → Backend-Edge (port 5000)
               ↓
           Camera (1 cam duy nhất)
```

### Mode 2: Connected to Central (Production)
```
Frontend → Backend-Central (port 8000)
               ↓
           Backend-Edge-1,2,3,4 (mỗi edge có 1 cam)
               ↓
           Cameras
```

---

## 📋 Implementation Tasks

### Task 1: Backend-Edge - Thêm API Endpoints

Backend-edge đã có database và parking_manager, cần thêm các API endpoints giống Central:

#### 1.1 History API
```python
# app.py

@app.get("/api/parking/history")
async def get_history(limit: int = 100, offset: int = 0, search: str = None):
    """Get parking history"""
    history = parking_manager.db.get_history(limit, offset, search)
    return {"success": True, "history": history, "count": len(history)}
```

#### 1.2 Stats API
```python
@app.get("/api/stats")
async def get_stats():
    """Get parking statistics"""
    stats = parking_manager.db.get_stats()
    return {"success": True, **stats}
```

#### 1.3 Cameras API
```python
@app.get("/api/cameras")
async def get_cameras():
    """Get camera list (chỉ có 1 camera)"""
    import config
    return {
        "success": True,
        "total": 1,
        "online": 1 if camera_manager.is_running else 0,
        "offline": 0 if camera_manager.is_running else 1,
        "cameras": [{
            "id": 1,
            "name": config.CAMERA_NAME,
            "ip": "localhost",  # Auto-fill
            "camera_type": config.CAMERA_TYPE,
            "status": "online" if camera_manager.is_running else "offline"
        }]
    }
```

#### 1.4 Config API (already exists, need to enhance)
```python
@app.get("/api/config")
async def get_config():
    """Get config - Edge specific"""
    import config
    return {
        "success": True,
        "config": {
            "camera": {
                "name": config.CAMERA_NAME,
                "type": config.CAMERA_TYPE,
                "ip": "localhost",  # Auto-fill, readonly
                "confidence_threshold": config.CONFIDENCE_THRESHOLD
            },
            "central_server": {
                "url": config.CENTRAL_SERVER_URL,  # User editable
                "enabled": config.SEND_TO_CENTRAL
            },
            "parking": {
                "fee_base": config.FEE_BASE_HOURS,
                "fee_per_hour": config.FEE_PER_HOUR,
                "fee_overnight": config.FEE_OVERNIGHT,
                "fee_daily_max": config.FEE_DAILY_MAX
            },
            "barrier": {
                "enabled": config.BARRIER_ENABLED,
                "ip": config.BARRIER_IP
            }
        }
    }
```

---

### Task 2: Database - Thêm Methods

File: `backend-edge1/database.py`

#### 2.1 get_history()
```python
def get_history(self, limit=100, offset=0, search=None):
    """Get parking history với pagination và search"""
    with self.lock:
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM entries"
        params = []

        if search:
            query += " WHERE plate_id LIKE ? OR plate_view LIKE ?"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
```

#### 2.2 get_stats()
```python
def get_stats(self):
    """Get parking statistics"""
    with self.lock:
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total vehicles in parking
        cursor.execute("SELECT COUNT(*) FROM entries WHERE status = 'IN'")
        total_in = cursor.fetchone()[0]

        # Today's entries
        cursor.execute("""
            SELECT COUNT(*) FROM entries
            WHERE date(entry_time) = date('now')
        """)
        today_entries = cursor.fetchone()[0]

        # Total revenue today
        cursor.execute("""
            SELECT SUM(fee) FROM entries
            WHERE date(exit_time) = date('now')
        """)
        today_revenue = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "vehicles_in_parking": total_in,
            "today_entries": today_entries,
            "today_exits": today_entries - total_in,
            "today_revenue": today_revenue
        }
```

---

### Task 3: Frontend Settings UI - Auto-fill Fields

File: `frontend/src/components/settings/SettingsModal.jsx`

#### 3.1 Detect Backend Type

```javascript
const [backendType, setBackendType] = useState(null); // "edge" | "central"

useEffect(() => {
  // Detect backend type từ config response
  const detectBackendType = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/config`);
      const data = await response.json();

      if (data.config.camera?.ip === "localhost") {
        setBackendType("edge");
      } else {
        setBackendType("central");
      }
    } catch (err) {
      console.error("Failed to detect backend type");
    }
  };

  detectBackendType();
}, []);
```

#### 3.2 Edge: Camera IP readonly

```jsx
{backendType === "edge" && (
  <div className="alert alert-info">
    <i className="bi bi-info-circle me-2"></i>
    Edge mode: Camera IP tự động (localhost)
  </div>
)}

<input
  type="text"
  className="form-control form-control-sm"
  value="localhost"
  disabled={backendType === "edge"}  // Readonly for edge
  placeholder="localhost"
/>
```

#### 3.3 Edge: Central URL editable

```jsx
<label className="form-label small">
  IP/URL máy chủ Central (để trống nếu standalone)
</label>
<input
  type="text"
  className="form-control form-control-sm"
  value={config.central_server?.url || ""}
  onChange={(e) => updateConfig("central_server", "url", e.target.value)}
  placeholder="http://192.168.1.100:8000"
/>
```

#### 3.4 Central: This Central IP readonly

```jsx
{backendType === "central" && (
  <div className="alert alert-info">
    <i className="bi bi-info-circle me-2"></i>
    Central mode: IP tự động điền từ network interface
  </div>
)}

<input
  type="text"
  className="form-control form-control-sm"
  value={config.central_server?.ip || "auto"}
  disabled={backendType === "central"}  // Readonly for central
  placeholder="Auto-detected"
/>
```

---

### Task 4: Auto-detect IP

#### 4.1 Backend-Edge: Camera IP = localhost

```python
# config.py
CAMERA_IP = "localhost"  # Always localhost for edge
```

#### 4.2 Backend-Central: This Central IP = auto-detect

```python
# backend-central/app.py

def get_local_ip():
    """Auto-detect local IP"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

@app.on_event("startup")
async def startup():
    # ...
    # Auto-detect IP cho P2P config
    local_ip = get_local_ip()
    print(f"📍 Auto-detected local IP: {local_ip}")

    # Update p2p_config.json nếu IP = "auto"
    config_file = "config/p2p_config.json"
    with open(config_file, 'r') as f:
        p2p_config = json.load(f)

    if p2p_config["this_central"]["ip"] == "auto":
        p2p_config["this_central"]["ip"] = local_ip
        with open(config_file, 'w') as f:
            json.dump(p2p_config, f, indent=2)
        print(f"✅ Updated P2P config with IP: {local_ip}")
```

---

## 🔄 Migration Plan

### Step 1: Update Backend-Edge

1. ✅ Thêm API endpoints: `/api/parking/history`, `/api/stats`, `/api/cameras`
2. ✅ Enhance `/api/config` endpoint
3. ✅ Thêm database methods: `get_history()`, `get_stats()`
4. ✅ Set `CAMERA_IP = "localhost"` (readonly)

### Step 2: Update Frontend

1. ✅ Detect backend type (edge vs central)
2. ✅ Camera IP readonly cho edge
3. ✅ Central URL editable cho edge
4. ✅ This Central IP readonly cho central

### Step 3: Update Backend-Central

1. ✅ Auto-detect local IP
2. ✅ Update P2P config with auto-detected IP
3. ✅ Edge cameras IP editable (manual config)

---

## 📖 User Experience

### Scenario 1: Setup Edge Standalone

```bash
# 1. Start backend-edge
cd backend-edge1
python app.py

# 2. Start frontend (point to edge)
cd frontend
VITE_CENTRAL_URL=http://localhost:5000 npm run dev

# 3. Open browser: http://localhost:5173
# 4. Go to Settings:
#    - Camera IP: "localhost" (grayed out, readonly)
#    - Camera Name: "Cổng vào A" (editable)
#    - Central URL: "" (empty, editable - optional)
#    - Barrier IP: "192.168.1.10" (editable)
```

### Scenario 2: Connect Edge to Central

```bash
# 1. Start backend-central
cd backend-central
python app.py
# → Auto-detect IP: 192.168.1.100

# 2. Start backend-edge
cd backend-edge1
python app.py

# 3. Frontend → Edge Settings:
#    - Central URL: "http://192.168.1.100:8000" (fill this)
#    - Click "Lưu cấu hình"
# → Edge sẽ gửi events lên Central

# 4. Frontend → Central (switch URL)
cd frontend
VITE_CENTRAL_URL=http://192.168.1.100:8000 npm run dev

# 5. Central Settings → P2P:
#    - This Central IP: "192.168.1.100" (auto-filled, readonly)
#    - Edge cameras: Add manually with IPs
```

---

## ✅ Validation Checklist

### Edge Standalone Mode
- [ ] Frontend kết nối edge port 5000
- [ ] Camera IP hiển thị "localhost" và grayed out
- [ ] Central URL để trống hoặc có thể điền
- [ ] History API trả về data từ edge database
- [ ] Stats API trả về thống kê đúng
- [ ] Camera status hiển thị online/offline

### Edge Connected to Central
- [ ] Edge gửi events lên Central
- [ ] Central nhận events từ edge
- [ ] Frontend kết nối central port 8000
- [ ] P2P sync hoạt động

### Central P2P Mode
- [ ] This Central IP auto-detect
- [ ] IP hiển thị và grayed out
- [ ] Edge cameras IP phải điền manual
- [ ] P2P config lưu đúng

---

## 🎉 Benefits

### For Users
- ✅ Setup đơn giản: Chỉ cần Edge + Frontend
- ✅ Không cần cài Central ngay từ đầu
- ✅ Có thể test Edge trước khi deploy full system

### For Developers
- ✅ Edge và Central có cùng API interface
- ✅ Frontend không cần thay đổi logic
- ✅ Dễ scale: Edge → Central → P2P

### For Deployment
- ✅ Edge standalone: 1 máy
- ✅ Edge + Central: 2 máy
- ✅ Multi-Central P2P: 10+ máy

---

## 📝 Notes

- **Camera IP**: Edge luôn dùng `localhost`, Central dùng IP thật của edge
- **Central IP**: Edge có thể để trống (standalone), Central auto-detect
- **P2P IP**: Central auto-detect, không cho sửa
- **Readonly fields**: Dùng `disabled` attribute trong input field
- **Backend type detection**: Check config response để phân biệt edge vs central

---

**Status**: 📋 Planning Complete - Ready to implement!
