#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Deleting Kubernetes resources..."
kubectl delete -f "$ROOT_DIR/k8s/hpa.yaml" --ignore-not-found || true
kubectl delete -f "$ROOT_DIR/k8s/service.yaml" --ignore-not-found || true
kubectl delete -f "$ROOT_DIR/k8s/deployment.yaml" --ignore-not-found || true
kubectl delete configmap otel-config --ignore-not-found || true

echo "Deleting Kind cluster..."
kind delete cluster || true

echo "Cleaning up Docker images..."
docker rmi stock-generator:latest 2>/dev/null || true

# Check if Docker compose is running and tear it down completely if so
echo "Checking if Docker Compose needs teardown..."
if [ -f "$ROOT_DIR/docker-compose.yml" ]; then
    cd "$ROOT_DIR"
    docker compose down -v --remove-orphans || true
fi

echo "Pruning unused Docker volumes and networks to leave no trace..."
docker network prune -f
docker volume prune -f

echo "Teardown complete! System is clean."
