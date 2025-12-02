# 🏗️ Kiến trúc Hệ thống 24/7 - Gợi ý & Checklist

## 📊 Đánh giá Kiến trúc Hiện tại

### ✅ Điểm Mạnh:

- ✅ **Offline Manager**: Edge có retry queue khi Central down
- ✅ **WebSocket Real-time**: Cập nhật real-time qua WebSocket
- ✅ **Heartbeat System**: Camera registry theo dõi status
- ✅ **Error Handling**: Có try/catch cơ bản

### ⚠️ Điểm Cần Cải thiện cho 24/7:

#### 1. **Database Layer** 🔴 CRITICAL

- **Vấn đề**: SQLite không tốt cho concurrent writes nhiều
- **Rủi ro**: Database lock, corruption khi nhiều cameras ghi đồng thời
- **Giải pháp**:
  - ✅ **Option 1 (Khuyến nghị)**: PostgreSQL/MySQL cho Central
  - ✅ **Option 2**: SQLite + WAL mode + connection pooling
  - ✅ **Option 3**: Giữ SQLite nhưng migrate sang PostgreSQL khi scale

#### 2. **Process Management** 🔴 CRITICAL

- **Vấn đề**: Chưa có auto-restart khi crash
- **Giải pháp**:
  - Systemd service (Linux)
  - PM2 (Node.js process manager - có thể dùng cho Python)
  - Docker + restart policies
  - Supervisor

#### 3. **Logging & Monitoring** 🟡 IMPORTANT

- **Vấn đề**: Chỉ dùng `print()` - khó debug
- **Giải pháp**:
  - Structured logging (Python `logging` module)
  - Log rotation
  - Centralized logging (ELK, Loki)
  - Health check endpoints
  - Metrics (Prometheus)

#### 4. **Resource Management** 🟡 IMPORTANT

- **Vấn đề**: Không có memory/resource limits
- **Giải pháp**:
  - Resource limits (systemd hoặc Docker)
  - Memory leak detection
  - Connection pooling

#### 5. **Backup & Recovery** 🟡 IMPORTANT

- **Vấn đề**: Không có backup strategy
- **Giải pháp**:
  - Automated database backups
  - Config backups
  - Disaster recovery plan

#### 6. **Network Resilience** 🟢 GOOD (có Offline Manager)

- **Đã có**: Retry queue, offline mode
- **Cần cải thiện**: Better timeout handling

---

## 🎯 Kiến trúc Đề xuất cho 24/7

### **Kiến trúc Hiện tại (Single Server):**

```
┌─────────────────┐
│  Edge Camera 1  │──┐
└─────────────────┘  │
┌─────────────────┐  │  ┌──────────────────┐
│  Edge Camera 2  │──┼──│  Central Server  │──┐
└─────────────────┘  │  │  (SQLite)        │  │
                     │  └──────────────────┘  │
┌─────────────────┐  │                        │
│  Edge Camera N  │──┘                        │
└─────────────────┘                          │
                                            │
                              ┌─────────────┘
                              │
                       ┌──────▼──────┐
                       │   Frontend  │
                       │   (React)   │
                       └─────────────┘
```

### **Kiến trúc Đề xuất (Production 24/7):**

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer / Reverse Proxy             │
│                      (Nginx / Traefik)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐
│  Central 1   │   │  Central 2   │   │  Central N   │
│ (Primary)    │   │ (Standby)    │   │ (Standby)    │
│              │   │              │   │              │
│ FastAPI      │   │ FastAPI      │   │ FastAPI      │
│ + Health     │   │ + Health     │   │ + Health     │
└───────┬──────┘   └───────┬──────┘   └───────┬──────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐
│ PostgreSQL   │   │ PostgreSQL   │   │ PostgreSQL   │
│ (Primary)    │◄──┤ (Replica)    │◄──┤ (Replica)    │
│              │   │              │   │              │
│ Streaming    │   │ Read-only    │   │ Read-only    │
│ Replication  │   │              │   │              │
└──────────────┘   └──────────────┘   └──────────────┘

Edge Cameras (Unchanged)
┌──────────────┐
│ Edge Camera 1│──┐
│ (Raspberry)  │  │
└──────────────┘  │
                  │  ┌──────────────────┐
┌──────────────┐  │  │  Monitoring      │
│ Edge Camera 2│──┼──│  (Prometheus +   │
│ (Raspberry)  │  │  │   Grafana)       │
└──────────────┘  │  └──────────────────┘
                  │
