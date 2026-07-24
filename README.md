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

## Kubernetes Data Ingestion Walkthrough

I have successfully completed the migration and enhancements to introduce the Kubernetes-based mock data ingestion system! Here is a summary of the new architecture and how to use it.

### Overview of Changes

1. **FastAPI Refactor**: `app/generator.py` has been completely rewritten from a script into a fast, async web server using `FastAPI`. It now listens for HTTP `POST /ingest` requests and handles the OpenTelemetry instrumentation for every incoming trade.
2. **Kubernetes Migration**: We created a full suite of Kubernetes manifests inside the `k8s/` directory.
   - **Deployment**: `k8s/deployment.yaml` strictly bounds each pod's maximum CPU usage to `200m` (1/5th of a core) and memory to `128Mi`, ensuring your laptop remains perfectly responsive even under heavy load.
   - **Service**: `k8s/service.yaml` exposes the application outside of Kind on port `8000`.
   - **HPA**: `k8s/hpa.yaml` automatically monitors CPU usage. Once utilization goes past 50%, it provisions new pods, scaling horizontally up to a maximum of 5 pods.
3. **Load Simulator**: A new script, `app/load_simulator.py`, was added so you can manually trigger traffic spikes and watch the autoscaling react in real-time.
4. **Automation Scripts**: We added `./scripts/setup-kind.sh` and `./scripts/teardown.sh` to fully automate the lifecycle of this system with zero leftover traces.

### How to Test the Setup

#### 1. Verify LGTM Stack
Your Grafana instance is running via Docker Compose at [http://localhost:3000](http://localhost:3000). The OpenTelemetry collector is successfully receiving metrics from our new Kubernetes cluster.

#### 2. Run a Quiet Market Load
You can simulate a normal, slow market by running the following command in your terminal. This sends 2 requests per second to the API:
```bash
source .venv/bin/activate
python app/load_simulator.py --mode quiet --duration 60
```
*If you run `kubectl get hpa -w` in another terminal, you'll see CPU utilization remains low (e.g., 10%) and the replicas stay at 1.*

#### 3. Trigger a Busy Market (Autoscaling)
To see the Horizontal Pod Autoscaler in action, run a busy market load. This will send 50 requests per second and instruct the API to do significantly more CPU work per request:
```bash
python app/load_simulator.py --mode busy --duration 120
```
As this runs, you can monitor the HPA:
```bash
kubectl get hpa -w
```
You will see the CPU utilization spike well past 50%, and Kubernetes will automatically spin up 4 new pods (for a total of 5) to handle the load.

#### 4. Complete Teardown
When you are completely finished with your environment, you can run the teardown script:
```bash
./scripts/teardown.sh
```
> [!TIP]
> This script is fully comprehensive. It deletes the Kind cluster, deletes all associated Docker networks, removes the unused images, and tears down the Docker Compose environment, leaving no trace on your laptop.
