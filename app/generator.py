import time
import random
import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
import os

# Configuration
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://otel-collector:4317")
SERVICE_NAME = "stock-generator"

resource = Resource.create({"service.name": SERVICE_NAME})

# 1. Setup Tracing
trace_provider = TracerProvider(resource=resource)
trace_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# 2. Setup Metrics
metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)


# Initial state
stocks = {
    "AAPL": {"price": 150.0, "volatility": 1.5},
    "GOOGL": {"price": 2800.0, "volatility": 5.0},
    "MSFT": {"price": 300.0, "volatility": 2.0},
    "TSLA": {"price": 800.0, "volatility": 10.0}
}

def observe_stock_price(options):
    for symbol, stock in stocks.items():
        yield metrics.Observation(stock["price"], {"symbol": symbol})

price_instrument = meter.create_observable_gauge("stock_price", callbacks=[observe_stock_price], description="Current stock price")
volume_instrument = meter.create_counter("stock_volume", description="Total shares traded")

# 3. Setup Logging
logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter(endpoint=OTLP_ENDPOINT, insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# Also set root logger to see standard prints if any
logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


def simulate_trade():
    symbol = random.choice(list(stocks.keys()))
    stock = stocks[symbol]

    with tracer.start_as_current_span("process_trade") as span:
        span.set_attribute("stock.symbol", symbol)

        # Simulate price movement
        change = random.uniform(-stock["volatility"], stock["volatility"])
        stock["price"] = max(1.0, stock["price"] + change) # Price can't be negative

        # Simulate trade volume
        shares = random.randint(10, 1000)
        action = random.choice(["BUY", "SELL"])

        span.set_attribute("trade.action", action)
        span.set_attribute("trade.shares", shares)
        span.set_attribute("trade.price", stock["price"])

        # Record Metrics
        volume_instrument.add(shares, {"symbol": symbol, "action": action})

        # Record Logs
        logger.info(f"Executed {action} order for {shares} shares of {symbol} at ${stock['price']:.2f}", extra={
            "symbol": symbol,
            "action": action,
            "shares": shares,
            "price": stock["price"]
        })

        # Simulate some processing time
        time.sleep(random.uniform(0.01, 0.1))

if __name__ == "__main__":
    logger.info("Starting stock generator...")
    try:
        while True:
            simulate_trade()
            time.sleep(random.uniform(0.5, 2.0))
    except KeyboardInterrupt:
        logger.info("Shutting down stock generator...")
