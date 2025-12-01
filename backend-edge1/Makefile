.PHONY: all setup run clean

# Default: chỉ cần gõ "make"
all: check-and-run

# Check deps → setup nếu thiếu → run
check-and-run:
	@if [ ! -d "venv" ] || ! python3 -c "from picamera2 import Picamera2" 2>/dev/null || ! pkg-config --exists libavformat 2>/dev/null; then \
		echo "⚠️  Missing dependencies, running setup..."; \
		$(MAKE) setup; \
	fi
	@$(MAKE) run

# Setup: cài system deps + venv + python packages
setup:
	@echo "📦 Installing system dependencies..."
	@sudo apt update -qq
	@sudo apt install -y python3-picamera2 \
		libavformat-dev libavcodec-dev libavdevice-dev \
		libavutil-dev libavfilter-dev libswscale-dev \
		libswresample-dev pkg-config
	@echo "✅ System deps installed"
	@echo "📦 Creating venv..."
	@rm -rf venv
	@python3 -m venv --system-site-packages venv
	@echo "📥 Installing Python packages..."
	@bash -c "source venv/bin/activate && pip install -q --upgrade pip && pip install -q -r requirements.txt"
	@mkdir -p data
	@echo "✅ Setup complete"

# Run app
run:
	@if [ ! -d "venv" ]; then \
		echo "❌ venv not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "🎯 Starting server..."
	@bash -c "source venv/bin/activate && python3 app.py"

# Clean cache
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete"
