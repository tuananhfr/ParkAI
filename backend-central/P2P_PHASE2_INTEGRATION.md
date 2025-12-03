## PHASE 2 - EVENT BROADCASTING & HANDLING

## Files Đã Tạo

1. `p2p/event_handler.py` - Xử lý events từ peers
2. `p2p/database_extensions.py` - Extend database với P2P methods
3. `p2p/parking_integration.py` - Broadcast parking events
4. `edge_api.py` - API cho edge servers

---

## Integration vào app.py

### Step 1: Import modules mới

Thêm vào đầu file `app.py`:

```python
# P2P imports
from p2p import P2PManager
from p2p.database_migration import migrate_database_for_p2p
from p2p.database_extensions import patch_database_for_p2p
from p2p.event_handler import P2PEventHandler
from p2p.parking_integration import P2PParkingBroadcaster
import p2p_api
import edge_api
```

### Step 2: Thêm global instances

```python
# ==================== Global Instances ====================
database = None
parking_state = None
camera_registry = None
config_manager = ConfigManager()

# P2P instances
p2p_manager = None
p2p_event_handler = None
p2p_broadcaster = None
```

### Step 3: Sửa startup event

```python
@app.on_event("startup")
async def startup():
    global database, parking_state, camera_registry
    global p2p_manager, p2p_event_handler, p2p_broadcaster

    try:
        # Initialize database
        database = CentralDatabase(db_file=config.DB_FILE)

        # ========== MIGRATE & PATCH DATABASE FOR P2P ==========
        migrate_database_for_p2p(config.DB_FILE)
        patch_database_for_p2p(database)
        # =====================================================

        # Initialize parking state manager
        parking_state = ParkingStateManager(database)

        # Initialize camera registry
        camera_registry = CameraRegistry(
            database,
            heartbeat_timeout=config.CAMERA_HEARTBEAT_TIMEOUT
        )
        camera_registry.start()

        # ========== INITIALIZE P2P ==========
        # Initialize P2P Manager
        p2p_manager = P2PManager(config_file="config/p2p_config.json")

        # Initialize P2P Event Handler
        p2p_event_handler = P2PEventHandler(
            database=database,
            this_central_id=p2p_manager.config.get_this_central_id()
        )

        # Initialize P2P Broadcaster
        p2p_broadcaster = P2PParkingBroadcaster(
            p2p_manager=p2p_manager,
            central_id=p2p_manager.config.get_this_central_id()
        )

        # Set P2P callbacks
        p2p_manager.on_vehicle_entry_pending = p2p_event_handler.handle_vehicle_entry_pending
        p2p_manager.on_vehicle_entry_confirmed = p2p_event_handler.handle_vehicle_entry_confirmed
        p2p_manager.on_vehicle_exit = p2p_event_handler.handle_vehicle_exit

        # Start P2P
        await p2p_manager.start()

        # Inject dependencies vào API routers
        p2p_api.set_p2p_manager(p2p_manager)
        edge_api.set_dependencies(database, parking_state, p2p_broadcaster)
        # ====================================

    except Exception as e:
        import traceback
        traceback.print_exc()
```

### Step 4: Include Edge API router

Thêm sau các routes hiện tại:

```python
# ==================== Include Routers ====================
app.include_router(p2p_api.router)
app.include_router(edge_api.router)  # ← THÊM DÒNG NÀY
```

---

## Edge Server Integration

Edge servers cần gọi Central API thay vì gửi event trực tiếp.

### Edge Detection Flow (Cũ → Mới)

**CŨ (Phase 1):**
```python
# Edge gửi event lên central
POST /api/edge/event
{
  "type": "ENTRY",
  "camera_id": 1,
  "data": {"plate_text": "29A-12345"}
}
```

