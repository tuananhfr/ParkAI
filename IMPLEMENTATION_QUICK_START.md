# 🚀 Quick Start Guide - Setup 24/7 Infrastructure

## 📋 Bước 1: Systemd Services (30 phút)

### **Central Server:**

```bash
# Tạo systemd service file
sudo nano /etc/systemd/system/parking-central.service
```

```ini
[Unit]
Description=Parking Central Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/parkAI/backend-central
Environment="PATH=/path/to/parkAI/backend-central/venv/bin"
ExecStart=/path/to/parkAI/backend-central/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

```bash
# Reload và enable
sudo systemctl daemon-reload
sudo systemctl enable parking-central
sudo systemctl start parking-central

# Check status
sudo systemctl status parking-central
journalctl -u parking-central -f  # Xem logs
```

### **Edge Camera (mỗi camera):**

```bash
sudo nano /etc/systemd/system/parking-edge1.service
```

```ini
[Unit]
Description=Parking Edge Camera 1
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/parkAI/backend-edge1
Environment="PATH=/path/to/parkAI/backend-edge1/venv/bin"
ExecStart=/path/to/parkAI/backend-edge1/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

---

## 📋 Bước 2: Structured Logging (1 giờ)

### **Thêm logging config:**

```bash
# Tạo file logging config
touch backend-central/logging_config.py
touch backend-edge1/logging_config.py
```

### **Backend Central:**

```python
# backend-central/logging_config.py
import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging(log_name="central"):
    """Setup structured logging"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler với rotation (10MB, giữ 5 files)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f"{log_name}.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### **Cập nhật app.py:**

```python
# backend-central/app.py
import logging
from logging_config import setup_logging

# Setup logging ở đầu file
logger = setup_logging("central")

# Thay thế tất cả print() bằng logger
logger.info("Server starting...")
logger.error(f"Error: {e}")
logger.warning("Warning message")
```

---

## 📋 Bước 3: Health Check Endpoint (30 phút)

### **Thêm vào backend-central/app.py:**

```python
@app.get("/api/health")
async def health_check():
    """Health check endpoint cho monitoring"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {}
        }
        
        # Check database
        try:
            database.check_connection()  # Thêm method này vào Database class
            health_status["services"]["database"] = "ok"
        except Exception as e:
            health_status["services"]["database"] = f"error: {str(e)}"
            health_status["status"] = "unhealthy"
        
        # Check camera registry
        try:
            if camera_registry:
                status = camera_registry.get_camera_status()
                health_status["services"]["camera_registry"] = "ok"
                health_status["cameras"] = {
                    "total": status.get("total", 0),
                    "online": status.get("online", 0),
                    "offline": status.get("offline", 0)
                }
            else:
                health_status["services"]["camera_registry"] = "not_initialized"
        except Exception as e:
            health_status["services"]["camera_registry"] = f"error: {str(e)}"
        
        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(content=health_status, status_code=status_code)
        
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "error": str(e)},
            status_code=503
        )
```

### **Thêm check_connection vào Database class:**

```python
# backend-central/database.py
def check_connection(self):
    """Check database connection"""
    try:
        with self.lock:
            conn = sqlite3.connect(self.db_file, timeout=5.0)
            conn.execute("SELECT 1")
            conn.close()
            return True
    except Exception as e:
        raise Exception(f"Database connection failed: {e}")
```

---

## 📋 Bước 4: Automated Backups (1 giờ)

### **Tạo backup script:**

```bash
# Tạo backup script
mkdir -p scripts
touch scripts/backup_central.sh
```

```bash
#!/bin/bash
# scripts/backup_central.sh

BACKUP_DIR="/backup/parking"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="/path/to/parkAI/backend-central/data/central.db"
CONFIG_FILE="/path/to/parkAI/backend-central/config.py"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
sqlite3 $DB_FILE ".backup $BACKUP_DIR/central_${DATE}.db"

# Backup config
cp $CONFIG_FILE $BACKUP_DIR/config_${DATE}.py

# Compress backups older than 7 days
find $BACKUP_DIR -name "*.db" -mtime +7 -exec gzip {} \;

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.db.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.py" -mtime +30 -delete

echo "✅ Backup completed: central_${DATE}.db"
```

```bash
# Make executable
chmod +x scripts/backup_central.sh

# Add to crontab (chạy mỗi ngày lúc 2AM)
crontab -e

# Thêm dòng này:
0 2 * * * /path/to/parkAI/scripts/backup_central.sh >> /var/log/parking_backup.log 2>&1
```

---

## 📋 Bước 5: Basic Monitoring với Prometheus (2 giờ)

### **Cài đặt Prometheus:**

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Tạo config
sudo mkdir -p /etc/prometheus
sudo cp prometheus.yml /etc/prometheus/
```

### **Prometheus config:**

```yaml
# /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'parking-central'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/metrics'
```

### **Thêm metrics endpoint vào app:**

```python
# backend-central/app.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Metrics
http_requests = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
http_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
cameras_online = Gauge('cameras_online', 'Number of online cameras')

@app.get("/api/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")
```

### **Systemd service cho Prometheus:**

```ini
# /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/usr/local/bin/prometheus --config.file=/etc/prometheus/prometheus.yml
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📋 Bước 6: PostgreSQL Migration (Tùy chọn - 4 giờ)

### **Cài đặt PostgreSQL:**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### **Tạo database:**

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE parking;
CREATE USER parking_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE parking TO parking_user;
\q
```

### **Migration script:**

```python
# backend-central/migrate_to_postgres.py
import sqlite3
import psycopg2
from datetime import datetime

def migrate():
    # Connect
    sqlite_conn = sqlite3.connect("data/central.db")
    pg_conn = psycopg2.connect(
        host="localhost",
        database="parking",
        user="parking_user",
        password="your_password"
    )
    
    sqlite_cursor = sqlite_conn.cursor()
    pg_cursor = pg_conn.cursor()
    
    # Migrate vehicles
    sqlite_cursor.execute("SELECT * FROM vehicles")
    vehicles = sqlite_cursor.fetchall()
    
    for vehicle in vehicles:
        pg_cursor.execute("""
            INSERT INTO vehicles (
                plate_id, plate_view, entry_time, 
                entry_camera_id, entry_camera_name,
                entry_confidence, entry_source,
                exit_time, exit_camera_id, exit_camera_name,
                exit_confidence, exit_source,
                duration, fee, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, vehicle)
    
    pg_conn.commit()
    print("✅ Migration completed!")
    
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    migrate()
```

---

## ✅ Testing Checklist

Sau khi setup xong, test các scenarios:

```bash
# 1. Test service restart
sudo systemctl restart parking-central
sudo systemctl status parking-central

# 2. Test health check
curl http://localhost:8000/api/health

# 3. Test logging
sudo journalctl -u parking-central -f

# 4. Test backup
./scripts/backup_central.sh
ls -lh /backup/parking/

# 5. Test crash recovery
sudo pkill -9 -f "python app.py"  # Kill process
# Systemd sẽ auto-restart
sudo systemctl status parking-central
```

---

## 🎯 Next Steps

Sau khi hoàn thành các bước trên:

1. ✅ **Monitoring Dashboard**: Setup Grafana
2. ✅ **Alerting**: Configure alerts (email, Slack)
3. ✅ **Load Testing**: Test với nhiều cameras
4. ✅ **Security**: Setup HTTPS, firewall
5. ✅ **High Availability**: Multiple servers (nếu cần)

Xem thêm chi tiết trong `ARCHITECTURE_24x7.md`!

