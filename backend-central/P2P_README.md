# P2P Sync System - Phase 1 Complete ✅

## 🎉 Đã Hoàn Thành

Phase 1 - P2P Core Infrastructure đã xong! Hệ thống giờ có khả năng:
- ✅ Kết nối P2P giữa nhiều central servers qua WebSocket
- ✅ Tự động reconnect khi peer offline
- ✅ Heartbeat keep-alive
- ✅ Config management qua API
- ✅ Database schema hỗ trợ P2P sync

---

## 📁 Files Đã Tạo

```
backend-central/
├── p2p/                              # P2P Module
│   ├── __init__.py                  # Module entry point
│   ├── protocol.py                  # Message types & validation
│   ├── config_loader.py             # Load P2P config từ JSON
│   ├── server.py                    # WebSocket server
│   ├── client.py                    # WebSocket client
│   ├── manager.py                   # Main orchestrator
│   └── database_migration.py        # DB migration script
│
├── config/
│   └── p2p_config.json              # P2P configuration file
│
├── p2p_api.py                       # API endpoints cho frontend
├── P2P_INTEGRATION_GUIDE.md         # Hướng dẫn tích hợp
└── P2P_README.md                    # File này
```

---

## 🚀 Cách Sử Dụng

### 1. Config P2P Centrals

Chỉnh sửa file `config/p2p_config.json`:

**Central-1:**
```json
{
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
    },
    {
      "id": "central-3",
      "ip": "192.168.1.103",
      "p2p_port": 9000
    }
  ]
}
```

**Hoặc để trống nếu chỉ có 1 central (standalone):**
```json
{
  "this_central": {
    "id": "central-1",
    "ip": "127.0.0.1",
    "p2p_port": 9000,
    "api_port": 8000
  },
  "peer_centrals": []
}
```

### 2. Integrate vào app.py

Xem file [P2P_INTEGRATION_GUIDE.md](P2P_INTEGRATION_GUIDE.md) để biết chi tiết.

**Tóm tắt:**
1. Import P2P modules
2. Khởi tạo `p2p_manager` trong startup
3. Stop trong shutdown
4. Include P2P API router

### 3. Chạy Server

```bash
cd backend-central
python app.py
```

### 4. Kiểm Tra P2P Status

```bash
# Via API
curl http://localhost:8000/api/p2p/status

# Expected response:
{
  "success": true,
  "this_central": "central-1",
  "running": true,
  "standalone_mode": false,
  "total_peers": 2,
  "connected_peers": 2,
  "peers": [...]
}
```

---

## 🌐 API Endpoints

### GET /api/p2p/config
Lấy P2P configuration hiện tại

**Response:**
```json
{
  "success": true,
  "config": {
    "this_central": {...},
    "peer_centrals": [...]
  }
}
```

### PUT /api/p2p/config
Cập nhật P2P configuration

**Request Body:**
```json
{
  "this_central": {
    "id": "central-1",
    "ip": "192.168.1.101",
    "p2p_port": 9000,
    "api_port": 8000
  },
  "peer_centrals": [...]
}
```

### GET /api/p2p/status
Lấy trạng thái P2P connections

**Response:**
```json
{
  "success": true,
  "this_central": "central-1",
  "running": true,
  "standalone_mode": false,
  "total_peers": 3,
  "connected_peers": 2,
  "messages_sent": 150,
  "messages_received": 148,
  "peers": [
    {
      "peer_id": "central-2",
      "peer_ip": "192.168.1.102",
      "peer_port": 9000,
      "connected": true,
      "last_ping_time": "2025-12-02T10:30:00"
    }
  ]
}
```

---

## 🎨 Frontend Integration

User sẽ quản lý P2P config từ frontend settings.

**Example React/Vue component:**

```javascript
// Get P2P status
const getP2PStatus = async () => {
  const response = await fetch('http://localhost:8000/api/p2p/status')
  const data = await response.json()

  console.log('Connected peers:', data.connected_peers)
  console.log('Peers:', data.peers)
}

// Update P2P config
const updateP2PConfig = async (config) => {
  const response = await fetch('http://localhost:8000/api/p2p/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  })

  const result = await response.json()
  console.log(result.message)
}
```

