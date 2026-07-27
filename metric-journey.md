Here is the end-to-end journey of a single `stock_price` metric reading—from its conception in Python memory to its immortalization in time-series storage:

---

### Phase 1: Conception & Birth (Instrument & In-Memory State)
1. **The Registry is Created**: When the `stock-generator` Kubernetes pod boots up, it initializes an in-memory dictionary called `stocks` ([generator.py:L51-L58](repo/sre-lgtm/app/generator.py#L51-L58)). Each stock ticker starts with a base price (e.g., `AAPL` starts at `$150.0`).
2. **The Instrument is Born**: On [generator.py:L87](repo/sre-lgtm/app/generator.py#L87), the OpenTelemetry SDK creates the instrument:
   ```python
   price_instrument = meter.create_observable_gauge("stock_price", callbacks=[observe_stock_price], description="Current stock price")
   ```
   Unlike a standard `Counter` where the application actively pushes data via `.add()` every time an event happens, an **Observable Gauge** is passive. It sits waiting for its scheduled check-up.
3. **The 5-Second Pulse**: Its heartbeat is defined by the `PeriodicExportingMetricReader` on [generator.py:L45](repo/sre-lgtm/app/generator.py#L45), which is programmed with an `export_interval_millis=5000` (5 seconds).

---

### Phase 2: Life in the Fast Lane (State Mutation)
Between collection pulses, the application runs an asynchronous background task called `market_trading_loop()` ([generator.py:L219](repo/sre-lgtm/app/generator.py#L219)).
* As simulated trades execute in `execute_stock_trade()`, the underlying price in memory is constantly mutating:
  ```python
  change = random.uniform(-stock["volatility"], stock["volatility"])
  stock["price"] = max(1.0, stock["price"] + change)
  ```
* In `busy` mode, this happens 25 times every 100 milliseconds! During these 5 seconds between exports, the `price_instrument` gauge ignores all intermediate fluctuations—it only cares about capturing a clean snapshot when the timer fires.

---

### Phase 3: The Awakening (The Collection Pulse)
Exactly 5,000 milliseconds after the last cycle, the `PeriodicExportingMetricReader` wakes up and initiates a collection sweep across all instruments.
1. It invokes our registered callback function: `observe_stock_price(options)` ([generator.py:L67-L69](repo/sre-lgtm/app/generator.py#L67-L69)).
2. The callback iterates through the current dictionary and yields 6 fresh observation objects—one for each ticker symbol:
   ```python
   yield metrics.Observation(stock["price"], {"symbol": symbol})
   ```
3. At this exact microsecond, our specific metric reading (for example, `AAPL` at `$151.24`) is officially born as a discrete data point paired with a timestamp and the label `{symbol="AAPL"}`.

---

### Phase 4: The Departure (OTLP Export over gRPC)
1. The SDK's `OTLPMetricExporter` ([generator.py:L44](repo/sre-lgtm/app/generator.py#L44)) takes this newly minted observation, serializes it into an OpenTelemetry Protocol (OTLP) protobuf payload, and transmits it over a gRPC connection to the endpoint `0.0.0.0:4317`.
2. The packet leaves the Python pod and travels across the Docker/Kubernetes virtual network to the **OpenTelemetry Collector** container.

---

### Phase 5: The Transit Hub (The OpenTelemetry Collector)
1. The Collector receives the payload via its `otlp` gRPC receiver ([config/otel-collector.yaml:L2-5](reposre-lgtm/config/otel-collector.yaml#L2-L5)).
2. It enters the `metrics` pipeline ([config/otel-collector.yaml:L34-37](reposre-lgtm/config/otel-collector.yaml#L34-L37)), where it passes through a `batch` processor to be grouped with other telemetry for efficiency.
3. The Collector hands our reading to the `otlphttp/mimir` exporter, which fires an HTTP POST request to `http://mimir:9009/otlp` with the multi-tenant header `X-Scope-OrgID: "anonymous"`.

---

### Phase 6: Immortality vs. Replacement (Storage in Mimir)
*Does our metric reading die or get replaced when the next 5-second reading arrives?* 
**Neither! In time-series observability, an individual metric reading is immortalized as an immutable historical data point.**

* When **Grafana Mimir** ingests our reading (`stock_price{symbol="AAPL"} = 151.24 @ t=10:00:00`), it appends this exact timestamp-value pair to a time-series chunk in long-term database storage.
* 5 seconds later (`t=10:00:05`), when a new price reading arrives (`$150.89`), **it does not overwrite or kill our previous reading**. Instead, it sits right next to it along the time axis.
* What *does* get "replaced" is the **instantaneous in-memory state** (`stock["price"]` in Python) and the "Current Value" displayed on live Grafana stat panels. But in storage, our reading lives on as part of the stock's price history until Mimir's data retention policies eventually prune or compact old data blocks weeks or months later.

---

### Phase 7: The Visualization (Grafana)
When you open the Grafana dashboard ([stocks.json](reposre-lgtm/config/grafana/provisioning/dashboards/stocks.json)), Grafana sends a PromQL query (`stock_price`) to Mimir. Mimir returns the stream of immortalized timestamps and values, and Grafana plots our specific reading as a vertex on the chart—connecting it to its ancestors and successors to visualize the market trend!