┌──────────────┐  │
│ Edge Camera N│──┘
│ (Raspberry)  │
└──────────────┘
```

---

## 📋 Checklist Triển khai 24/7

### 🔴 **CRITICAL - Phải làm ngay:**

#### 1. Process Management

- [ ] **Systemd Service** cho Central Server
- [ ] **Systemd Service** cho mỗi Edge Camera
- [ ] **Auto-restart** on failure
- [ ] **Restart limits** (tránh restart loop)

#### 2. Database Migration

- [ ] **PostgreSQL** setup cho Central
- [ ] **Migration script** từ SQLite → PostgreSQL
- [ ] **Connection pooling** (SQLAlchemy)
- [ ] **Database backups** (daily automated)

#### 3. Logging System

- [ ] **Python logging** thay thế `print()`
- [ ] **Log rotation** (RotatingFileHandler)
- [ ] **Log levels** (DEBUG, INFO, WARNING, ERROR)
- [ ] **Centralized logging** (tùy chọn)

#### 4. Health Checks

- [ ] **Health endpoint** `/api/health`
- [ ] **Liveness probe** (for monitoring)
- [ ] **Readiness probe** (for load balancer)

#### 5. Monitoring

- [ ] **System metrics** (CPU, Memory, Disk)
- [ ] **Application metrics** (requests, errors, latency)
- [ ] **Database metrics** (connections, queries)
- [ ] **Alerting** (email, Slack, Telegram)

---

### 🟡 **IMPORTANT - Nên làm sớm:**

#### 6. Error Handling & Recovery

- [ ] **Graceful shutdown** handling
- [ ] **Circuit breaker** cho external calls
- [ ] **Retry policies** với exponential backoff
- [ ] **Dead letter queue** cho failed events

#### 7. Security

- [ ] **HTTPS/SSL** certificates
- [ ] **API authentication** (JWT tokens)
- [ ] **Rate limiting**
- [ ] **Input validation** & sanitization
- [ ] **Firewall rules**

#### 8. Backup & Recovery

- [ ] **Database backups** (automated, daily)
- [ ] **Config backups**
- [ ] **Disaster recovery** plan
- [ ] **Backup restore** testing

#### 9. Performance Optimization

- [ ] **Database indexes** optimization
- [ ] **Connection pooling**
- [ ] **Caching** (Redis) cho frequent queries
- [ ] **Query optimization**

---

### 🟢 **NICE TO HAVE - Tối ưu:**

#### 10. High Availability (HA)

- [ ] **Load balancer** (Nginx, Traefik)
- [ ] **Multiple Central servers** (primary + standby)
- [ ] **Database replication** (PostgreSQL streaming)
- [ ] **Failover** mechanism

#### 11. Scaling

- [ ] **Horizontal scaling** capability
- [ ] **Container orchestration** (Docker Swarm, K8s)
- [ ] **Microservices** architecture (nếu cần)

#### 12. DevOps

- [ ] **CI/CD pipeline**
- [ ] **Infrastructure as Code** (Terraform, Ansible)
- [ ] **Automated testing**
- [ ] **Blue-Green deployment**

---

## 🛠️ Implementation Guide

### **1. Systemd Service cho Central Server**

```ini
# /etc/systemd/system/parking-central.service
[Unit]
Description=Parking Central Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=parking
WorkingDirectory=/opt/parking/backend-central
Environment="PATH=/opt/parking/backend-central/venv/bin"
ExecStart=/opt/parking/backend-central/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Resource limits
LimitNOFILE=65536
MemoryMax=2G

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable parking-central
sudo systemctl start parking-central
sudo systemctl status parking-central
```

### **2. Logging Setup**

```python
# backend-central/logging_config.py
import logging
import logging.handlers
import os

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler với rotation
    file_handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/central.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
