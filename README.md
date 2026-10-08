# Supervisord on DigitalOcean App Platform

A production-ready template for running multi-process applications on DigitalOcean App Platform using [Supervisord](http://supervisord.org/).

[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/AppPlatform-Templates/supervisord-appplatform/tree/main)

## What is Supervisord?

Supervisord is a process control system for UNIX-like systems. It's designed for application-level process management, making it ideal for containerized environments where you need to run multiple related processes together.

## Use Cases

- **Web Service + Monitoring**: Run your application with OpenTelemetry Collector or other monitoring sidecars
- **Multi-Process Applications**: Applications that need multiple related processes in one container
- **Sidecar Pattern**: Run auxiliary processes alongside your main application (logging agents, proxies, etc.)

## What's Included

**Running Processes**:
1. **Flask Web App** - Example application on port 8080 with OpenTelemetry instrumentation
2. **OTEL Collector** - OpenTelemetry sidecar for observability
3. Both managed by **Supervisord** (process manager)

**Endpoints**:
- Process dashboard at `/` showing all running processes
- Health check endpoint at `/health`
- Test trace endpoint at `/test-trace` to verify OTEL instrumentation

## Architecture

```
┌─────────────────────────────────────┐
│   DigitalOcean App Platform         │
│                                     │
│  ┌───────────────────────────────┐  │
│  │    Container (Port 8080)      │  │
│  │                               │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │   Supervisord (PID 1)   │  │  │
│  │  └──────────┬──────────────┘  │  │
│  │             │                 │  │
│  │    ┌────────┴────────┐        │  │
│  │    │                 │        │  │
│  │  ┌─▼──────┐    ┌────▼─────┐   │  │
│  │  │ Flask  │    │   OTEL   │   │  │
│  │  │  Web   │    │  Agent   │   │  │
│  │  │  App   │    │ (Sidecar)│   │  │
│  │  │ :8080  │    │          │   │  │
│  │  └────────┘    └──────────┘   │  │
│  │                               │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Project Structure

```
supervisord-appplatform/
├── .do/
│   ├── app.yaml                      # App Platform deployment spec
│   └── deploy.template.yaml          # Deploy button template
├── app/
│   ├── app.py                        # Example Flask application
│   ├── requirements.txt              # Python dependencies
│   └── start.sh                      # Application startup script
├── config/
│   ├── supervisord.conf              # Supervisord configuration
│   └── otel-collector-config.yaml    # OpenTelemetry Collector config
├── Dockerfile                        # Container definition
├── docker-compose.yml                # Local development setup
└── Makefile                          # Development commands
```

## Deployment Methods

### One-Click Deploy

Click the "Deploy to DigitalOcean" button above to deploy instantly with zero configuration.

### Deploy via CLI

```bash
# Clone the repository
git clone https://github.com/AppPlatform-Templates/supervisord-appplatform.git
cd supervisord-appplatform

# Deploy to App Platform
doctl apps create --spec .do/app.yaml
```

**To customize**: Fork this repo, update the repo reference in your chosen template (`.do/` folder) to point to your fork, then deploy.

## Local Development

Run locally using Docker Compose:

```bash
docker-compose up
```

Access the app at `http://localhost:8080` or `http://127.0.0.1:8080`

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for detailed local development instructions.

## Configure OpenTelemetry (Optional)

By default, traces/logs/metrics are exported to console logs (visible in App Platform Runtime Logs).

To send to production backends (Grafana Cloud, Datadog, Honeycomb, etc.), see [OTEL_PRODUCTION.md](OTEL_PRODUCTION.md).

To disable OTEL, remove the `[program:otel-collector]` section from `config/supervisord.conf`.

## Resources

- [Supervisord Documentation](http://supervisord.org/)
- [DigitalOcean App Platform Documentation](https://docs.digitalocean.com/products/app-platform/)
- [App Spec Reference](https://docs.digitalocean.com/products/app-platform/reference/app-spec/)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Local Development Guide](LOCAL_DEVELOPMENT.md)

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/AppPlatform-Templates/supervisord-appplatform/issues)
- **DigitalOcean Community**: [community.digitalocean.com](https://www.digitalocean.com/community)
- **Support**: [DigitalOcean Support](https://www.digitalocean.com/support/)
