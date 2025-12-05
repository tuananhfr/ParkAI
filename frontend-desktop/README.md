# 🖥ParkAI Desktop Application

Desktop application cho hệ thống quản lý bãi đỗ xe, xây dựng với PyQt6.

## 🚀 Quick Start

### Trên Raspberry Pi:

```bash
cd frontend-desktop
make setup  # Lần đầu tiên
make run    # Chạy app
```

Hoặc ngắn gọn:
```bash
make  # Setup (nếu cần) và chạy
```

### Trên Windows/Mac/Linux:

```bash
cd frontend-desktop
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 📋 Requirements

- **Python**: 3.9+
- **OS**:
  - Raspberry Pi OS (recommended)
  - Windows 10/11
  - macOS 10.15+
  - Ubuntu 20.04+
- **RAM**: Tối thiểu 2GB

## 📚 Documentation

- **[RASPBERRY_PI_SETUP.md](../RASPBERRY_PI_SETUP.md)** - Hướng dẫn cài đặt trên Raspberry Pi
- **[PYQT6_TUTORIAL_ROADMAP.md](../PYQT6_TUTORIAL_ROADMAP.md)** - Roadmap học PyQt6 từ đầu
- **[PHASE_1_SETUP_MAIN_WINDOW.md](../PHASE_1_SETUP_MAIN_WINDOW.md)** - Phase 1: Setup & Main Window
- **[PHASE_2_API_CONNECTION.md](../PHASE_2_API_CONNECTION.md)** - Phase 2: API Client
- **[PHASE_3_DASHBOARD_STATS.md](../PHASE_3_DASHBOARD_STATS.md)** - Phase 3: Dashboard
- **[PHASE_4_CAMERA_VIEWS.md](../PHASE_4_CAMERA_VIEWS.md)** - Phase 4: Camera Views
- **[PHASE_5_HISTORY_SETTINGS.md](../PHASE_5_HISTORY_SETTINGS.md)** - Phase 5: History & Settings

## 🎯 Features

- ✅ **Real-time Dashboard** - Hiển thị stats (entries, exits, revenue) real-time
- ✅ **Camera Monitoring** - Grid hiển thị multiple cameras với controls
- ✅ **History Management** - Table hiển thị entry/exit records với filter
- ✅ **Settings** - Configuration cho backend connection, P2P, staff
- ✅ **WebSocket Updates** - Live updates không cần polling
- ✅ **Touchscreen Support** - Hoạt động tốt trên Pi touchscreen

## 🏗Project Structure

```
frontend-desktop/
├── main.py                    # Entry point
├── config.py                  # Configuration
├── requirements.txt           # Python dependencies
├── Makefile                   # Build & run automation
│
├── core/                      # Business logic
│   ├── api_client.py         # REST API client
│   ├── websocket_manager.py  # WebSocket manager
│   └── models.py             # Data models
│
├── ui/                        # UI components
│   ├── main_window.py        # Main window
│   ├── dashboard/            # Dashboard widgets
│   ├── cameras/              # Camera monitoring
│   ├── history/              # History table
│   └── settings/             # Settings dialog
│
└── utils/                     # Utilities
    ├── logger.py             # Logging
    └── helpers.py            # Helper functions
```

## ⚙Configuration

### Backend URL

**Option 1**: Environment variable

```bash
export CENTRAL_URL=http://192.168.0.144:8000
```

**Option 2**: `.env` file

```bash
echo "CENTRAL_URL=http://192.168.0.144:8000" > .env
```

**Option 3**: Settings trong app (Settings tab)

## 🧪 Testing

```bash
# Test PyQt6 installation
make test

# Test manual
source venv/bin/activate
python -c "from PyQt6.QtWidgets import QApplication; print('OK')"
```

## 🐛 Troubleshooting

Xem [RASPBERRY_PI_SETUP.md](../RASPBERRY_PI_SETUP.md#-troubleshooting) cho common errors và solutions.

## 📝 Development

### Makefile Commands

```bash
make           # Setup (if needed) và chạy app
make setup     # Install dependencies
make run       # Chạy app
make test      # Test dependencies
make clean     # Xóa cache
make help      # Hiển thị help
```

### Running in development mode

```bash
source venv/bin/activate
python main.py
```

### Code style

- Follow PEP 8
- Use type hints
- Add docstrings cho classes và functions
- Comments giải thích logic phức tạp

## 🎨 Screenshots

TODO: Thêm screenshots khi app hoàn thành

## 📄 License

Copyright © 2024 ParkAI

## 🤝 Contributing

TODO: Add contributing guidelines

## 📧 Contact

TODO: Add contact info