**MỚI (Phase 2):**
```python
# 1. Edge gửi detection lên central
POST /api/edge/detection
{
  "edge_id": "edge-1",
  "plate_id": "29A12345",
  "plate_view": "29A-123.45",
  "camera_type": "car",
  "direction": "ENTRY",
  "confidence": 0.95
}

# Response:
{
  "success": true,
  "vehicle_info": {
    "already_inside": false,
    "plate_id": "29A12345",
    "plate_view": "29A-123.45"
  }
}

# 2. Frontend hiển thị info
# 3. User click "Open Barrier"

# 4. Frontend gọi:
POST /api/edge/barrier/open
{
  "edge_id": "edge-1",
  "plate_id": "29A12345",
  "action": "open"
}

# Response:
{
  "success": true,
  "action": "ENTRY",
  "event_id": "central-1_1733140800000_29A12345"
}

# 5. Central tự động:
#    - INSERT vào DB
#    - Broadcast P2P đến peers
#    - Return success

# 6. Edge mở barrier (GPIO)

# 7. User đóng barrier

# 8. Frontend gọi:
POST /api/edge/barrier/close
{
  "edge_id": "edge-1",
  "plate_id": "29A12345",
  "action": "close"
}
```

---

## Testing

### Test 1: Standalone Mode (1 central)

```bash
# Start central
cd backend-central
python app.py

# Test detection
curl -X POST http://localhost:8000/api/edge/detection \
  -H "Content-Type: application/json" \
  -d '{
    "edge_id": "edge-1",
    "plate_id": "29A12345",
    "plate_view": "29A-123.45",
    "camera_type": "car",
    "direction": "ENTRY",
    "confidence": 0.95
  }'

# Test open barrier
curl -X POST http://localhost:8000/api/edge/barrier/open \
  -H "Content-Type: application/json" \
  -d '{
    "edge_id": "edge-1",
    "plate_id": "29A12345",
    "action": "open"
  }'

# Check history
curl http://localhost:8000/api/parking/history
```

### Test 2: Multi-Central Mode (2 centrals)

Terminal 1 (Central-1):
```bash
cd backend-central-1
python app.py
```

Terminal 2 (Central-2):
```bash
cd backend-central-2
python app.py
```

Terminal 3 (Test):
```bash
# Entry ở Central-1
curl -X POST http://192.168.1.101:8000/api/edge/barrier/open \
  -H "Content-Type: application/json" \
  -d '{
    "edge_id": "edge-1",
    "plate_id": "29A12345",
    "action": "open"
  }'

# Check Central-2 có sync không
curl http://192.168.1.102:8000/api/parking/history | grep 29A12345

# Exit ở Central-2
curl -X POST http://192.168.1.102:8000/api/edge/barrier/open \
  -H "Content-Type: application/json" \
  -d '{
    "edge_id": "edge-8",
    "plate_id": "29A12345",
    "action": "open"
  }'

# Check fee calculation
curl http://192.168.1.101:8000/api/parking/history | grep 29A12345
```

---

## Logs to Watch

Khi chạy, bạn sẽ thấy logs như:

```
✅ P2P Server started on ws://127.0.0.1:9000
✅ Connected to P2P peer central-2
📡 Broadcasted ENTRY_PENDING: 29A-123.45 (central-1_1733140800000_29A12345)
✅ Synced ENTRY from central-1: 29A-123.45 (central-1_1733140800000_29A12345)
📡 Broadcasted EXIT: central-1_1733140800000_29A12345, fee 25000
✅ Synced EXIT from central-2: event central-1_1733140800000_29A12345, fee 25000
```

---

## Troubleshooting

### Event không broadcast
**Check:**
1. P2P manager đã start chưa: `curl /api/p2p/status`
2. Peers có connected không: `connected_peers > 0`
3. Xem logs console

### Event broadcast nhưng peer không nhận
**Check:**
1. Peer có online không
2. WebSocket connection OK không
3. Firewall có block port 9000 không

### Duplicate entries
**Check:**
1. Conflict resolution có chạy không (xem logs)
2. event_id có unique không
3. Database có index cho event_id không

---

## Next: Phase 3 - Sync on Reconnect

Phase 2 đã xong broadcast & handling. Phase 3 sẽ implement:

- Sync missed events khi peer reconnect
- SYNC_REQUEST/RESPONSE protocol
- Track last_sync_time per peer

---

## Database Queries Hữu Ích

```sql
-- Check events từ P2P
SELECT * FROM history WHERE sync_status = 'SYNCED';

-- Check events local
SELECT * FROM history WHERE sync_status = 'LOCAL';

-- Check duplicate event_id
SELECT event_id, COUNT(*)
FROM history
GROUP BY event_id
HAVING COUNT(*) > 1;

-- Check sync state
SELECT * FROM p2p_sync_state;
```
