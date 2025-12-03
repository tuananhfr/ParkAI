# Frontend P2P Integration Guide

## Tổng Quan

Đã tích hợp P2P Settings UI vào frontend React với Bootstrap 5.

### Files Đã Tạo/Sửa

1. **`frontend/src/components/settings/p2p/P2PSettings.jsx`** (NEW - 600+ lines)
   - Component quản lý cấu hình P2P
   - Hiển thị trạng thái kết nối real-time
   - Quản lý danh sách peer centrals
   - Sync state monitoring

2. **`frontend/src/components/settings/SettingsModal.jsx`** (MODIFIED)
   - Import P2PSettings component
   - Replace CentralSyncServersList với P2PSettings
   - Tab "IP máy chủ central khác" giờ dùng P2PSettings

---

## Features

### 1. P2P Status Overview

Hiển thị tổng quan trạng thái P2P network:
- Trạng thái P2P (Đang chạy / Dừng)
- Số peers đang kết nối
- Tổng số peers
- Central ID hiện tại

### 2. This Central Configuration

Cấu hình central hiện tại:
- **Central ID**: ID duy nhất (ví dụ: central-1)
- **IP Address**: IP trong LAN (ví dụ: 192.168.1.101)
- **P2P Port**: Port WebSocket (mặc định: 9000)
- **API Port**: Port HTTP API (mặc định: 8000)

### 3. Peer Centrals Management

Quản lý danh sách peer centrals:
- **Thêm peer**: Form thêm peer mới
- **Sửa peer**: Inline editing IP và port
- **Xóa peer**: Xóa peer khỏi danh sách
- **Test connection**: Kiểm tra kết nối đến peer

### 4. Real-time Status

Hiển thị trạng thái kết nối từng peer:
- 🟢 **Kết nối** (connected) - Màu xanh
- 🔴 **Mất kết nối** (disconnected) - Màu đỏ
- 🟡 **Đang kết nối** (connecting) - Màu vàng
- ⚪ **Không rõ** (unknown) - Màu xám

### 5. Sync State Monitoring

Hiển thị thông tin đồng bộ với từng peer:
- Thời gian sync lần cuối
- Timestamp sync lần cuối
- Status badge

### 6. Auto Refresh

Tự động refresh status mỗi 10 giây.

---

## API Endpoints Được Sử Dụng

### GET `/api/p2p/config`
Lấy cấu hình P2P hiện tại.

**Response:**
```json
{
  "success": true,
  "config": {
    "this_central": {
      "id": "central-1",
      "ip": "192.168.1.101",
      "p2p_port": 9000,
      "api_port": 8000
    },
    "peer_centrals": [
      {
        "id": "central-2",
        "ip": "192.168.1.102",
        "p2p_port": 9000
      }
    ]
  }
}
```

### PUT `/api/p2p/config`
Lưu cấu hình P2P mới.

**Request:**
```json
{
  "this_central": {...},
  "peer_centrals": [...]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Config saved successfully"
}
```

### GET `/api/p2p/status`
Lấy trạng thái P2P network.

**Response:**
```json
{
  "success": true,
  "running": true,
  "connected_peers": 2,
  "total_peers": 3,
  "peers": [
    {
      "peer_id": "central-2",
      "status": "connected",
      "last_seen": "2025-12-02 10:30:00"
    }
  ]
}
```

### GET `/api/p2p/sync-state`
Lấy trạng thái đồng bộ với từng peer.

**Response:**
```json
{
  "success": true,
  "sync_state": [
    {
      "peer_central_id": "central-2",
      "last_sync_timestamp": 1733140800000,
      "last_sync_time": "2025-12-02 10:30:00",
      "updated_at": "2025-12-02 10:30:05"
    }
  ]
}
```

### POST `/api/p2p/test-connection?peer_id=xxx`
Test kết nối đến peer.

**Response:**
```json
{
  "success": true,
  "message": "Connection successful"
}
```

---

## Usage Flow

### 1. Mở Settings Modal

User click vào Settings → Tab "IP máy chủ central khác"

### 2. Xem Trạng Thái

Component tự động load:
- P2P config từ backend
- P2P status (realtime)
- Sync state với từng peer

### 3. Cấu Hình This Central

User điền:
- Central ID (ví dụ: central-1)
- IP Address (ví dụ: 192.168.1.101)
- P2P Port (mặc định: 9000)
- API Port (mặc định: 8000)

