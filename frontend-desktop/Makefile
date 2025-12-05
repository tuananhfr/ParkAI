.PHONY: all setup run clean test help

# Default: chỉ cần gõ "make"
all: check-and-run

# Help - Hiển thị các commands
help:
	@echo "📚 ParkAI Desktop - Available Commands:"
	@echo ""
	@echo "  make          - Setup (nếu cần) và chạy app"
	@echo "  make setup    - Cài đặt dependencies và tạo venv"
	@echo "  make run      - Chạy desktop app"
	@echo "  make test     - Test PyQt6 installation"
	@echo "  make clean    - Xóa cache và __pycache__"
	@echo "  make help     - Hiển thị help này"
	@echo ""

# Check deps → setup nếu thiếu → run
check-and-run:
	@if [ ! -d "venv" ] || ! venv/bin/python3 -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null; then \
		echo "⚠️  Missing dependencies, running setup..."; \
		$(MAKE) setup; \
	fi
	@$(MAKE) run

# Setup: cài system deps + venv + python packages
setup:
	@echo "📦 Installing system dependencies..."
	@sudo apt update -qq
	@sudo apt install -y -qq \
		python3-pip \
		python3-venv \
		python3-dev \
		python3-pyqt6 \
		python3-pyqt6.qtwebengine \
		libxcb-xinerama0 \
		libxcb-cursor0 \
		libxkbcommon-x11-0 \
		libegl1 \
		libgl1-mesa-glx \
		libglib2.0-0 \
		libdbus-1-3 \
		libfontconfig1 \
		libfreetype6 \
		libx11-6 \
		libx11-xcb1
	@echo "✅ System deps installed"
	@echo ""
	@echo "📦 Creating virtual environment (with system packages)..."
	@rm -rf venv
	@python3 -m venv --system-site-packages venv
	@echo "✅ Virtual environment created"
	@echo ""
	@echo "📥 Installing Python packages..."
	@bash -c "source venv/bin/activate && pip install -q --upgrade pip && pip install -q -r requirements.txt"
	@echo "✅ Python packages installed"
	@echo ""
	@echo "🎉 Setup complete! Run 'make run' to start the app."

# Run app
run:
	@if [ ! -d "venv" ]; then \
		echo "❌ venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "🚀 Starting ParkAI Desktop..."
	@bash -c "source venv/bin/activate && python3 main.py"

# Test PyQt6 installation
test:
	@echo "🧪 Testing PyQt6 installation..."
	@if [ ! -d "venv" ]; then \
		echo "❌ venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@bash -c "source venv/bin/activate && python3 -c 'from PyQt6.QtWidgets import QApplication; print(\"✅ PyQt6 OK\")'"
	@bash -c "source venv/bin/activate && python3 -c 'import requests; print(\"✅ requests OK\")'"
	@bash -c "source venv/bin/activate && python3 -c 'import websocket; print(\"✅ websocket-client OK\")'"
	@echo "🎉 All dependencies OK!"

# Clean cache
clean:
	@echo "🧹 Cleaning cache..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"

# Clean all (including venv)
clean-all: clean
	@echo "🧹 Removing virtual environment..."
	@rm -rf venv
	@echo "✅ All clean!"
