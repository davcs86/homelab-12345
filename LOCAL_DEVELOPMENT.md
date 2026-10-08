# Local Development Guide

This guide will help you run and test the Supervisord application on your local machine using Docker.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- [Docker Compose](https://docs.docker.com/compose/install/) installed
- `make` command (comes with macOS/Linux, Windows users can use Git Bash)

## Quick Start

### 1. Build and Run

```bash
# Build the Docker image
make build

# Start the application
make up

# Or start with logs visible (recommended for first run)
make dev
```

The application will be available at: **http://127.0.0.1:8080**

**Note**: If you're using OrbStack, use `127.0.0.1` instead of `localhost` due to networking differences.

### 2. View the Dashboard

Open your browser and visit:
- **http://127.0.0.1:8080** - Process monitoring dashboard
- **http://127.0.0.1:8080/health** - Health check
- **http://127.0.0.1:8080/info** - Environment info
- **http://127.0.0.1:8080/?format=json** - JSON API

### 3. Stop the Application

```bash
make down
```

## Available Commands

### Basic Operations

```bash
make build       # Build Docker image
make up          # Start in background
make dev         # Start with logs visible
make down        # Stop application
make restart     # Restart container
make logs        # View live logs
```

### Supervisord Management

```bash
make status      # Check process status
make shell       # Open bash in container
make restart-app # Restart Flask app only
```

### Testing

```bash
make test        # Test health and info endpoints
make processes   # View process architecture (JSON)
```

### Cleanup

```bash
make clean       # Remove containers and images
make fresh       # Clean rebuild from scratch
```

## Interacting with Supervisord

### Check Process Status

```bash
# Via make command
make status

# Or inside container
make shell
supervisorctl status
```

Expected output:
```
app                              RUNNING   pid 2, uptime 0:05:23
```

### Restart Processes

```bash
# From host
make restart-app

# Or inside container
make shell
supervisorctl restart app
```

### View Process Logs

```bash
# Container logs
make logs

# Or inside container
make shell
tail -f /var/log/app/app.out.log
```

## Development Workflow

### 1. Live Development (Optional)

Uncomment the volumes section in `docker-compose.yml` to enable live code reloading:

```yaml
volumes:
  - ./app:/app
  - ./config/supervisord.conf:/etc/supervisor/conf.d/supervisord.conf
```

Then restart:
```bash
make restart-app
```

### 2. Test Changes

```bash
# Make code changes in app/app.py

# Restart the app
make restart-app

# View logs
make logs

# Test endpoints
make test
```

### 3. Add New Processes

1. Edit `config/supervisord.conf` to add agents or sidecars:
```ini
[program:monitoring-agent]
command=python monitoring_agent.py
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/fd/1
stdout_logfile_maxbytes=0
```

2. Rebuild and restart:
```bash
make fresh
```

3. Check status:
```bash
make status
```

## Verifying Multi-Process Architecture

### Option 1: Web Dashboard

Visit **http://127.0.0.1:8080** in your browser to see:
- Visual architecture diagram
- PID 1 (supervisord) information
- All managed processes
- Process tree

### Option 2: Command Line

```bash
# Get JSON process info
make processes

# Or detailed view
curl -s "http://127.0.0.1:8080/?format=json" | python3 -m json.tool
```

### Option 3: Inside Container

```bash
make shell

# Check PID 1
ps -p 1

# View process tree
ps auxf

# Supervisord status
supervisorctl status
```

Expected output shows:
- **PID 1**: supervisord
- **PID 2+**: Flask app and other managed processes

## Troubleshooting

### Container Won't Start

```bash
# Check logs
make logs

# Rebuild from scratch
make fresh
```

### Port Already in Use

If port 8080 is busy, edit `docker-compose.yml`:
```yaml
ports:
  - "8888:8080"  # Change host port to 8888
```

Then visit http://127.0.0.1:8888

### Cannot Connect to Docker

```bash
# Check Docker is running
docker ps

# Start Docker Desktop (macOS/Windows)
# or start Docker daemon (Linux)
```

### Process Not Starting

```bash
# Enter container
make shell

# Check supervisord logs
cat /var/log/supervisor/supervisord.log

# Try starting manually
supervisorctl start app
```

## Simulating App Platform Environment

To test with App Platform-like settings:

```bash
# Edit docker-compose.yml
environment:
  - APP_ENV=production
  - PORT=8080
  - OTEL_ENABLED=false

# Restart
make restart
```

## Adding OpenTelemetry Agent

1. Uncomment OTEL dependencies in `app/requirements.txt`

2. Enable in `docker-compose.yml`:
```yaml
environment:
  - OTEL_ENABLED=true
  - OTEL_EXPORTER_OTLP_ENDPOINT=http://your-collector:4318
```

3. Uncomment `[program:otel-agent]` in `config/supervisord.conf`

4. Rebuild:
```bash
make fresh
```

## Best Practices

1. **Always use `make` commands** for common operations
2. **Check logs** after starting: `make logs`
3. **Use `make status`** to verify processes are running
4. **Clean rebuild** if issues occur: `make fresh`
5. **Test endpoints** before deploying: `make test`

## Next Steps

- **Customize** `app/app.py` with your application logic
- **Add monitoring agents** or sidecars in `config/supervisord.conf`
- **Test OTEL instrumentation** with `make test-trace`
- **Test locally** with `make dev`
- **Deploy** to App Platform when ready

## Resources

- [Supervisord Documentation](http://supervisord.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Flask Documentation](https://flask.palletsprojects.com/)

## Getting Help

If you encounter issues:

1. Check logs: `make logs`
2. Verify status: `make status`
3. Try clean rebuild: `make fresh`
4. Open shell for debugging: `make shell`

---

Happy developing! 🚀
