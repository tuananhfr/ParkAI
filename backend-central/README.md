# 🏢 Backend Central - Parking Management Server

Central server tổng hợp dữ liệu từ tất cả Edge cameras.

---

## QUICK START

```bash
# Chạy ngay (tự động setup nếu chưa có)
make

# Hoặc từng bước:
make setup    # Cài đặt dependencies
make run      # Chạy server
```

---

## 📋 YÊU CẦU

- **Python 3.8+**
- **SQLite** (có sẵn)

---

## 🔧 CẤU HÌNH

Sửa file `config.py`:

```python
# Server
HOST = "0.0.0.0"
PORT = 8000

# Database
DB_FILE = "data/central.db"
```

---

## 🚀 DEPLOYMENT

### 1. **Development:**
```bash
make
```

### 2. **Production:**
```bash
# Sử dụng systemd service
sudo nano /etc/systemd/system/parking-central.service
```

```ini
[Unit]
Description=Parking Central Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/backend-central
ExecStart=/path/to/backend-central/venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable parking-central
sudo systemctl start parking-central
sudo systemctl status parking-central
```

---

## API ENDPOINTS

### **Camera Management**
- `GET /api/cameras` - Danh sách cameras
- `POST /api/edge/heartbeat` - Edge heartbeat
- `POST /api/edge/event` - Edge events (ENTRY/EXIT)

### **Parking Data**
- `GET /api/parking/state` - Xe đang trong bãi
- `GET /api/parking/history` - Lịch sử ra/vào
- `GET /api/vehicle/{plate_id}` - Thông tin xe

### **Stats**
- `GET /api/stats` - Thống kê tổng quan

---

## 🗂STRUCTURE

```
backend-central/
├── app.py                  # Main FastAPI app
├── config.py              # Configuration
├── database.py            # SQLite database
├── parking_state.py       # Parking logic
├── camera_registry.py     # Camera management
├── requirements.txt       # Python dependencies
├── Makefile              # Build & run commands
├── README.md             # This file
└── data/
    └── central.db        # SQLite database (auto-created)
```

---

## 🧹 MAINTENANCE

```bash
# Clean cache
make clean

# Reset database (CẨN THẬN!)
rm -rf data/central.db

# View logs
tail -f logs/*.log  # Nếu có logging
```

---

## TROUBLESHOOTING

### **Port đã được sử dụng:**
```bash
# Check port 8000
sudo lsof -i :8000

# Đổi port trong config.py
PORT = 8001
```

### **Database locked:**
```bash
# Restart server
sudo systemctl restart parking-central
```

### **Không kết nối được:**
```bash
# Check firewall
sudo ufw allow 8000/tcp
```

---

## 📊 MONITORING

```bash
# Check server health
curl http://localhost:8000/api/cameras

# Check database size
du -h data/central.db

# Monitor connections
watch -n 1 'curl -s http://localhost:8000/api/cameras | jq .cameras.online'
```

---

## CHECKLIST

- [ ] Python 3.8+ installed
- [ ] `make setup` hoàn tất
- [ ] Port 8000 available
- [ ] Config đã điều chỉnh (nếu cần)
- [ ] `make` chạy thành công
- [ ] Test API: `curl http://localhost:8000/api/cameras`

---

**� DONE! Server đang chạy tại http://localhost:8000**
