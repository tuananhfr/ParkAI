.PHONY: all check-and-run install run dev test clean setup start stop check-models

# Default: chỉ cần gõ "make"
.DEFAULT_GOAL := all

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default: chỉ cần gõ "make"
all: check-and-run

# Check deps → setup nếu thiếu → run
check-and-run:
	@if [ ! -d "venv" ]; then \
		echo "$(YELLOW)Virtual environment not found. Creating...$(NC)"; \
		$(MAKE) setup-venv; \
	fi
	@if [ ! -f "models/license_plate.pt" ]; then \
		echo "$(RED)Error: models/license_plate.pt not found!$(NC)"; \
		echo "$(YELLOW)Please add model file to models/ directory$(NC)"; \
		exit 1; \
	fi
	@$(MAKE) run

help: ## Show this help message
	@echo "$(BLUE)Camera IP Backend - License Plate Detection$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Installation

setup-venv: ## Create virtual environment and install dependencies
	@echo "$(GREEN)Creating virtual environment...$(NC)"
	@python3 -m venv venv
	@echo "$(GREEN)Installing dependencies...$(NC)"
	@bash -c "source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
	@echo "$(GREEN)Virtual environment setup complete!$(NC)"

install: ## Install all Python dependencies (requires venv)
	@if [ ! -d "venv" ]; then \
		echo "$(RED)Error: venv not found. Run 'make setup-venv' first.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Installing Python dependencies...$(NC)"
	@bash -c "source venv/bin/activate && pip install -r requirements.txt"
	@echo "$(GREEN)Installation complete!$(NC)"

setup: setup-venv check-models ## Complete setup (venv + deps + check models)
	@echo "$(GREEN)Setup complete! Run 'make run' or 'make dev'$(NC)"

check-models: ## Check if model files exist
	@echo "$(BLUE)Checking model files...$(NC)"
	@if [ ! -f "models/license_plate.pt" ]; then \
		echo "$(RED)Error: models/license_plate.pt not found!$(NC)"; \
		exit 1; \
	fi
	@if [ ! -f "models/ocr.onnx" ]; then \
		echo "$(YELLOW)Warning: models/ocr.onnx not found (optional)$(NC)"; \
	fi
	@echo "$(GREEN)Model files OK$(NC)"

##@ Running

run: ## Run production server (port 5000)
	@if [ ! -d "venv" ]; then \
		echo "$(RED)Error: venv not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Starting production server...$(NC)"
	@bash -c "source venv/bin/activate && python main.py"

dev: ## Run development server with auto-reload
	@if [ ! -d "venv" ]; then \
		echo "$(RED)Error: venv not found. Run 'make setup' first.$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Starting development server with auto-reload...$(NC)"
	@bash -c "source venv/bin/activate && uvicorn main:app --reload --port 5000"

start: ## Start server with go2rtc (both API and go2rtc)
	@echo "$(GREEN)Starting API and go2rtc...$(NC)"
	npm start

start-api: run ## Start only API server (alias for run)

start-dev: dev ## Start only API in dev mode (alias for dev)

##@ Testing

test: ## Run detection tests
	@echo "$(GREEN)Running detection tests...$(NC)"
	@if [ -f "test_detection.py" ]; then \
		python test_detection.py; \
	else \
		echo "$(YELLOW)test_detection.py not found$(NC)"; \
	fi

test-health: ## Test health endpoint
	@echo "$(BLUE)Testing health endpoint...$(NC)"
	@curl -s http://localhost:5000/health || echo "$(RED)Server not running$(NC)"

test-api: ## Test API endpoints (requires server running)
	@echo "$(BLUE)Testing API endpoints...$(NC)"
	@curl -s http://localhost:5000/health && echo "$(GREEN)Health: OK$(NC)" || echo "$(RED)Health: FAILED$(NC)"
	@curl -s http://localhost:5000/api/cameras | python -m json.tool || echo "$(RED)Cameras API: FAILED$(NC)"

##@ Maintenance

clean: ## Clean cache files and temporary files
	@echo "$(YELLOW)Cleaning cache files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean complete!$(NC)"

clean-all: clean ## Clean everything including models and uploads
	@echo "$(YELLOW)Cleaning all generated files...$(NC)"
	rm -f output_detection.jpg 2>/dev/null || true
	rm -rf uploads/* 2>/dev/null || true
	@echo "$(GREEN)Clean all complete!$(NC)"

##@ Information

info: ## Show system information
	@echo "$(BLUE)System Information:$(NC)"
	@echo "Python version:"
	@python --version
	@echo ""
	@echo "pip version:"
	@pip --version
	@echo ""
	@echo "Installed packages:"
	@pip list | grep -E "fastapi|uvicorn|torch|ultralytics|opencv" || echo "$(YELLOW)Some packages not installed$(NC)"

check: check-models info ## Run all checks

status: ## Check if server is running
	@echo "$(BLUE)Checking server status...$(NC)"
	@curl -s http://localhost:5000/health > /dev/null && echo "$(GREEN)Server is running$(NC)" || echo "$(RED)Server is not running$(NC)"

##@ Documentation

docs: ## Open API documentation in browser
	@echo "$(GREEN)Opening API docs...$(NC)"
	@echo "Swagger UI: http://localhost:5000/docs"
	@echo "ReDoc: http://localhost:5000/redoc"

show-endpoints: ## Show all available API endpoints
	@echo "$(BLUE)Available API Endpoints:$(NC)"
	@echo ""
	@echo "$(GREEN)Camera Management:$(NC)"
	@echo "  GET    /api/cameras"
	@echo "  POST   /api/cameras"
	@echo "  PUT    /api/cameras/{id}"
	@echo "  DELETE /api/cameras/{id}"
	@echo ""
	@echo "$(GREEN)License Plate Detection:$(NC)"
	@echo "  POST   /api/detect/upload"
	@echo "  POST   /api/detect/upload/visualize"
	@echo "  POST   /api/detect/rtsp"
	@echo ""
	@echo "$(GREEN)System:$(NC)"
	@echo "  GET    /health"
	@echo ""
	@echo "$(YELLOW)Docs: http://localhost:5000/docs$(NC)"

##@ Quick Start

quickstart: setup run ## Complete quickstart (setup + run)
