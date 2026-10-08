.PHONY: build up down logs shell restart clean

# Build the Docker image
build:
	docker-compose build

# Start the application
up:
	docker-compose up -d
	@echo ""
	@echo "✅ Application started!"
	@echo "🌐 Visit: http://127.0.0.1:8080"
	@echo "   (If using OrbStack, use 127.0.0.1 instead of localhost)"
	@echo "📊 View logs: make logs"
	@echo ""

# Start with logs visible
dev:
	docker-compose up

# Stop the application
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# Open shell in running container
shell:
	docker-compose exec supervisord-app /bin/bash

# Check supervisord status
status:
	docker-compose exec supervisord-app supervisorctl status

# Restart supervisord processes
restart-app:
	docker-compose exec supervisord-app supervisorctl restart app

# Restart the entire container
restart:
	docker-compose restart

# Clean up (remove containers, images, volumes)
clean:
	docker-compose down -v
	docker-compose rm -f
	docker rmi supervisord-appplatform-supervisord-app 2>/dev/null || true

# Rebuild and start fresh
fresh: clean build up

# Test the application
test:
	@echo "Testing health endpoint..."
	@curl -s http://127.0.0.1:8080/health | python3 -m json.tool
	@echo ""
	@echo "Testing info endpoint..."
	@curl -s http://127.0.0.1:8080/info | python3 -m json.tool

# Test OTEL trace generation
test-trace:
	@echo "Generating test trace..."
	@curl -s http://127.0.0.1:8080/test-trace | python3 -m json.tool
	@echo ""
	@echo "View traces with: make logs | grep custom-operation"

# Show process information
processes:
	@curl -s "http://127.0.0.1:8080/?format=json" | python3 -m json.tool

help:
	@echo "Available commands:"
	@echo "  make build       - Build Docker image"
	@echo "  make up          - Start application (background)"
	@echo "  make dev         - Start application (foreground with logs)"
	@echo "  make down        - Stop application"
	@echo "  make logs        - View application logs"
	@echo "  make shell       - Open bash shell in container"
	@echo "  make status      - Check supervisord process status"
	@echo "  make restart-app - Restart Flask app via supervisord"
	@echo "  make restart     - Restart entire container"
	@echo "  make clean       - Remove containers and images"
	@echo "  make fresh       - Clean rebuild and start"
	@echo "  make test        - Test health and info endpoints"
	@echo "  make test-trace  - Generate OTEL test trace"
	@echo "  make processes   - Show process architecture (JSON)"
	@echo "  make help        - Show this help message"
