import time
import random
import logging
import math
import asyncio
import psutil
import os
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
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Configuration
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://otel-collector:4317")
SERVICE_NAME = "stock-generator"
POD_NAME = os.getenv("HOSTNAME", "local-pod")
MARKET_MODE = os.getenv("MARKET_MODE", "quiet")  # 'quiet' or 'busy'

resource = Resource.create({"service.name": SERVICE_NAME, "k8s.pod.name": POD_NAME})

# Initialize psutil process CPU monitoring
process = psutil.Process(os.getpid())
_ = process.cpu_percent()

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

# Expanded stock market registry with order books and price history
stocks = {
    "AAPL": {"price": 150.0, "volatility": 1.5, "history": [150.0] * 50, "orders": []},
    "GOOGL": {"price": 2800.0, "volatility": 5.0, "history": [2800.0] * 50, "orders": []},
    "MSFT": {"price": 300.0, "volatility": 2.0, "history": [300.0] * 50, "orders": []},
    "TSLA": {"price": 800.0, "volatility": 10.0, "history": [800.0] * 50, "orders": []},
    "NVDA": {"price": 450.0, "volatility": 8.0, "history": [450.0] * 50, "orders": []},
    "AMZN": {"price": 130.0, "volatility": 2.5, "history": [130.0] * 50, "orders": []},
}

# Pre-populate simulated limit order book for depth analysis
for symbol, s in stocks.items():
    for _ in range(100):
        price_offset = random.uniform(-15.0, 15.0)
        s["orders"].append({"price": max(1.0, s["price"] + price_offset), "shares": random.randint(10, 500)})


def observe_stock_price(options):
    for symbol, stock in stocks.items():
        yield metrics.Observation(stock["price"], {"symbol": symbol})


def observe_pod_cpu(options):
    # Pod CPU Utilization percentage
    cpu_pct = process.cpu_percent()
    return [metrics.Observation(cpu_pct, {"pod": POD_NAME, "service": SERVICE_NAME})]


def observe_pod_memory(options):
    mem_mb = process.memory_info().rss / (1024 * 1024)
    return [metrics.Observation(mem_mb, {"pod": POD_NAME, "service": SERVICE_NAME})]


def observe_active_replicas(options):
    return [metrics.Observation(1, {"pod": POD_NAME, "service": SERVICE_NAME})]


price_instrument = meter.create_observable_gauge("stock_price", callbacks=[observe_stock_price], description="Current stock price")
volume_instrument = meter.create_counter("stock_volume", description="Total shares traded")
cpu_instrument = meter.create_observable_gauge("pod_cpu_utilization", callbacks=[observe_pod_cpu], description="Pod CPU Utilization (%)")
mem_instrument = meter.create_observable_gauge("pod_memory_usage_mb", callbacks=[observe_pod_memory], description="Pod Memory Usage (MB)")
replicas_instrument = meter.create_observable_gauge("pod_active_replicas", callbacks=[observe_active_replicas], description="Active Pod Status")

# 3. Setup Logging
logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter(endpoint=OTLP_ENDPOINT, insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
set_logger_provider(logger_provider)

handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(logging.INFO)


# Authentic Stock Metadata & Pricing Algorithms
def process_order_book(stock, current_price):
    """Simulate matching trades against limit order book depth and calculating execution slippage."""
    matched = 0
    slippage = 0.0
    for order in stock["orders"]:
        if abs(order["price"] - current_price) < 5.0:
            matched += order["shares"]
            slippage += abs(order["price"] - current_price) * 0.01
    return matched, slippage


def calculate_bollinger_bands(history, window=20):
    """Calculate moving averages and volatility Bollinger Bands across stock price history."""
    if len(history) < window:
        window = len(history)
    recent = history[-window:]
    mean = sum(recent) / window
    variance = sum((x - mean) ** 2 for x in recent) / window
    std_dev = math.sqrt(variance) if variance > 0 else 0.001
    upper_band = mean + (2 * std_dev)
    lower_band = mean - (2 * std_dev)
    return mean, std_dev, upper_band, lower_band


def evaluate_option_greeks(price, volatility, time_to_maturity=0.25, risk_free_rate=0.05):
    """Run Black-Scholes derivative pricing models to evaluate Greeks (delta, gamma) on stock option metadata."""
    strikes = [price * 0.9, price * 0.95, price, price * 1.05, price * 1.1]
    greeks_summary = 0.0
    for K in strikes:
        d1 = (math.log(price / K) + (risk_free_rate + 0.5 * (volatility ** 2)) * time_to_maturity) / (volatility * math.sqrt(time_to_maturity) + 1e-5)
        d2 = d1 - volatility * math.sqrt(time_to_maturity)
        
        cdf_d1 = 0.5 * (1.0 + math.erf(d1 / math.sqrt(2.0)))
        cdf_d2 = 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))
        
        call_price = price * cdf_d1 - K * math.exp(-risk_free_rate * time_to_maturity) * cdf_d2
        delta = cdf_d1
        gamma = math.exp(-0.5 * (d1 ** 2)) / (price * volatility * math.sqrt(2 * math.pi * time_to_maturity) + 1e-5)
        greeks_summary += (call_price + delta + gamma)
    return greeks_summary