```

### **3. Health Check Endpoint**

```python
# backend-central/app.py
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        database.check_connection()

        # Check camera registry
        if camera_registry:
            status = camera_registry.get_camera_status()

        return {
            "status": "healthy",
            "database": "ok",
            "camera_registry": "ok",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
```

### **4. Database Migration (SQLite → PostgreSQL)**

```python
# backend-central/database_migration.py
"""
Migration script từ SQLite sang PostgreSQL
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

def migrate_sqlite_to_postgres():
    # Connect to SQLite
    sqlite_conn = sqlite3.connect("data/central.db")
    sqlite_cursor = sqlite_conn.cursor()

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        host="localhost",
        database="parking",
        user="parking",
        password="..."
    )
    pg_cursor = pg_conn.cursor()

    # Migrate vehicles table
    sqlite_cursor.execute("SELECT * FROM vehicles")
    vehicles = sqlite_cursor.fetchall()

    if vehicles:
        execute_values(
            pg_cursor,
            "INSERT INTO vehicles (...) VALUES %s",
            vehicles
        )

    pg_conn.commit()
    print("✅ Migration completed!")
```

---

## 📊 Monitoring Setup

### **Prometheus Metrics**

```python
# backend-central/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
camera_online = Gauge('cameras_online', 'Number of online cameras')
database_connections = Gauge('database_connections_active', 'Active database connections')
```

### **Grafana Dashboard**

- System metrics (CPU, Memory, Disk)
- Application metrics (requests/sec, error rate)
- Database metrics (connections, query time)
- Camera status

---

## 🔒 Security Checklist

- [ ] **HTTPS**: SSL certificates (Let's Encrypt)
- [ ] **API Keys**: Authentication cho Edge cameras
- [ ] **Rate Limiting**: Ngăn DDoS
- [ ] **Input Validation**: Sanitize user input
- [ ] **SQL Injection**: Parameterized queries
- [ ] **XSS Protection**: Frontend sanitization
- [ ] **CORS**: Restrict origins
- [ ] **Firewall**: Chỉ mở ports cần thiết

---

## 📈 Scaling Strategy

### **Vertical Scaling (Tăng tài nguyên server):**

- CPU: 2 cores → 4 cores
- RAM: 4GB → 8GB
- Storage: SSD với tốc độ cao

### **Horizontal Scaling (Thêm servers):**

- Multiple Central servers với load balancer
- Database replication (read replicas)
- Edge cameras không cần scale (đã phân tán)

---

## 🚨 Alerting Rules

### **Critical Alerts:**

- Server down > 1 minute
- Database connection failed
- Disk space < 10%
- Memory usage > 90%
- Error rate > 5%

### **Warning Alerts:**

- Camera offline > 5 minutes
- Response time > 1 second
- Disk space < 20%
- Memory usage > 70%

---

## ✅ Testing Checklist

- [ ] **Load Testing**: Simulate nhiều cameras
- [ ] **Stress Testing**: Tối đa concurrent requests
- [ ] **Failover Testing**: Central server crash
- [ ] **Network Testing**: Edge camera disconnect
- [ ] **Database Testing**: Migration, backup, restore
- [ ] **Recovery Testing**: Restart sau crash

---

## 📝 Recommendations Summary

### **Ngắn hạn (1-2 tuần):**

1. ✅ Systemd services
2. ✅ Structured logging
3. ✅ Health check endpoints
4. ✅ Basic monitoring (Prometheus)
5. ✅ Automated backups

### **Trung hạn (1-2 tháng):**

1. ✅ PostgreSQL migration
2. ✅ Advanced monitoring (Grafana)
3. ✅ Security hardening
4. ✅ Performance optimization
5. ✅ High availability setup

### **Dài hạn (3-6 tháng):**

1. ✅ Microservices architecture (nếu cần)
2. ✅ Kubernetes deployment
3. ✅ Advanced analytics
4. ✅ Machine learning integration

---

## 💰 Cost Estimation

### **Minimum Setup (Small Scale):**

- 1x Central Server: $20-50/month (VPS)
- 1x PostgreSQL DB: $10-25/month (Managed)
- Monitoring: Free (Prometheus self-hosted)
- **Total: ~$30-75/month**

### **Production Setup (Medium Scale):**

- 2x Central Servers: $40-100/month
- 1x PostgreSQL Primary + 1 Replica: $50-100/month
- Load Balancer: $10-20/month
- Monitoring (Grafana Cloud): $10/month
- **Total: ~$110-230/month**

### **Enterprise Setup (Large Scale):**

- Multiple Central Servers: $200-500/month
- PostgreSQL Cluster: $200-500/month
- Kubernetes Cluster: $100-300/month
- Managed Monitoring: $50-100/month
- **Total: ~$550-1400/month**

---

## 🎯 Kết luận

**Kiến trúc hiện tại có thể chạy 24/7** nhưng cần cải thiện:

1. ✅ **Process Management** (Systemd) - CRITICAL
2. ✅ **Logging System** - CRITICAL
3. ✅ **Database** (SQLite → PostgreSQL) - IMPORTANT
4. ✅ **Monitoring & Alerting** - IMPORTANT
5. ✅ **Backup Strategy** - IMPORTANT

**Ưu tiên:**

- Bắt đầu với Systemd + Logging + Health checks (1-2 ngày)
- Sau đó PostgreSQL migration (1 tuần)
- Cuối cùng Monitoring & HA (2-4 tuần)

Với các cải thiện này, hệ thống sẽ **sẵn sàng cho production 24/7**! 🚀