**UI Mockup:**
```
┌─────────────────────────────────────────┐
│  P2P Central Servers Configuration     │
├─────────────────────────────────────────┤
│                                         │
│  This Central:                          │
│  ├─ ID:       central-1                │
│  ├─ IP:       192.168.1.101            │
│  ├─ P2P Port: 9000                     │
│  └─ API Port: 8000                     │
│                                         │
│  Peer Centrals:                        │
│  ┌─────────────────────────────────┐  │
│  │ Central-2                        │  │
│  │ IP: 192.168.1.102    Port: 9000 │  │
│  │ Status: ✅ Connected            │  │
│  └─────────────────────────────────┘  │
│                                         │
│  ┌─────────────────────────────────┐  │
│  │ Central-3                        │  │
│  │ IP: 192.168.1.103    Port: 9000 │  │
│  │ Status: ❌ Offline              │  │
│  └─────────────────────────────────┘  │
│                                         │
│  [+ Add Peer]  [Save]                  │
└─────────────────────────────────────────┘
```

---

## 🗄️ Database Changes

Migration tự động thêm columns vào bảng `history`:

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | TEXT | Unique event ID (format: `central-1_timestamp_plate_id`) |
| `source_central` | TEXT | Central nào tạo event này |
| `edge_id` | TEXT | Edge camera nào detect |
| `sync_status` | TEXT | `LOCAL` (tạo ở central này) hoặc `SYNCED` (nhận từ peer) |

Table mới: `p2p_sync_state`
- Track last sync timestamp với mỗi peer
- Dùng để sync missed events khi reconnect

---

## 🔧 Troubleshooting

### P2P Server không start
**Error:** `Address already in use`

**Fix:**
1. Kiểm tra port 9000 đã được sử dụng: `netstat -ano | findstr 9000`
2. Đổi port trong `p2p_config.json`

### Peer không connect
**Symptom:** `connected_peers: 0`

**Fix:**
1. Kiểm tra firewall cho phép port 9000
2. Ping IP của peer: `ping 192.168.1.102`
3. Kiểm tra peer server có đang chạy không
4. Kiểm tra IP/port trong config có đúng không

### Config không load
**Error:** `Failed to load P2P config`

**Fix:**
1. Kiểm tra file `config/p2p_config.json` tồn tại
2. Validate JSON syntax: https://jsonlint.com
3. Kiểm tra permissions của file

---

## 📝 Next Steps - Phase 2

Phase 1 đã xây xong **infrastructure**. Tiếp theo:

### Phase 2: Event Broadcasting & Handling (3-4 ngày)
- [ ] Khi ENTRY → broadcast P2P event
- [ ] Khi EXIT → broadcast P2P event
- [ ] Nhận event từ peer → lưu vào DB
- [ ] Deduplication logic (race condition)

### Phase 3: Conflict Resolution (2-3 ngày)
- [ ] Timestamp-based conflict resolution
- [ ] Handle duplicate entries
- [ ] Eventual consistency

### Phase 4: Sync on Reconnect (2 ngày)
- [ ] Track last sync time per peer
- [ ] SYNC_REQUEST/RESPONSE protocol
- [ ] Merge missed events

### Phase 5: Testing (2-3 ngày)
- [ ] Test với 2-3 centrals
- [ ] Test race conditions
- [ ] Test network partition
- [ ] Test reconnect scenarios

---

## 💡 Design Decisions

### Tại sao dùng WebSocket thay vì HTTP?
- **Real-time:** Event được broadcast ngay lập tức
- **Persistent connection:** Giảm overhead của HTTP handshake
- **Auto-reconnect:** Tự động kết nối lại khi peer offline

### Tại sao có cả Server và Client?
- **Server:** Nhận connections từ peers (inbound)
- **Client:** Connect đến peers (outbound)
- **Dual mode:** Đảm bảo P2P mesh network, không phụ thuộc ai là initiator

### Tại sao config qua file JSON thay vì DB?
- **Simplicity:** Dễ edit, backup, deploy
- **Portability:** Copy file là xong
- **Frontend control:** User quản lý qua UI, backend tự sync

---

## 🙏 Notes

- **Không phá vỡ logic hiện tại:** Tất cả code cũ vẫn hoạt động bình thường
- **Standalone mode:** Nếu `peer_centrals` rỗng, central hoạt động độc lập
- **Zero downtime:** P2P có thể start/stop mà không ảnh hưởng API chính
- **Frontend first:** User config từ UI, không cần SSH vào server

---

## 📞 Support

Nếu có vấn đề, check:
1. Logs trong console
2. [P2P_INTEGRATION_GUIDE.md](P2P_INTEGRATION_GUIDE.md)
3. API response `/api/p2p/status`

Happy coding! 🚀
