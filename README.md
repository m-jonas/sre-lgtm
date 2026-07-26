# SRE LGTM Project

## Overview
This project is a local observability environment designed for Site Reliability Engineering (SRE) and chaos engineering practice. It deploys a complete LGTM (Loki, Grafana, Tempo, Mimir) stack using Docker Compose, along with an OpenTelemetry Collector to ingest and route telemetry data.

A custom Python application (`stock-generator`) is included to simulate financial stock data and generate mock telemetry (logs, metrics, and traces) that flows into the observability stack.

## Aims
The primary goals of this project are:
- **Observability Practice:** Provide a sandbox environment to learn and experiment with the LGTM stack.
- **Telemetry Collection:** Demonstrate how to use OpenTelemetry to collect and route logs, metrics, and traces.
- **SRE & Chaos Engineering:** Offer a foundational environment to practice incident response, monitoring, and chaos engineering techniques.
- **Custom Instrumentation:** Show how a Python application can be instrumented using the OpenTelemetry SDK to generate meaningful observability data.

## Architecture
The architecture consists of the following components, all deployed as Docker containers and connected via a custom Docker network (`lgtm`):

1.  **Application (Mock Data Generator):**
    - `stock-generator`: A Python application that simulates trading of various stocks (e.g., AAPL, GOOGL, MSFT, TSLA). It generates traces (simulating trade processing), metrics (stock prices and trading volume), and logs (trade execution details).
    - It uses the OpenTelemetry Python SDK to send this telemetry data via OTLP (OpenTelemetry Protocol) over gRPC to the OpenTelemetry Collector.

2.  **Telemetry Routing:**
    - `otel-collector`: The OpenTelemetry Collector receives OTLP data from the application and routes it to the appropriate backend systems.
        - **Traces** are exported to Tempo.
        - **Metrics** are exported to Mimir.
        - **Logs** are exported to Loki.

3.  **Observability Backends (LGTM Stack):**
    - `loki`: A horizontally-scalable, highly-available, multi-tenant log aggregation system inspired by Prometheus.
    - `tempo`: A high-volume, minimal dependency trace storage backend.
    - `mimir`: A scalable, highly available, multi-tenant, long-term storage for Prometheus metrics.
    - `grafana`: The visualization layer. It connects to Loki, Tempo, and Mimir as data sources to create dashboards and query the telemetry data. It is pre-configured with these data sources and can load custom dashboards.

## Prerequisites
To run this project, you need the following installed on your local machine:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Instructions for Use

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_name>
    ```

2.  **Start the Environment:**
    First, start the LGTM observability stack using Docker Compose:
    ```bash
    docker compose up -d
    ```
    Then, create the local Kubernetes (Kind) cluster and deploy the data ingestion application by running the setup script:
    ```bash
    ./scripts/setup-kind.sh
    ```
    *Note: The first time you run this, it may take a few minutes to download the necessary Docker images, build the `stock-generator` image, and spin up the Kind cluster.*

3.  **Access Grafana:**
    Once all containers are up and running, you can access the Grafana UI in your web browser:
    - **URL:** `http://localhost:3000`
    - **Authentication:** Anonymous login is enabled and configured with Admin privileges, so no credentials are required.

4.  **Explore the Data:**
    - **Data Sources:** Grafana is automatically provisioned with Loki, Tempo, and Mimir as data sources. You can verify this in Grafana under `Connections` > `Data sources`.
    - **Dashboards:** You can explore any pre-provisioned dashboards or create your own using the `Explore` view in Grafana to query logs (Loki), traces (Tempo), and metrics (Mimir).
    - The `stock-generator` application will continuously generate data as long as it is running.

5.  **Stop the Environment:**
    When you are completely finished, use the comprehensive teardown script to cleanly delete the Kubernetes cluster and stop the Docker Compose services without leaving any leftover networks or volumes:
    ```bash
    ./scripts/teardown.sh
    ```

## Configuration Details
- **OpenTelemetry Collector:** Configuration is located at `config/otel-collector.yaml`.
- **Grafana Data Sources:** Provisioning configuration is at `config/grafana/provisioning/datasources/datasources.yaml`.
- **Grafana Dashboards:** Dashboards can be added to `config/grafana/provisioning/dashboards/`.
- **LGTM Configurations:** Individual configurations for Loki, Tempo, and Mimir are located in the `config/` directory (`loki.yaml`, `tempo.yaml`, `mimir.yaml`).
- **Python Application:** The source code and `Dockerfile` for the `stock-generator` are in the `app/` directory.
## Chaos Engineering

This project includes a standalone chaos engineering script (`chaos_monkey.py`) that randomly targets and disrupts running services (using Docker Compose `kill` or `restart`) while generating its own OpenTelemetry telemetry.

To run the chaos monkey:

1. **Ensure the Environment is Running:**
   Make sure the LGTM stack and custom network are running before executing the script:
   ```bash
   docker compose up -d
   ```