app = FastAPI(title="Autonomous Stock Market Engine")
FastAPIInstrumentor.instrument_app(app)


class ModeRequest(BaseModel):
    mode: str


class TradeRequest(BaseModel):
    symbol: str = None
    shares: int = None
    action: str = None


def execute_stock_trade(symbol: str = None, shares: int = None, action: str = None, intensity: int = 1):
    if not symbol or symbol not in stocks:
        symbol = random.choice(list(stocks.keys()))
    stock = stocks[symbol]

    with tracer.start_as_current_span("process_trade") as span:
        span.set_attribute("stock.symbol", symbol)
        span.set_attribute("market.mode", MARKET_MODE)

        # Simulate stock price movement and update price history
        change = random.uniform(-stock["volatility"], stock["volatility"])
        stock["price"] = max(1.0, stock["price"] + change)
        stock["history"].append(stock["price"])
        if len(stock["history"]) > 200:
            stock["history"].pop(0)

        if not shares:
            shares = random.randint(10, 1000)
        if not action:
            action = random.choice(["BUY", "SELL"])

        span.set_attribute("trade.action", action)
        span.set_attribute("trade.shares", shares)
        span.set_attribute("trade.price", stock["price"])

        # Authentic Stock Metadata Processing (Driving Hardware Resource Spikes)
        matched, slippage = process_order_book(stock, stock["price"])
        mean, std_dev, upper, lower = calculate_bollinger_bands(stock["history"])

        # In busy market mode, derivative pricing intensity increases with volume, authentically spiking CPU
        for _ in range(intensity):
            _ = evaluate_option_greeks(stock["price"], stock["volatility"])

        span.set_attribute("metadata.bollinger_upper", upper)
        span.set_attribute("metadata.bollinger_lower", lower)
        span.set_attribute("metadata.order_book_slippage", slippage)

        # Record Metrics
        volume_instrument.add(shares, {"symbol": symbol, "action": action, "pod": POD_NAME})

        # Record Logs
        logger.info(
            f"Executed {action} order for {shares} shares of {symbol} at ${stock['price']:.2f} | Bollinger: [{lower:.2f}, {upper:.2f}]",
            extra={
                "symbol": symbol,
                "action": action,
                "shares": shares,
                "price": stock["price"],
                "market_mode": MARKET_MODE,
                "pod": POD_NAME
            }
        )


async def market_trading_loop():
    global MARKET_MODE
    logger.info(f"Starting autonomous market engine in '{MARKET_MODE}' mode on pod '{POD_NAME}'...")
    while True:
        try:
            if MARKET_MODE == "busy":
                # High volume trading surge: 25 trades per batch with intensive derivative metadata evaluation
                for _ in range(25):
                    execute_stock_trade(intensity=200)
                await asyncio.sleep(0.1)
            else:
                # Quiet trading day: 1 trade per batch with standard metadata evaluation
                execute_stock_trade(intensity=5)
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Error in trading loop: {e}")
            await asyncio.sleep(1)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(market_trading_loop())


@app.post("/market/mode")
async def set_market_mode(request: ModeRequest):
    global MARKET_MODE
    if request.mode not in ["quiet", "busy"]:
        raise HTTPException(status_code=400, detail="Mode must be 'quiet' or 'busy'")
    MARKET_MODE = request.mode
    logger.info(f"Market mode dynamically updated to: {MARKET_MODE} on pod {POD_NAME}")
    return {"status": "success", "mode": MARKET_MODE, "pod": POD_NAME}


@app.get("/market/mode")
async def get_market_mode():
    return {"mode": MARKET_MODE, "pod": POD_NAME, "cpu_percent": process.cpu_percent()}


@app.post("/ingest")
async def ingest_trade(request: TradeRequest):
    execute_stock_trade(request.symbol, request.shares, request.action, intensity=10)
    return {"status": "success", "message": "Trade processed"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": MARKET_MODE, "pod": POD_NAME}
