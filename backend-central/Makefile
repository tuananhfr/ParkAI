.PHONY: all setup run clean

# Default: chỉ cần gõ "make"
all: check-and-run

# Check deps → setup nếu thiếu → run
check-and-run:
	@if [ ! -d "venv" ]; then \
		echo "⚠️  venv not found, running setup..."; \
		$(MAKE) setup; \
	fi
	@$(MAKE) run

# Setup: tạo venv + cài python packages
setup:
	@echo "📦 Creating venv..."
	@rm -rf venv
	@python3 -m venv venv
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
	@echo "🎯 Starting Central Server..."
	@bash -c "source venv/bin/activate && python3 app.py"

# Clean cache
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete"