2. **Set up a Virtual Environment:**
   It is recommended to run the script in a virtual environment to manage dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   Install the required OpenTelemetry packages from `requirements-chaos.txt`:
   ```bash
   pip install -r requirements-chaos.txt
   ```

4. **Run the Script:**
   Execute the chaos monkey script to trigger disruptions:
   ```bash
   python chaos_monkey.py
   ```

## Troubleshooting

### "operation not supported" Error on Startup
If you run `docker compose up -d --build` and encounter an error similar to this:

```
failed to create endpoint ... on network ... : failed to add the host (veth...) <=> sandbox (veth...) pair interfaces: operation not supported
```

This is often caused by kernel limitations related to the `overlay` or `overlay2` storage drivers when dealing with network namespaces (often in constrained virtualized environments like LXC or some specific Linux setups).

**Solution:**
You can resolve this by configuring Docker to use the `vfs` storage driver. This driver is less disk-space efficient because it doesn't use layered filesystems (it does full copies), but it works well in restricted environments.

1.  Create or edit the Docker daemon configuration file:
    ```bash
    echo '{ "storage-driver": "vfs" }' | sudo tee /etc/docker/daemon.json
    ```
2.  Restart the Docker service for the changes to take effect:
    ```bash
    sudo systemctl restart docker
    ```
3.  Clean up any broken network state:
    ```bash
    docker network prune -f
    ```
4.  Try spinning up the environment again:
    ```bash
    docker compose up -d --build
    ```

## Autonomous Kubernetes Market Engine & Autoscaling Walkthrough

We have re-architected the system into a unified, autonomous Kubernetes-native stock market simulation engine with authentic hardware resource spiking and fast autoscaling!

### Overview of Architectural Enhancements

1. **Unified Autonomous Market Engine (`app/generator.py`)**:
   - Eliminated the external `load_simulator.py` script and removed `stock-generator` from Docker Compose. The application runs exclusively natively inside Kubernetes (Kind).
   - The engine features an autonomous background trading loop that operates in two dynamic modes: `quiet` and `busy`.
   - **Authentic Resource Spikes**: Instead of artificial CPU spin loops, hardware CPU surges are driven by processing realistic stock metadata—including limit order book matching, volatility Bollinger Bands, and Black-Scholes derivative pricing (option Greeks delta and gamma calculations).
2. **Fast Scale-Down Autoscaling (`k8s/hpa.yaml`)**:
   - Configured the Horizontal Pod Autoscaler with an explicit 15-second stabilization window (`scaleDown.stabilizationWindowSeconds: 15`).
   - When trading volume surges on a busy day, pods scale up from 1 to 5 replicas. As soon as the market quiets, pods scale back down to 1 replica within ~15–30 seconds.
3. **Architecture-Aware Chaos Monkey (`chaos_monkey.py`)**:
   - Enhanced Chaos Monkey to target both Kubernetes pods (`kubectl delete pod --grace-period=0 --force` or rolling deployment restarts) and Docker Compose observability containers.
4. **Upgraded Grafana Dashboard**:
   - New dedicated panels in Grafana displaying real-time Pod CPU Utilization (%), Pod Memory Usage (MB), Active Pod Replicas (HPA status), Trade Volume Spikes, and Chaos Disruption Events.

---

### How to Simulate Market Days & Test Autoscaling

#### 1. Start the Environment
Ensure the LGTM observability stack and Kind cluster are running:
```bash
docker compose up -d
./scripts/setup-kind.sh
```
Your Grafana dashboard is accessible at [http://localhost:3000](http://localhost:3000) (Dashboard: **Stock Trading Overview**).

#### 2. Simulate a Quiet Trading Day
To run a quiet market (low volume, ~5% CPU utilization, 1 pod replica):
```bash
./scripts/simulate-market.sh quiet
```
Monitor the HPA status to verify stable low utilization:
```bash
kubectl get hpa -w
```

#### 3. Simulate a Busy Trading Day (Surging to 5 Pods)
To simulate a high-volume busy trading day where intensive stock derivative pricing spikes pod CPU utilization:
```bash
./scripts/simulate-market.sh busy
```
Watch in real-time as HPA detects CPU utilization > 50% and scales pod replicas from 1 to 5:
```bash
kubectl get hpa -w
```

#### 4. Observe Fast Scale-Down (5 -> 1 Pod)
Once you are done observing the busy market, return to quiet mode:
```bash
./scripts/simulate-market.sh quiet
```
Thanks to our custom HPA behavioral policy, you will observe the replicas scale straight back down from 5 to 1 within ~15–30 seconds!

#### 5. Run Chaos Monkey Resilience Testing
Test system resilience under chaotic disruptions across both Kubernetes pods and observability services:
```bash
source .venv/bin/activate
python chaos_monkey.py
```
Check the **Chaos Monkey Disruption Events** and **Active Pod Replicas** panels in Grafana to observe self-healing in action.

#### 6. Complete Teardown
When finished, clean up all clusters, networks, and containers:
```bash
./scripts/teardown.sh
```