### 4. Thêm Peer

User click "Thêm Peer":
- Điền Peer ID (ví dụ: central-2)
- Điền IP Address (ví dụ: 192.168.1.102)
- Điền P2P Port (mặc định: 9000)
- Click "Thêm"

### 5. Lưu Cấu Hình

User click "Lưu cấu hình P2P":
- Frontend gửi PUT request đến `/api/p2p/config`
- Backend save config vào `config/p2p_config.json`
- Hiện thông báo "Vui lòng khởi động lại server"

### 6. Restart Server

User restart backend server:
```bash
# Ctrl+C để stop
# python app.py để start lại
```

P2P system sẽ load config mới và kết nối đến peers.

---

## UI Components Breakdown

### P2PSettings Component

```jsx
<P2PSettings />
```

**State:**
- `p2pConfig`: Cấu hình P2P
- `p2pStatus`: Trạng thái P2P network
- `syncState`: Trạng thái sync với peers
- `loading`: Loading state
- `saving`: Saving state
- `message`: Success/error message
- `showAddPeer`: Show/hide add peer form
- `newPeer`: New peer form data

**Effects:**
- Load config, status, sync state khi mount
- Auto refresh status/sync state mỗi 10s

**Functions:**
- `fetchP2PConfig()`: Load P2P config
- `fetchP2PStatus()`: Load P2P status
- `fetchSyncState()`: Load sync state
- `handleSaveConfig()`: Save config
- `handleAddPeer()`: Add peer
- `handleRemovePeer()`: Remove peer
- `handleTestConnection()`: Test connection to peer
- `updateThisCentral()`: Update this central config
- `updatePeer()`: Update peer config
- `getPeerStatus()`: Get peer connection status
- `getSyncInfo()`: Get sync info for peer

---

## Styling (Bootstrap 5)

### Status Badges

```html
<!-- Connected -->
<span class="badge bg-success">
  <i class="bi bi-check-circle me-1"></i>
  Kết nối
</span>

<!-- Disconnected -->
<span class="badge bg-danger">
  <i class="bi bi-x-circle me-1"></i>
  Mất kết nối
</span>

<!-- Connecting -->
<span class="badge bg-warning">
  <i class="bi bi-arrow-repeat me-1"></i>
  Đang kết nối
</span>

<!-- Unknown -->
<span class="badge bg-secondary">
  <i class="bi bi-question-circle me-1"></i>
  Không rõ
</span>
```

### Cards

- **Primary Card**: P2P Status Overview (bg-primary)
- **Secondary Card**: This Central Config (bg-secondary)
- **Info Card**: Peer Centrals List (bg-info)
- **Success Card**: Add Peer Form (border-success)

### Icons (Bootstrap Icons)

- `bi-broadcast`: P2P Network
- `bi-server`: Central Server
- `bi-diagram-3`: Peer Network
- `bi-check-circle`: Connected
- `bi-x-circle`: Disconnected
- `bi-arrow-repeat`: Connecting/Sync
- `bi-lightning`: Test Connection
- `bi-trash`: Remove
- `bi-plus-circle`: Add

---

## Validation

### Add Peer Validation

1. **ID và IP bắt buộc**
   - Check `newPeer.id.trim()` và `newPeer.ip.trim()`
   - Hiện lỗi nếu empty

2. **Duplicate ID check**
   - Check `peer_centrals` có peer với ID trùng không
   - Hiện lỗi nếu trùng

3. **IP format** (optional - có thể thêm)
   ```javascript
   const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
   if (!ipPattern.test(newPeer.ip.trim())) {
     setMessage({
       type: "error",
       text: "IP address không hợp lệ"
     });
   }
   ```

---

## Error Handling

### Network Errors

Tất cả fetch requests có try-catch:
```javascript
try {
  const response = await fetch(...);
  const data = await response.json();
  if (data.success) {
    // Success
  } else {
    setMessage({ type: "error", text: data.error });
  }
} catch (err) {
  setMessage({ type: "error", text: "Network error" });
}
```

### Loading States

- **Initial load**: Show spinner khi đang load config
- **Saving**: Disable button, show "Đang lưu..."
- **Testing connection**: Show message "Đang kiểm tra kết nối..."

---

## Testing Scenarios

### Test 1: Cấu hình Central mới

