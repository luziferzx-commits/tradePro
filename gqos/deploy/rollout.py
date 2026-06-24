import time
import requests
import sys

def verify_health_endpoints(host: str = "http://localhost:8080", timeout: int = 10):
    """
    Simulates a deployment rollout script that verifies the health of the new container
    before routing traffic to it (similar to a Kubernetes readiness probe).
    """
    print(f"Starting rollout verification for {host}...")
    
    endpoints = ['/health', '/live', '/ready']
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        all_passed = True
        
        for ep in endpoints:
            try:
                response = requests.get(f"{host}{ep}", timeout=1)
                if response.status_code != 200:
                    print(f"[WAITING] Endpoint {ep} returned {response.status_code}")
                    all_passed = False
                    break
            except requests.exceptions.RequestException:
                print(f"[WAITING] Endpoint {ep} unreachable...")
                all_passed = False
                break
                
        if all_passed:
            print("[SUCCESS] All health checks passed! Container is ready to receive live traffic.")
            return True
            
        time.sleep(1)
        
    print("[ERROR] Health check timeout. Rollback triggered.")
    return False

if __name__ == "__main__":
    success = verify_health_endpoints()
    if not success:
        sys.exit(1)
