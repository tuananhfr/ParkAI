# Frontend Features - App1.jsx

## Overview

App1.jsx là giao diện quản lý bãi xe với đầy đủ tính năng:
- Camera realtime (WebRTC)
- Tự động nhận diện biển số (OCR)
- Mở cửa barrier (VÀO/RA)
- Lịch sử xe vào/ra
- Thống kê realtime

---

## Components

### 1. **CameraView** - Camera + Barrier Control

**Features:**
- ✅ WebRTC video stream realtime
- ✅ Canvas overlay để vẽ detection boxes
- ✅ **Form cố định** với các field rõ ràng (như app chuyên nghiệp)
- ✅ Auto-fill biển số khi OCR đọc được
- ✅ Warning khi không đọc được biển số
- ✅ Manual input (user có thể nhập tay)
- ✅ Icon hiển thị source (Robot icon = Auto, Pencil icon = Manual)
- ✅ Progress bar hiển thị độ chính xác OCR
- ✅ Thời gian realtime (update mỗi giây)
- ✅ Hiển thị camera info (tên, type, location) - disabled field
- ✅ Nút mở cửa (VÀO hoặc RA tùy camera type)

**States:**
```javascript
- plateText: Biển số (auto-fill hoặc manual)
- plateSource: "auto" | "manual"
- plateConfidence: 0.0 - 1.0
- cannotReadPlate: Warning hiển thị khi OCR không đọc được
- isOpening: Loading state khi đang mở cửa
- cameraInfo: {id, name, type, location}
- userEdited: Track xem user có edit text không
- currentTime: Date object (update mỗi giây)
```

**Form Layout (Cố định):**
```
┌─────────────────────────────────┐
│ ℹ️  Thông tin xe                │
├─────────────────────────────────┤
│ # Biển số xe                    │
│ [30G56789        ] [🤖]         │
│                                 │
│ 🕐 Thời gian                    │
│ [27/01/2025, 14:30:45]          │
│                                 │
│ 📹 Camera                       │
│ [Cổng vào A (VÀO)]              │
│                                 │
│ 🚀 Độ chính xác                 │
│ [████████░░] 92%                │
│                                 │
│ [Mở cửa VÀO]                    │
└─────────────────────────────────┘
```

**Logic:**
```
OCR đọc được text
  → Auto-fill vào input
  → Badge: "Auto (92%)"
  → User có thể edit → Badge chuyển sang "Manual"

OCR không đọc được
  → Hiển thị warning "Không đọc được biển số"
  → User nhập tay
  → Badge: "Manual"

User nhấn "Mở cửa"
  → POST /api/open-barrier
  → Lưu vào DB (SQLite)
  → Mở barrier (nếu enabled)
  → Refresh history panel
  → Reset form
```

---

### 2. **HistoryPanel** - Lịch sử + Thống kê

**Features:**
- ✅ Hiển thị lịch sử xe VÀO/RA
- ✅ Stats realtime (VÀO, RA, Trong bãi, Doanh thu)
- ✅ Filter: Tất cả / Hôm nay / VÀO / RA
- ✅ Auto-refresh mỗi 10s
- ✅ Manual refresh button
- ✅ Hiển thị:
  - Biển số (formatted: 30G-123.45)
  - Thời gian VÀO + tên camera
  - Thời gian RA + tên camera (nếu đã ra)
  - Duration (2 giờ 30 phút)
  - Fee (tính tiền dựa vào thời gian)
  - Badge: IN (green) / OUT (gray)

**Stats Display:**
```
╔═══════════════════════════════╗
║  VÀO    RA    Trong bãi    Thu ║
║   23    22        1       450K ║
╚═══════════════════════════════╝
```

**History Item:**
```
╔════════════════════════════════╗
║ 30G-123.45              [IN]   ║
║ ↓ 2025-01-27 10:30 (Vào A)     ║
║ ↑ 2025-01-27 12:45 (Ra A)      ║
║                   2 giờ 15 phút║
║                      25,000đ   ║
╚════════════════════════════════╝
```

---

## Layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌──────────────────┐  ┌──────────────────────┐   │
│  │  Camera View     │  │   History Panel      │   │
│  │  (70%)           │  │   (30%)              │   │
│  │                  │  │                      │   │
│  │  [Video]         │  │  Stats: VÀO RA Fee  │   │
│  │  [Canvas overlay]│  │  Filter: [buttons]   │   │
│  │                  │  │  List: [...items]    │   │
│  │  Input: 30G...   │  │                      │   │
│  │  [Mở cửa VÀO]    │  │                      │   │
│  └──────────────────┘  └──────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Responsive:**
- Desktop: 70% camera / 30% history (side-by-side)
- Mobile: Full width camera, history dưới (stack)

---

## API Integration

### Camera Info
```javascript
GET /api/camera/info
→ { camera: { id: 1, name: "Cổng vào A", type: "ENTRY" } }
```

### Open Barrier
```javascript
POST /api/open-barrier
Body: { plate_text: "30G56789", confidence: 0.92, source: "auto" }
→ { success: true, action: "ENTRY", message: "Xe 30G-567.89 VÀO" }
```

### History
```javascript
GET /api/history?today_only=true&status=IN
→ { success: true, count: 10, stats: {...}, history: [...] }
```

---

## UX Flow

### Scenario 1: OCR đọc được text

```
1. Xe vào → Camera detect
2. OCR đọc: "30G56789"
3. Auto-fill input: "30G56789"
4. Badge: "Auto (92%)"
5. User check → OK
6. Nhấn "Mở cửa VÀO"
7. → Lưu DB, mở barrier
8. → History panel refresh
9. → Form reset
```

### Scenario 2: OCR không đọc được

```
1. Xe vào → Camera detect
2. OCR fail (chỉ thấy box, không có text)
3. Warning: "Không đọc được biển số"
4. User nhập tay: "30G56789"
5. Badge: "Manual"
6. Nhấn "Mở cửa VÀO"
7. → Lưu DB với source="manual"
```

### Scenario 3: User edit text auto

```
1. OCR auto-fill: "30G56788" (sai)
2. User sửa → "30G56789"
3. Badge: "Auto (92%)" → "Manual"
4. Nhấn "Mở cửa"
5. → Lưu với source="manual"
```

---

## Error Handling

### WebRTC Connection Lost
```javascript
- Hiển thị error: "WebRTC connection lost"
- Auto-reconnect sau 3 giây
- Badge connection: Red → Gray → Green (khi reconnect)
```

### API Error
```javascript
- Xe đã VÀO chưa RA → Alert error message
- Invalid plate → Alert "Biển số không hợp lệ"
- Network error → Alert "Lỗi kết nối"
```

### WebSocket Disconnected
```javascript
- Auto-reconnect sau 3 giây
- Ping/pong keep-alive mỗi 5s
- Warning: Boxes sẽ biến mất khi disconnect
```

---

## Configuration

### Backend URL
```javascript
const BACKEND_URL = "http://192.168.0.144:5000";
const WS_URL = "ws://192.168.0.144:5000/ws/detections";
```

### Polling Intervals
```javascript
- History refresh: 10 seconds
- WebSocket ping: 5 seconds
- Detection box timeout: 1 second
```

---

## Testing Checklist

### Camera View
- [ ] Video stream loads
- [ ] Detection boxes appear
- [ ] Auto-fill works when OCR reads text
- [ ] Warning appears when OCR fails
- [ ] Manual input works
- [ ] Badge shows correct source
- [ ] Button opens barrier
- [ ] Form resets after submit
- [ ] Camera info displays (name, type)

### History Panel
- [ ] Stats display correctly
- [ ] Filter buttons work
- [ ] List shows entries
- [ ] Auto-refresh works
- [ ] Manual refresh works
- [ ] Entry details correct (time, duration, fee)
- [ ] IN/OUT badge colors correct

### Integration
- [ ] History refreshes after opening barrier
- [ ] Multiple cameras work (different IDs)
- [ ] Camera ENTRY shows green button
- [ ] Camera EXIT shows red button
- [ ] Fee calculation correct
- [ ] Duplicate detection prevented (xe đã VÀO)

---

## Future Enhancements

### Phase 2
- [ ] Print receipt (in hóa đơn)
- [ ] Export to Excel/PDF
- [ ] Search by plate number
- [ ] Date range filter
- [ ] Dashboard với charts
- [ ] Camera snapshot khi detect
- [ ] SMS notification
- [ ] Multi-language support

### Phase 3
- [ ] Face recognition
- [ ] Vehicle type detection (car/motor)
- [ ] Monthly pass management
- [ ] Payment gateway integration
- [ ] Mobile app (React Native)
