"""
Example Flask Application managed by Supervisord
This is a simple demo app to showcase multi-process management
"""

from flask import Flask, jsonify, Response, request
import os
import sys
import logging
import subprocess
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure OpenTelemetry if enabled
otel_enabled = os.getenv('OTEL_ENABLED', 'true').lower() == 'true'
if otel_enabled:
    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.sdk.resources import Resource

        # OTEL_EXPORTER_OTLP_ENDPOINT is the base URL for all signals
        # The Python OTLP HTTP exporters need the full path to each endpoint
        base_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        
        # Set up resource with service name
        resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "supervisord-app")})
        
        # Configure Traces
        trace_provider = TracerProvider(resource=resource)
        trace_exporter = OTLPSpanExporter(endpoint=f"{base_endpoint}/v1/traces")
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)
        
        # Configure Metrics
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{base_endpoint}/v1/metrics")
        )
        metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(metric_provider)
        
        # Configure Logs
        log_provider = LoggerProvider(resource=resource)
        log_exporter = OTLPLogExporter(endpoint=f"{base_endpoint}/v1/logs")
        log_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
        
        # Attach OTEL handler to Python logging
        handler = LoggingHandler(logger_provider=log_provider)
        logging.getLogger().addHandler(handler)

        # Instrument Flask app (auto-generates traces and metrics)
        FlaskInstrumentor().instrument_app(app)

        logger.info(f"OpenTelemetry instrumentation enabled - base endpoint: {base_endpoint}")
        logger.info(f"  Traces: {base_endpoint}/v1/traces")
        logger.info(f"  Metrics: {base_endpoint}/v1/metrics")
        logger.info(f"  Logs: {base_endpoint}/v1/logs")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry: {e}")
        otel_enabled = False
else:
    logger.info("OpenTelemetry instrumentation disabled")

@app.route('/')
def home():
    """Home endpoint - shows process architecture"""
    try:
        # Get current process info
        current_pid = os.getpid()
        current_ppid = os.getppid()

        # Get process tree
        ps_output = subprocess.check_output(['ps', 'auxf'], text=True)

        # Get supervisorctl status
        supervisor_status = None
        supervisor_processes = []
        try:
            supervisor_status = subprocess.check_output(
                ['supervisorctl', '-c', '/etc/supervisor/conf.d/supervisord.conf', 'status'],
                text=True,
                stderr=subprocess.STDOUT
            )
            # Parse supervisor status into structured data
            for line in supervisor_status.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        supervisor_processes.append({
                            'name': parts[0],
                            'status': parts[1],
                            'details': ' '.join(parts[2:]) if len(parts) > 2 else ''
                        })
        except Exception as e:
            supervisor_status = f"Error: {str(e)}"

        # Get PID 1 info
        pid1_cmd = None
        try:
            pid1_info = subprocess.check_output(['ps', '-p', '1', '-o', 'cmd'], text=True)
            pid1_cmd = pid1_info.strip().split('\n')[1] if '\n' in pid1_info else pid1_info
        except Exception as e:
            pid1_cmd = f"Error: {str(e)}"

        # Check if JSON format is requested
        if request.args.get('format') == 'json':
            return jsonify({
                'status': 'ok',
                'architecture': {
                    'description': 'Multi-process container managed by supervisord',
                    'pid_1': {
                        'process': 'supervisord',
                        'command': pid1_cmd,
                        'role': 'Process supervisor and PID 1'
                    },
                    'managed_processes': supervisor_processes
                },
                'current_request': {
                    'handler_pid': current_pid,
                    'parent_pid': current_ppid,
                    'process_name': 'Flask application'
                },
                'raw_data': {
                    'supervisor_status': supervisor_status,
                    'process_tree': ps_output
                }
            })

        # Return HTML view
        return render_process_html(current_pid, current_ppid, pid1_cmd, supervisor_processes, ps_output)

    except Exception as e:
        logger.error(f"Error in home endpoint: {e}", exc_info=True)
        return jsonify({
            'error': str(e),
            'current_process': {
                'pid': os.getpid(),
                'ppid': os.getppid()
            }
        }), 500

@app.route('/health')
def health():
    """Health check endpoint for App Platform"""
    return jsonify({
        'status': 'healthy',
        'service': 'supervisord-app'
    }), 200

@app.route('/info')
def info():
    """Show environment and process information"""
    return jsonify({
        'environment': {
            'APP_ENV': os.getenv('APP_ENV', 'development'),
            'PORT': os.getenv('PORT', '8080'),
            'OTEL_ENABLED': str(otel_enabled)
        },
        'process_manager': 'supervisord',
        'python_version': sys.version
    })

@app.route('/test-trace')
def test_trace():
    """Generate custom trace spans to demonstrate OTEL instrumentation"""
    if not otel_enabled:
        return jsonify({
            'error': 'OpenTelemetry is not enabled',
            'hint': 'Set OTEL_ENABLED=true environment variable'
        }), 400

    # Get tracer and create custom spans
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("custom-operation") as span:
        span.set_attribute("operation.type", "demo")
        span.set_attribute("operation.id", random.randint(1000, 9999))

        # Simulate some processing
        time.sleep(0.05)

    return jsonify({
        'status': 'success',
        'message': 'Custom trace generated!',
        'otel_enabled': True,
        'service_name': os.getenv("OTEL_SERVICE_NAME", "supervisord-app")
    })

