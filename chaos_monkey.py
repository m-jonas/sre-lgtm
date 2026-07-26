import os
import random
import subprocess
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, SimpleLogRecordProcessor

# Configuration
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = "chaos-monkey"
DEFAULT_TARGETS = "stock-generator,loki,tempo,mimir,otel-collector,grafana"
CHAOS_TARGETS = os.getenv("CHAOS_TARGETS", DEFAULT_TARGETS).split(",")

resource = Resource.create({"service.name": SERVICE_NAME})

# 1. Setup Tracing
trace_provider = TracerProvider(resource=resource)
trace_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
# Use SimpleSpanProcessor since this is a script that runs and exits immediately
trace_provider.add_span_processor(SimpleSpanProcessor(trace_exporter))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# 2. Setup Metrics
metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=1000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

chaos_counter = meter.create_counter("chaos_events_total", description="Total number of chaos events triggered")

# 3. Setup Logging
logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter(endpoint=OTLP_ENDPOINT, insecure=True)
# Use SimpleLogRecordProcessor for script
logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# Also set root logger to see standard prints
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


def execute_chaos():
    with tracer.start_as_current_span("execute_chaos") as span:
        # Determine number of targets to affect (1 to all)
        num_targets = random.randint(1, len(CHAOS_TARGETS))
        targets = random.sample(CHAOS_TARGETS, num_targets)

        span.set_attribute("chaos.num_targets", num_targets)
        span.set_attribute("chaos.targets", targets)

        logger.info(f"Triggering chaos on {num_targets} targets: {', '.join(targets)}", extra={"targets": targets})

        for target in targets:
            action = random.choice(["kill", "restart"])
            span.set_attribute(f"chaos.action.{target}", action)

            chaos_counter.add(1, {"target": target, "action": action})
            logger.info(f"Applying '{action}' to service: {target}", extra={"target": target, "action": action})

            try:
                # Check if target is running as a Kubernetes pod
                k8s_pods_res = subprocess.run(
                    ["kubectl", "get", "pods", "-l", f"app={target}", "-o", "jsonpath='{.items[*].metadata.name}'"],
                    capture_output=True, text=True
                )
                pod_names = k8s_pods_res.stdout.strip().strip("'").split()
                if pod_names and pod_names[0]:
                    # Kubernetes target disruption
                    if action == "kill":
                        target_pod = random.choice(pod_names)
                        logger.info(f"Killing Kubernetes pod: {target_pod}")
                        subprocess.run(["kubectl", "delete", "pod", target_pod, "--grace-period=0", "--force"], check=True, capture_output=True)
                    elif action == "restart":
                        logger.info(f"Triggering rolling restart for Kubernetes deployment: {target}")
                        subprocess.run(["kubectl", "rollout", "restart", f"deployment/{target}"], check=True, capture_output=True)
                else:
                    # Docker Compose target disruption
                    if action == "kill":
                        container_id = subprocess.run(["docker", "compose", "ps", "-q", target], check=True, capture_output=True, text=True).stdout.strip()
                        if container_id:
                            subprocess.run(["docker", "restart", "-t", "0", container_id], check=True, capture_output=True)
                        else:
                            logger.warning(f"Could not find container or pod for service {target} to disrupt")
                    elif action == "restart":
                        subprocess.run(["docker", "compose", "restart", target], check=True, capture_output=True)

                logger.info(f"Successfully executed {action} on {target}")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
                logger.error(f"Failed to execute {action} on {target}: {err_msg}")
                span.set_attribute(f"chaos.error.{target}", err_msg)

if __name__ == "__main__":
    logger.info("Starting chaos monkey...")
    execute_chaos()
    logger.info("Chaos monkey finished.")

    # Ensure telemetry is flushed before exit
    try:
        meter_provider.force_flush()
        trace_provider.force_flush()
        logger_provider.force_flush()
    except Exception as e:
        print(f"Error flushing telemetry: {e}")
