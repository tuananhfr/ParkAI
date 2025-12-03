# P2P Integration Guide

## Phase 1 Completed ✅

Đã hoàn thành P2P core infrastructure:

### Files Created:
1. `p2p/__init__.py` - P2P module entry point
2. `p2p/protocol.py` - Message types và protocol
3. `p2p/config_loader.py` - Load P2P config từ JSON
4. `p2p/server.py` - WebSocket server nhận connections từ peers
5. `p2p/client.py` - WebSocket clients kết nối đến peers
6. `p2p/manager.py` - Orchestrator chính
7. `p2p/database_migration.py` - Migration script cho DB
8. `p2p_api.py` - API endpoints cho frontend
9. `config/p2p_config.json` - Default config file

---

## Cách Integrate vào app.py

### Step 1: Import P2P Manager

Thêm vào đầu file `app.py`:

```python
from p2p import P2PManager
from p2p.database_migration import migrate_database_for_p2p
import p2p_api
```

### Step 2: Khởi tạo P2P Manager

Thêm vào phần global instances (sau `config_manager`):

```python
# ==================== Global Instances ====================
database = None
parking_state = None
camera_registry = None
config_manager = ConfigManager()

# P2P Manager
p2p_manager = None  # ← THÊM DÒNG NÀY
```

### Step 3: Start P2P trong startup event

Sửa hàm `startup()`:

```python
@app.on_event("startup")
async def startup():
    global database, parking_state, camera_registry, p2p_manager

    try:
        # Initialize database
        database = CentralDatabase(db_file=config.DB_FILE)

        # Migrate database for P2P (chạy 1 lần)
        migrate_database_for_p2p(config.DB_FILE)

        # Initialize parking state manager
        parking_state = ParkingStateManager(database)

        # Initialize camera registry
        camera_registry = CameraRegistry(
            database,
            heartbeat_timeout=config.CAMERA_HEARTBEAT_TIMEOUT
        )
        camera_registry.start()

        # ========== THÊM P2P MANAGER ==========
        # Initialize P2P Manager
        p2p_manager = P2PManager(config_file="config/p2p_config.json")

        # Set callbacks (implement later in Phase 2)
        # p2p_manager.on_vehicle_entry_pending = handle_p2p_entry_pending
        # p2p_manager.on_vehicle_entry_confirmed = handle_p2p_entry_confirmed
        # p2p_manager.on_vehicle_exit = handle_p2p_exit

        # Start P2P
        await p2p_manager.start()

        # Inject P2P manager vào API router
        p2p_api.set_p2p_manager(p2p_manager)
        # ======================================

    except Exception as e:
        import traceback
        traceback.print_exc()
```

### Step 4: Stop P2P trong shutdown event

Sửa hàm `shutdown()`:

```python
@app.on_event("shutdown")
async def shutdown():
    global camera_registry, p2p_manager

    if camera_registry:
        camera_registry.stop()

    # ========== THÊM P2P SHUTDOWN ==========
    if p2p_manager:
        await p2p_manager.stop()
    # =======================================
```

### Step 5: Include P2P API Router

Thêm sau các routes hiện tại (trước `if __name__ == '__main__'`):

```python
# ==================== Include P2P Router ====================
app.include_router(p2p_api.router)
```

---

## Testing P2P

### 1. Standalone Mode (1 central)

Config mặc định (`config/p2p_config.json`):
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

Chạy server:
```bash
cd backend-central
python app.py
```

Kiểm tra P2P status:
```bash
curl http://localhost:8000/api/p2p/status
```

Expected response:
```json
{
  "success": true,
  "this_central": "central-1",
  "running": true,
  "standalone_mode": true,
  "total_peers": 0,
  "connected_peers": 0,
  "messages_sent": 0,
  "messages_received": 0,
  "peers": []
}
```

### 2. Multi-Central Mode (2+ centrals)

#### Central-1 Config:
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
    }
  ]
}
```

#### Central-2 Config:
```json
{
  "this_central": {
    "id": "central-2",
    "ip": "192.168.1.102",
    "p2p_port": 9000,
    "api_port": 8000
  },
  "peer_centrals": [
    {
      "id": "central-1",
      "ip": "192.168.1.101",
      "p2p_port": 9000
    }
  ]
}
```

Chạy cả 2 servers:

Terminal 1:
```bash
cd backend-central-1
python app.py
```

Terminal 2:
```bash
cd backend-central-2
python app.py
```

Kiểm tra connection:
```bash
# Từ central-1
curl http://192.168.1.101:8000/api/p2p/status

# Từ central-2
curl http://192.168.1.102:8000/api/p2p/status
```

Expected response:
```json
{
  "success": true,
  "this_central": "central-1",
  "running": true,
  "standalone_mode": false,
  "total_peers": 1,
  "connected_peers": 1,
  "messages_sent": 5,
  "messages_received": 5,
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

## Frontend Integration

### Get P2P Config:
```javascript
fetch('http://localhost:8000/api/p2p/config')
  .then(res => res.json())
  .then(data => console.log(data.config))
```

### Update P2P Config:
```javascript
const newConfig = {
  this_central: {
    id: "central-1",
    ip: "192.168.1.101",
    p2p_port: 9000,
    api_port: 8000
  },
  peer_centrals: [
    {
      id: "central-2",
      ip: "192.168.1.102",
      p2p_port: 9000
    },
    {
      id: "central-3",
      ip: "192.168.1.103",
      p2p_port: 9000
    }
  ]
}

fetch('http://localhost:8000/api/p2p/config', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(newConfig)
})
  .then(res => res.json())
  .then(data => console.log(data))
```

### Get P2P Status:
```javascript
fetch('http://localhost:8000/api/p2p/status')
  .then(res => res.json())
  .then(data => {
    console.log('Connected peers:', data.connected_peers)
    console.log('Peers:', data.peers)
  })
```

---

## Next Steps - Phase 2

Phase 1 đã xong P2P infrastructure. Phase 2 sẽ implement:

1. **Event Broadcasting**: Khi có ENTRY/EXIT → broadcast đến peers
2. **Event Handling**: Nhận event từ peer → lưu vào DB
3. **Conflict Resolution**: Xử lý race condition
4. **Sync on Reconnect**: Sync missed events khi peer reconnect

Tất cả logic hiện tại (entry/exit, fee calculation) giữ nguyên. P2P chỉ là layer sync data giữa các centrals.

---

## Troubleshooting

### P2P Server không start:
- Kiểm tra port 9000 đã được sử dụng chưa: `netstat -ano | findstr 9000`
- Thử đổi port trong config

### Peer không connect:
- Kiểm tra firewall
- Ping peer IP: `ping 192.168.1.102`
- Kiểm tra peer server có đang chạy không

### Config không load:
- Kiểm tra file `config/p2p_config.json` có tồn tại không
- Kiểm tra JSON syntax có đúng không
- Xem logs trong console

---

## Database Schema Changes

Migration tự động thêm columns:
- `event_id` TEXT - Unique event ID (central-1_timestamp_plate_id)
- `source_central` TEXT - Central nào tạo event
- `edge_id` TEXT - Edge camera nào detect
- `sync_status` TEXT - LOCAL hoặc SYNCED

Table mới:
- `p2p_sync_state` - Track last sync time với mỗi peer
