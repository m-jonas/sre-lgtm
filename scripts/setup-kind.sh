#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building stock-generator Docker image..."
cd "$ROOT_DIR/app" && docker build -t stock-generator:latest .

echo "Creating Kind cluster..."
if ! kind get clusters | grep -q "^kind$"; then
  kind create cluster --config "$ROOT_DIR/k8s/kind-config.yaml"
else
  echo "Kind cluster already exists."
fi

echo "Loading image into Kind..."
kind load docker-image stock-generator:latest

echo "Getting Docker bridge IP for OTLP connectivity..."
HOST_IP=$(docker network inspect kind -f '{{(index .IPAM.Config 0).Gateway}}')
echo "Host IP from Kind is $HOST_IP"

echo "Creating ConfigMap with OTLP Endpoint..."
kubectl create configmap otel-config --from-literal=OTLP_ENDPOINT="http://${HOST_IP}:4317" --dry-run=client -o yaml | kubectl apply -f -

echo "Installing Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
echo "Patching Metrics Server for insecure TLS..."
kubectl patch -n kube-system deployment metrics-server --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

echo "Applying Kubernetes manifests..."
kubectl apply -f "$ROOT_DIR/k8s/deployment.yaml"
kubectl apply -f "$ROOT_DIR/k8s/service.yaml"
kubectl apply -f "$ROOT_DIR/k8s/hpa.yaml"

echo "Waiting for pods to be ready..."
kubectl rollout status deployment/stock-generator

echo "Setup complete! The generator is available at http://localhost:8000/health"
