FROM python:3.11-slim

# Install supervisor and basic dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    curl \
    procps \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install OpenTelemetry Collector
RUN wget -O /tmp/otelcol-contrib.tar.gz \
    https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v0.91.0/otelcol-contrib_0.91.0_linux_amd64.tar.gz \
    && tar -xzf /tmp/otelcol-contrib.tar.gz -C /usr/local/bin/ \
    && rm /tmp/otelcol-contrib.tar.gz \
    && chmod +x /usr/local/bin/otelcol-contrib

# Create application directory
WORKDIR /app

# Copy application files
COPY app/ /app/
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/otel-collector-config.yaml /app/otel-collector-config.yaml

# Make start script executable
RUN chmod +x /app/start.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /var/log/supervisor /var/log/app /var/run

# Expose application port and OTEL collector ports
EXPOSE 8080 4317 4318

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start supervisord as the main process with explicit nodaemon flag
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
