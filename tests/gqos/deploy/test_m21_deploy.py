import threading
import time
import pytest
from gqos.deploy.rollout import verify_health_endpoints
from gqos.ops.health import start_health_server

def test_simulated_deploy_health_check():
    # Start a dummy health server on a background thread
    port = 8081
    start_health_server(port=port)
    
    # Allow server to bind
    time.sleep(0.1)
    
    # Run the deployment rollout check
    # We expect it to succeed since the endpoints are live
    success = verify_health_endpoints(host=f"http://localhost:{port}", timeout=2)
    
    assert success == True
    
def test_simulated_deploy_rollback():
    # Test a fake port that nothing is listening on
    # Should timeout and trigger rollback (return False)
    success = verify_health_endpoints(host="http://localhost:9999", timeout=1)
    
    assert success == False

if __name__ == "__main__":
    test_simulated_deploy_health_check()
    test_simulated_deploy_rollback()
    print("M21 Deploy Tests Passed!")
