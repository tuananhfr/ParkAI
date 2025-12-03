# PHASE 3 - SYNC ON RECONNECT

## Files Đã Tạo

1. `p2p/sync_manager.py` - Sync manager
2. Updated `p2p/manager.py` - Thêm sync callbacks
3. Updated `p2p/database_extensions.py` - Thêm get_sync_state()
4. `p2p_api_extensions.py` - API sync state

---

## Integration vào app.py

### Step 1: Import Sync Manager

Thêm vào imports:

```python
from p2p.sync_manager import P2PSyncManager
import p2p_api_extensions
```

### Step 2: Thêm global instance

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
p2p_sync_manager = None  # ← THÊM DÒNG NÀY
```

### Step 3: Sửa startup event

Thêm vào sau khi khởi tạo `p2p_broadcaster`:

```python
@app.on_event("startup")
async def startup():
    global database, parking_state, camera_registry
    global p2p_manager, p2p_event_handler, p2p_broadcaster, p2p_sync_manager

    try:
        # ... existing code ...

        # Initialize P2P Broadcaster
        p2p_broadcaster = P2PParkingBroadcaster(
            p2p_manager=p2p_manager,
            central_id=p2p_manager.config.get_this_central_id()
        )

        # ========== INITIALIZE SYNC MANAGER ==========
        # Initialize P2P Sync Manager
        p2p_sync_manager = P2PSyncManager(
            database=database,
            p2p_manager=p2p_manager,
            central_id=p2p_manager.config.get_this_central_id()
        )

        # Set sync callbacks
        p2p_manager.on_sync_request = p2p_sync_manager.handle_sync_request
        p2p_manager.on_sync_response = p2p_sync_manager.handle_sync_response

        # Set peer connection callbacks
        p2p_manager.on_peer_connected = p2p_sync_manager.on_peer_connected
        p2p_manager.on_peer_disconnected = p2p_sync_manager.on_peer_disconnected
        # =============================================

        # Set event callbacks (existing code)
        p2p_manager.on_vehicle_entry_pending = p2p_event_handler.handle_vehicle_entry_pending
        p2p_manager.on_vehicle_entry_confirmed = p2p_event_handler.handle_vehicle_entry_confirmed
        p2p_manager.on_vehicle_exit = p2p_event_handler.handle_vehicle_exit

        # Start P2P
        await p2p_manager.start()

        # Inject dependencies
        p2p_api.set_p2p_manager(p2p_manager)
        edge_api.set_dependencies(database, parking_state, p2p_broadcaster)
        p2p_api_extensions.set_database(database)  # ← THÊM DÒNG NÀY

    except Exception as e:
        import traceback
        traceback.print_exc()
```

### Step 4: Thêm API endpoint

Thêm route trong app.py:

```python
# ========== SYNC STATE API ==========
@app.get("/api/p2p/sync-state")
async def get_p2p_sync_state():
    """Get P2P sync state"""
    return p2p_api_extensions.get_sync_state_endpoint()
```

---

## How It Works

### Scenario: Central-2 Offline → Online Lại

```
T=0: Central-2 offline

T=1min: Xe vào ở Central-1
├─ Central-1: INSERT entry
├─ Broadcast P2P → Central-3,4,5...10 nhận được
└─ Central-2: OFFLINE, không nhận

T=2min: Xe ra ở Central-1
├─ Central-1: UPDATE exit, fee=25000
├─ Broadcast P2P → Central-3,4,5...10 update
└─ Central-2: vẫn OFFLINE

T=5min: Central-2 ONLINE lại

T=5min+1s:
├─ P2P Client (Central-1) → reconnect to Central-2
├─ P2P Client trigger: on_connected callback
└─ Sync Manager: request_sync_from_peer("central-2")

T=5min+2s:
├─ Central-1: Get last_sync_timestamp for Central-2 = T=0
├─ Central-1 gửi SYNC_REQUEST:
│  {
│    "type": "SYNC_REQUEST",
│    "source_central": "central-1",
│    "data": {
│      "since_timestamp": 0  // T=0
│    }
│  }
└─ Central-2 nhận SYNC_REQUEST

T=5min+3s:
├─ Central-2: Query events since T=0
├─ Central-2: get_events_since(0) → [entry event, exit event]
├─ Central-2 gửi SYNC_RESPONSE:
│  {
│    "type": "SYNC_RESPONSE",
│    "source_central": "central-2",
│    "data": {
│      "events": [
│        { event_id: "central-1_xxx", plate_id: "29A12345", ... },
│        { event_id: "central-1_xxx", exit_time: "...", fee: 25000, ... }
│      ]
│    }
│  }
└─ Central-1 nhận SYNC_RESPONSE

T=5min+4s:
├─ Central-1: Parse 2 events
├─ Central-1: Check event_id exists → KHÔNG (Central-2 missed)
├─ Central-1: INSERT entry event
├─ Central-1: UPDATE exit event
└─ Central-1: Update last_sync_timestamp = NOW

→ KẾT QUẢ: Central-2 đã sync 2 events bị miss
```

### Wait, Sai Flow! Sửa Lại:

**ĐÚNG FLOW:**

```
Central-2 online lại → Central-2 gửi SYNC_REQUEST đến tất cả peers

T=5min: Central-2 online
T=5min+1s:
├─ Central-2 connect đến Central-1
└─ on_connected("central-1") triggered

T=5min+2s:
├─ Central-2 Sync Manager: request_sync_from_peer("central-1")
├─ Central-2 get last_sync_timestamp("central-1") = T=0
├─ Central-2 gửi SYNC_REQUEST đến Central-1:
│  "Cho tôi events từ T=0 đến giờ"