1. Mở Settings → Tab "IP máy chủ central khác"
2. Điền:
   - Central ID: central-1
   - IP Address: 192.168.1.101
   - P2P Port: 9000
   - API Port: 8000
3. Click "Lưu cấu hình P2P"
4. Verify: Message "Đã lưu cấu hình"
5. Restart backend server
6. Verify: P2P status shows "Đang chạy"

### Test 2: Thêm Peer

1. Click "Thêm Peer"
2. Điền:
   - Peer ID: central-2
   - IP Address: 192.168.1.102
   - P2P Port: 9000
3. Click "Thêm"
4. Verify: Peer xuất hiện trong danh sách
5. Click "Lưu cấu hình P2P"
6. Restart backend server
7. Verify: Peer status shows "Kết nối" hoặc "Mất kết nối"

### Test 3: Test Connection

1. Thêm peer (hoặc dùng peer có sẵn)
2. Click nút "Lightning" (Test connection)
3. Verify: Message "Đang kiểm tra kết nối..."
4. Nếu peer online: Message "Kết nối thành công"
5. Nếu peer offline: Message "Không thể kết nối"

### Test 4: Real-time Status

1. Thêm 2 peers
2. Lưu config, restart server
3. Verify: Status auto refresh mỗi 10s
4. Stop 1 peer backend
5. Verify: Sau 10s, status đổi thành "Mất kết nối"
6. Start peer backend lại
7. Verify: Sau 10s, status đổi thành "Kết nối"

### Test 5: Sync State

1. Thêm peer, lưu config, restart server
2. Tạo entry event ở central-1
3. Peer nhận event, sync
4. Refresh frontend
5. Verify: Sync state hiển thị thời gian sync lần cuối

---

## Troubleshooting

### Frontend không load được config

**Lỗi:** `Không thể tải cấu hình P2P`

**Check:**
1. Backend server có chạy không? (`http://localhost:8000`)
2. P2P API endpoints có được integrate vào `app.py` chưa?
3. Check browser console có lỗi CORS không?

**Fix:**
- Start backend server
- Integrate P2P API vào `app.py`
- Add CORS middleware nếu cần

### Status không cập nhật

**Lỗi:** Status luôn hiển thị "Không rõ"

**Check:**
1. Backend có implement `/api/p2p/status` chưa?
2. P2P manager có chạy không?

**Fix:**
- Verify P2P manager started trong `app.py`
- Check logs backend

### Không thể lưu config

**Lỗi:** `Lỗi khi lưu cấu hình`

**Check:**
1. File `config/p2p_config.json` có write permission không?
2. Backend có log lỗi gì không?

**Fix:**
- Check file permissions
- Check backend logs

### Peer status luôn "Mất kết nối"

**Lỗi:** Peer trong danh sách nhưng status "Mất kết nối"

**Check:**
1. Peer backend có chạy không?
2. IP/Port có đúng không?
3. Firewall có block port 9000 không?
4. Mạng LAN có kết nối không?

**Fix:**
- Start peer backend
- Verify IP/Port
- Open firewall port 9000
- Ping peer IP để test network

---

## Next Steps

### Optional Enhancements

1. **Batch Operations**
   - Import/Export peer list từ JSON/CSV
   - Bulk add peers

2. **Visual Network Graph**
   - Hiển thị P2P network dưới dạng graph
   - Sử dụng D3.js hoặc vis.js

3. **Sync Stats**
   - Tổng số events đã sync
   - Sync speed (events/second)
   - Last sync errors

4. **Logs Viewer**
   - Hiển thị P2P logs trong UI
   - Filter logs theo peer

5. **Auto Discovery**
   - Scan mạng LAN tìm central servers
   - Auto add peers

---

## Summary

✅ **Frontend P2P Settings hoàn thành!**

**Features:**
- ✅ Cấu hình This Central
- ✅ Quản lý Peer Centrals
- ✅ Real-time status monitoring
- ✅ Sync state monitoring
- ✅ Test connection
- ✅ Bootstrap 5 styling
- ✅ Auto refresh (10s)
- ✅ Error handling
- ✅ Validation

**Integration:**
- ✅ Đã tích hợp vào SettingsModal
- ✅ Sử dụng P2P API endpoints
- ✅ Bootstrap 5 components

**Next:**
- Test với 2-3 centrals thực tế
- Verify real-time sync
- User training

---

🎉 **Frontend P2P Integration Complete!**