def render_process_html(current_pid, current_ppid, pid1_cmd, supervisor_processes, ps_output):
    """Render a nice HTML view of the process information"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Supervisord Process Monitor</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 1200px;
                margin: 40px auto;
                padding: 0 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                border-radius: 8px;
                padding: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #0080FF;
                margin-top: 0;
            }
            h2 {
                color: #333;
                border-bottom: 2px solid #0080FF;
                padding-bottom: 10px;
                margin-top: 30px;
            }
            .status-box {
                background: #f8f9fa;
                border-left: 4px solid #0080FF;
                padding: 15px;
                margin: 15px 0;
                border-radius: 4px;
            }
            .process-item {
                background: #fff;
                border: 1px solid #e0e0e0;
                padding: 12px;
                margin: 10px 0;
                border-radius: 4px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .status-running {
                color: #28a745;
                font-weight: bold;
            }
            .status-stopped {
                color: #dc3545;
                font-weight: bold;
            }
            .pid-badge {
                background: #0080FF;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            pre {
                background: #1e1e1e;
                color: #d4d4d4;
                padding: 20px;
                border-radius: 4px;
                overflow-x: auto;
                font-size: 13px;
            }
            .metric {
                display: inline-block;
                margin-right: 20px;
            }
            .metric-label {
                color: #666;
                font-size: 14px;
            }
            .metric-value {
                color: #333;
                font-size: 20px;
                font-weight: bold;
            }
            .architecture-diagram {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 4px;
                font-family: monospace;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Supervisord Process Monitor</h1>

            <div class="status-box">
                <strong>Multi-Process Architecture Active</strong><br>
                Supervisord is managing multiple processes in a single container
            </div>

            <h2>📊 Architecture Overview</h2>
            <div style="background: #fff; border: 2px solid #0080FF; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <div style="text-align: center; color: #666; font-weight: bold; margin-bottom: 20px;">
                    Container (DigitalOcean App Platform)
                </div>

                <div style="background: #e3f2fd; border: 2px solid #0080FF; border-radius: 6px; padding: 15px; margin: 10px 20px;">
                    <div style="text-align: center;">
                        <div style="background: #0080FF; color: white; display: inline-block; padding: 10px 20px; border-radius: 6px; margin-bottom: 10px;">
                            <strong>PID 1: supervisord</strong>
                        </div>
                        <div style="color: #666; font-size: 14px;">Process Supervisor &amp; Init System</div>
                    </div>

                    <div style="text-align: center; margin: 20px 0;">
                        <div style="font-size: 24px; color: #0080FF;">↓</div>
                        <div style="color: #666; font-size: 12px;">manages</div>
                    </div>

                    <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 15px;">
    """

    # Add a box for each supervisor process
    for proc in supervisor_processes:
        is_running = proc['status'] == 'RUNNING'
        border_color = '#28a745' if is_running else '#dc3545'
        status_color = '#28a745' if is_running else '#dc3545'
        status_icon = '✓' if is_running else '✗'

        # Determine process description
        if proc['name'] == 'app':
            description = 'Flask Application'
            extra_info = 'Port 8080'
        elif proc['name'] == 'otel-agent':
            description = 'OTEL Agent'
            extra_info = '(Sidecar)'
        else:
            description = proc['name'].replace('-', ' ').title()
            extra_info = 'Process'

        html += f"""
                        <div style="background: white; border: 2px solid {border_color}; border-radius: 6px; padding: 15px; min-width: 200px; text-align: center;">
                            <div style="color: {status_color}; font-weight: bold; margin-bottom: 5px;">{status_icon} {proc['status']}</div>
                            <div style="font-weight: bold;">{proc['name']}</div>
                            <div style="color: #666; font-size: 14px; margin-top: 5px;">{description}</div>
                            <div style="color: #999; font-size: 12px;">{extra_info}</div>
                        </div>
        """

    html += f"""
                    </div>
                </div>
            </div>

            <h2>🎯 PID 1 (Init Process)</h2>
            <div class="process-item">
                <div>
                    <strong>supervisord</strong><br>
                    <code style="color: #666;">{pid1_cmd}</code>
                </div>
                <span class="pid-badge">PID 1</span>
            </div>

            <h2>⚙️ Managed Processes</h2>
    """

    for proc in supervisor_processes:
        status_class = 'status-running' if proc['status'] == 'RUNNING' else 'status-stopped'
        html += f"""
            <div class="process-item">
                <div>
                    <strong>{proc['name']}</strong><br>
                    <span class="{status_class}">{proc['status']}</span> - {proc['details']}
                </div>
            </div>
        """

    html += f"""
            <h2>📍 Current Request Handler</h2>
            <div class="status-box">
                <div class="metric">
                    <div class="metric-label">Process ID</div>
                    <div class="metric-value">{current_pid}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Parent PID</div>
                    <div class="metric-value">{current_ppid}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Process</div>
                    <div class="metric-value">Flask App</div>
                </div>
            </div>

            <h2>🌳 Full Process Tree</h2>
            <pre>{ps_output}</pre>

            <p style="text-align: center; color: #666; margin-top: 40px;">
                <small>Add <code>?format=json</code> to URL for JSON API response | <a href="/health">Health Check</a> | <a href="/info">Info</a></small>
            </p>
        </div>
    </body>
    </html>
    """

    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    logger.info(f"Starting Flask app on port {port}")

    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.getenv('APP_ENV') == 'development'
    )