T=5min+3s:
├─ Central-1 nhận SYNC_REQUEST từ Central-2
├─ Central-1: get_events_since(0) → [entry, exit]
├─ Central-1 gửi SYNC_RESPONSE về Central-2

T=5min+4s:
├─ Central-2 nhận SYNC_RESPONSE từ Central-1
├─ Central-2: Merge 2 events vào local DB
└─ Central-2: Update last_sync_timestamp("central-1") = NOW

→ Central-2 đã sync xong!
```

---

## Logs to Watch

**Central-2 online lại:**
```
✅ Connected to P2P peer central-1
🔗 Peer central-1 connected, requesting sync...
🔄 Requesting sync from central-1 (since 0)
✅ Sent SYNC_REQUEST to central-1
```

**Central-1 nhận SYNC_REQUEST:**
```
📥 Received SYNC_REQUEST from central-2 (since 0)
📤 Sending 2 events to central-2
✅ Sent SYNC_RESPONSE to central-2
```

**Central-2 nhận SYNC_RESPONSE:**
```
📥 Received SYNC_RESPONSE from central-1: 2 events
✅ Merged 2 events, skipped 0
✅ Updated last sync timestamp for central-1: 1733145600000
```

---

## Testing

### Test 1: Manual Offline/Online

Terminal 1 (Central-1):
```bash
python app.py
```

Terminal 2 (Central-2):
```bash
python app.py
# Sau 30s, Ctrl+C stop
```

Terminal 3 (Test):
```bash
# Entry ở Central-1 (while Central-2 offline)
curl -X POST http://192.168.1.101:8000/api/edge/barrier/open \
  -d '{"edge_id": "edge-1", "plate_id": "29A12345"}'

# Check Central-2 KHÔNG có data
curl http://192.168.1.102:8000/api/parking/history | grep 29A12345
# → Empty
```

Terminal 2 (Restart Central-2):
```bash
python app.py
# Wait 5 seconds for sync
```

Terminal 3 (Check sync):
```bash
# Check Central-2 ĐÃ CÓ data
curl http://192.168.1.102:8000/api/parking/history | grep 29A12345
# → Found!

# Check sync state
curl http://192.168.1.102:8000/api/p2p/sync-state
```

### Test 2: Network Partition

Simulate network partition:
```bash
# Block traffic từ Central-2 đến Central-1
# (Linux/Mac)
sudo iptables -A OUTPUT -d 192.168.1.101 -j DROP

# Wait 2 minutes

# Unblock
sudo iptables -D OUTPUT -d 192.168.1.101 -j DROP

# Check logs → auto sync
```

---

## API Endpoints Mới

### GET /api/p2p/sync-state

Get sync state với tất cả peers

**Response:**
```json
{
  "success": true,
  "sync_state": [
    {
      "peer_central_id": "central-2",
      "last_sync_timestamp": 1733145600000,
      "last_sync_time": "2025-12-02 11:00:00",
      "updated_at": "2025-12-02 11:00:05"
    },
    {
      "peer_central_id": "central-3",
      "last_sync_timestamp": 1733145500000,
      "last_sync_time": "2025-12-02 10:58:20",
      "updated_at": "2025-12-02 10:58:25"
    }
  ]
}
```

---

## Database Queries

```sql
-- Check sync state
SELECT * FROM p2p_sync_state;

-- Check missed events (events sau last_sync_timestamp)
SELECT h.*, s.last_sync_timestamp
FROM history h
JOIN p2p_sync_state s ON s.peer_central_id = 'central-2'
WHERE strftime('%s', h.created_at) * 1000 > s.last_sync_timestamp;

-- Update sync timestamp manually (if needed)
UPDATE p2p_sync_state
SET last_sync_timestamp = 1733145600000,
    last_sync_time = CURRENT_TIMESTAMP
WHERE peer_central_id = 'central-2';
```

---

## Configuration

### Sync Window

Default: Sync từ 7 ngày trước (lần đầu sync)

Để đổi, sửa trong `sync_manager.py`:

```python
def get_last_sync_timestamp(self, peer_id: str) -> int:
    # ...
    # Return timestamp 7 days ago (sync 7 ngày gần nhất)
    from datetime import timedelta
    week_ago = datetime.now() - timedelta(days=7)  # ← Đổi days=30 nếu muốn
    return int(week_ago.timestamp() * 1000)
```

### Sync Limit

Default: Sync tối đa 5000 events mỗi lần

Để đổi, sửa trong `sync_manager.py`:

```python
events = self.db.get_events_since(since_timestamp, limit=5000)  # ← Đổi limit
```

---

## Troubleshooting

### Sync không trigger
**Check:**
1. Peer có connect không: `/api/p2p/status`
2. Callbacks có được set không (xem logs khi startup)
3. on_connected có được gọi không

### Sync response nhưng không merge
**Check:**
1. Events có event_id không
2. Events đã tồn tại chưa (duplicate)
3. Xem logs: "Merged X events, skipped Y"

### Sync timestamp không update
**Check:**
1. Database có write permission không
2. p2p_sync_state table tồn tại không
3. Xem logs errors

---

## Next: Final Testing & Documentation

Phase 3 xong! Tiếp theo:

1. Full integration testing với 3-5 centrals
2. Performance testing
3. Edge case testing
4. Documentation finalization

---

## Summary

Phase 3 đã implement:
- ✅ Auto sync khi peer reconnect
- ✅ SYNC_REQUEST/RESPONSE protocol
- ✅ Track last_sync_timestamp per peer
- ✅ Merge missed events
- ✅ API endpoint để monitor sync state

**Total Phase 1+2+3:**
- ~2400 lines code
- 18 files
- Complete P2P system

🎉 **P2P SYSTEM COMPLETE!**
