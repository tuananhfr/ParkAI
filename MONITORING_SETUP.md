# 📊 Monitoring Setup Guide

## 🎯 Overview

Hướng dẫn setup monitoring cho hệ thống Parking 24/7.

## 📋 Components

1. **Prometheus** - Metrics collection
2. **Grafana** - Visualization dashboard
3. **Alertmanager** - Alerting (optional)

---

## 1️⃣ Prometheus Setup

### Installation:

```bash
# Download
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
sudo mv prometheus-2.45.0.linux-amd64 /opt/prometheus

# Create user
sudo useradd --no-create-home --shell /bin/false prometheus
sudo chown -R prometheus:prometheus /opt/prometheus
```

### Config File:

```yaml
# /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'parking-central'
    static_configs:
      - targets: ['localhost:8000']
        labels:
          instance: 'central-server'
          service: 'parking-central'

  - job_name: 'system'
    static_configs:
      - targets: ['localhost:9100']  # Node Exporter

  - job_name: 'postgresql'
    static_configs:
      - targets: ['localhost:9187']  # PostgreSQL Exporter
```

### Systemd Service:

```ini
# /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
User=prometheus
ExecStart=/opt/prometheus/prometheus \
    --config.file=/etc/prometheus/prometheus.yml \
    --storage.tsdb.path=/var/lib/prometheus \
    --web.console.templates=/opt/prometheus/consoles \
    --web.console.libraries=/opt/prometheus/console_libraries
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable prometheus
sudo systemctl start prometheus
```

---

## 2️⃣ Metrics Export trong App

### Install Prometheus Client:

```bash
cd backend-central
pip install prometheus-client
```

### Add Metrics:

```python
# backend-central/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# HTTP Metrics
http_requests = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

# Application Metrics
cameras_online = Gauge('cameras_online', 'Number of online cameras')
cameras_offline = Gauge('cameras_offline', 'Number of offline cameras')
vehicles_in_parking = Gauge('vehicles_in_parking', 'Number of vehicles in parking')
events_processed = Counter('events_processed_total', 'Total events processed', ['type'])

# Database Metrics
database_queries = Counter('database_queries_total', 'Total database queries')
database_query_duration = Histogram('database_query_duration_seconds', 'Database query duration')

def start_metrics_server(port=9090):
    """Start Prometheus metrics server"""
    start_http_server(port)
```

### Integrate vào app.py:

```python
# backend-central/app.py
from metrics import (
    http_requests, http_request_duration,
    cameras_online, cameras_offline,
    vehicles_in_parking, start_metrics_server
)
import time

# Start metrics server
start_metrics_server(9090)

# Middleware để track requests
@app.middleware("http")
async def track_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    duration = time.time() - start_time
    http_request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    http_requests.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    return response

# Update metrics trong endpoints
@app.post("/api/edge/heartbeat")
async def receive_heartbeat(request: Request):
    # ... existing code ...
    
    # Update camera metrics
    status = camera_registry.get_camera_status()
    cameras_online.set(status.get("online", 0))
    cameras_offline.set(status.get("offline", 0))
    
    return JSONResponse({"success": True})
```

### Metrics Endpoint:

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@app.get("/api/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## 3️⃣ Grafana Setup

### Installation:

```bash
# Add repository
sudo apt-get install -y apt-transport-https software-properties-common wget
sudo wget -q -O /usr/share/keyrings/grafana.key https://apt.grafana.com/gpg.key
echo "deb [signed-by=/usr/share/keyrings/grafana.key] https://apt.grafana.com stable main" | sudo tee -a /etc/apt/sources.list.d/grafana.list

# Install
sudo apt-get update
sudo apt-get install grafana

# Start
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### Add Prometheus Data Source:

1. Login: http://localhost:3000 (admin/admin)
2. Configuration → Data Sources → Add data source
3. Select Prometheus
4. URL: http://localhost:9090
5. Save & Test

### Import Dashboard:

```json
// dashboard.json - Basic dashboard
{
  "dashboard": {
    "title": "Parking System Monitoring",
    "panels": [
      {
        "title": "HTTP Requests/sec",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Online Cameras",
        "targets": [
          {
            "expr": "cameras_online"
          }
        ]
      },
      {
        "title": "Vehicles in Parking",
        "targets": [
          {
            "expr": "vehicles_in_parking"
          }
        ]
      }
    ]
  }
}
```

---

## 4️⃣ Alerting Rules

### Prometheus Alert Rules:

```yaml
# /etc/prometheus/alerts.yml
groups:
  - name: parking_alerts
    rules:
      - alert: CentralServerDown
        expr: up{job="parking-central"} == 0
        for: 1m
        annotations:
          summary: "Central server is down"
          
      - alert: CameraOffline
        expr: cameras_offline > 0
        for: 5m
        annotations:
          summary: "Camera is offline for 5 minutes"
          
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          
      - alert: DatabaseConnectionFailed
        expr: database_queries_total == 0
        for: 2m
        annotations:
          summary: "Database connection failed"
```

### Update prometheus.yml:

```yaml
# /etc/prometheus/prometheus.yml
rule_files:
  - "/etc/prometheus/alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - localhost:9093
```

---

## 5️⃣ Key Metrics to Monitor

### System Metrics:
- CPU usage
- Memory usage
- Disk usage
- Network I/O

### Application Metrics:
- HTTP requests/sec
- Error rate
- Response time (p50, p95, p99)
- Active WebSocket connections

### Business Metrics:
- Cameras online/offline
- Vehicles in parking
- Events processed/sec
- Entry/Exit events

### Database Metrics:
- Query duration
- Connection pool usage
- Database size

---

## 📊 Sample Dashboard Queries

```promql
# HTTP Requests per second
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Average response time
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Camera uptime percentage
avg_over_time((cameras_online / (cameras_online + cameras_offline))[1h])

# Events processed per minute
rate(events_processed_total[1m])
```

---

## ✅ Testing

```bash
# Test Prometheus
curl http://localhost:9090/api/v1/targets

# Test Metrics endpoint
curl http://localhost:8000/api/metrics

# Test Grafana
curl http://localhost:3000/api/health
```

---

## 🎯 Next Steps

1. Setup Alertmanager for notifications
2. Configure email/Slack alerts
3. Create custom dashboards
4. Setup log aggregation (ELK, Loki)
5. Performance testing with metrics

Xem thêm: `ARCHITECTURE_24x7.md`

