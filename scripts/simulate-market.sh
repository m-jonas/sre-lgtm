#!/bin/bash
set -e

MODE=$1

if [ -z "$MODE" ]; then
  echo "Usage: $0 <quiet|busy|status>"
  echo "  quiet  : Simulate a quiet trading day (low trade volume, low CPU, 1 pod)"
  echo "  busy   : Simulate a busy trading day (high trade volume, derivative pricing CPU surge, scales to 5 pods)"
  echo "  status : Display current market mode, HPA status, and pod replicas"
  exit 1
fi

if [ "$MODE" = "status" ]; then
  echo "=== Current Market Engine Status ==="
  curl -s http://localhost:8000/health || echo "Could not connect to localhost:8000"
  echo ""
  echo "=== HPA Status ==="
  kubectl get hpa stock-generator-hpa
  echo ""
  echo "=== Running Pods ==="
  kubectl get pods -l app=stock-generator
  exit 0
fi

if [ "$MODE" != "quiet" ] && [ "$MODE" != "busy" ]; then
  echo "Error: Mode must be 'quiet' or 'busy'."
  exit 1
fi

echo "Switching stock trading simulation to '$MODE' mode..."

# 1. Try updating active running pods instantly via API
curl -s -X POST http://localhost:8000/market/mode \
  -H "Content-Type: application/json" \
  -d "{\"mode\": \"$MODE\"}" || echo "Note: Could not reach localhost:8000 API directly, relying on Kubernetes deployment spec update."

# 2. Update Kubernetes deployment spec so current and newly scaled pods maintain this mode
kubectl set env deployment/stock-generator MARKET_MODE="$MODE"

echo ""
echo "Market successfully set to '$MODE'."
if [ "$MODE" = "busy" ]; then
  echo "Watch the CPU utilization surge and pods scale up from 1 to 5:"
  echo "  kubectl get hpa -w"
elif [ "$MODE" = "quiet" ]; then
  echo "Watch the CPU utilization drop and pods scale down to 1 within ~15-30 seconds:"
  echo "  kubectl get hpa -w"
fi
