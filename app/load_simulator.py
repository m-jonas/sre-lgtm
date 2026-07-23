import requests
import time
import argparse
from concurrent.futures import ThreadPoolExecutor

def send_request(url, iterations):
    try:
        response = requests.post(
            f"{url}/ingest",
            json={"cpu_spin_iterations": iterations},
            timeout=5
        )
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
    except Exception as e:
        pass # Ignore errors to keep blasting

def simulate_load(url, rps, duration, iterations):
    print(f"Starting load simulation to {url}")
    print(f"Target RPS: {rps}, Duration: {duration}s, Spin Iterations: {iterations}")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max(10, rps)) as executor:
        while time.time() - start_time < duration:
            loop_start = time.time()
            for _ in range(rps):
                executor.submit(send_request, url, iterations)
            
            # Sleep to maintain RPS
            elapsed = time.time() - loop_start
            sleep_time = max(0, 1.0 - elapsed)
            time.sleep(sleep_time)

    print("Load simulation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Generator Load Simulator")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="API URL")
    parser.add_argument("--mode", type=str, choices=["quiet", "busy"], default="quiet", help="Load mode")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    
    args = parser.parse_args()
    
    if args.mode == "quiet":
        simulate_load(args.url, rps=2, duration=args.duration, iterations=10000)
    elif args.mode == "busy":
        simulate_load(args.url, rps=50, duration=args.duration, iterations=500000)
