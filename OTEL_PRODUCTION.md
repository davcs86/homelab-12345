# OpenTelemetry Production Configuration

## Current Setup (Default)

**By default, telemetry goes to console logs only.**

Your app is already collecting traces, metrics, and logs. You can see them in App Platform's Runtime Logs.

**No configuration needed!** Deploy and it works.

---

## Send to Grafana Cloud (Optional)

To send telemetry to Grafana Cloud, make these 2 changes:

### 1. Update `config/otel-collector-config.yaml`

Add the OTLP exporter:

```yaml
exporters:
  logging:
    loglevel: info

  otlp:
    endpoint: otlp-gateway-prod-us-central-0.grafana.net:443
    headers:
      authorization: "Basic ${env:GRAFANA_CLOUD_TOKEN}"
    tls:
      insecure: false

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [logging, otlp]  # Changed: added otlp

    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [logging, otlp]  # Changed: added otlp

    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [logging, otlp]  # Changed: added otlp
```

**Note:** Get your Grafana Cloud OTLP endpoint from: Grafana Cloud Portal → Stack → OTLP

### 2. Add Token in `.do/app.yaml`

```yaml
envs:
  # ... existing env vars ...

  - key: GRAFANA_CLOUD_TOKEN
    value: your-grafana-cloud-token-here
    scope: RUN_TIME
    type: SECRET
```

**Note:** Get your token from: Grafana Cloud Portal → Stack → OTLP

### 3. Deploy

```bash
git add config/otel-collector-config.yaml .do/app.yaml
git commit -m "Add Grafana Cloud"
git push

# Or update existing app
doctl apps update <APP_ID> --spec .do/app.yaml
```

Done! Telemetry now goes to both console logs AND Grafana Cloud.

---

## Other Platforms

For Datadog, Honeycomb, New Relic, or other platforms:

1. Check their OTEL documentation for the exporter configuration
2. Add the exporter to `config/otel-collector-config.yaml`
3. Add required API keys/tokens to `.do/app.yaml` as secrets
4. Deploy

The pattern is the same - just replace the exporter details.
