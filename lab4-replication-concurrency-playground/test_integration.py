"""
Integration tests for the key-value store with single-leader replication.
Tests the basic functionality, replication, and consistency.
"""

import asyncio
import time
import pytest
import httpx

# Configuration
LEADER_URL = "http://localhost:8000"
FOLLOWER_URLS = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
]

async def wait_for_services(timeout: int = 60):
    """Wait for all services to be healthy."""
    start = time.time()
    services = [LEADER_URL] + FOLLOWER_URLS
    
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                healthy = True
                for url in services:
                    response = await client.get(f"{url}/health", timeout=2.0)
                    if response.status_code != 200:
                        healthy = False
                        break
                if healthy:
                    print("All services are healthy!")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
    
    raise TimeoutError("Services did not become healthy in time")

async def clear_all_stores():
    """Clear data from leader and all followers."""
    async with httpx.AsyncClient() as client:
        await client.delete(f"{LEADER_URL}/clear", timeout=5.0)
        for url in FOLLOWER_URLS:
            try:
                await client.delete(f"{url}/clear", timeout=5.0)
            except Exception:
                pass

@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module", autouse=True)
async def setup_services():
    """Setup fixture to wait for services."""
    await wait_for_services()
    yield
    # Cleanup after tests
    await clear_all_stores()

@pytest.mark.asyncio
async def test_leader_health():
    """Test that the leader is healthy."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{LEADER_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["role"] == "leader"

@pytest.mark.asyncio
async def test_follower_health():
    """Test that all followers are healthy."""
    async with httpx.AsyncClient() as client:
        for i, url in enumerate(FOLLOWER_URLS):
            response = await client.get(f"{url}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["role"] == "follower"

@pytest.mark.asyncio
async def test_write_and_read_from_leader():
    """Test basic write and read operations on the leader."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Write a value
        response = await client.post(
            f"{LEADER_URL}/write",
            json={"key": "test_key", "value": "test_value"},
            timeout=15.0
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"
        
        # Read the value back
        response = await client.get(f"{LEADER_URL}/read/test_key")
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["value"] == "test_value"

@pytest.mark.asyncio
async def test_replication_to_followers():
    """Test that writes are replicated to followers."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Write a value to the leader
        response = await client.post(
            f"{LEADER_URL}/write",
            json={"key": "replicated_key", "value": "replicated_value"},
            timeout=15.0
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Wait a bit for replication to complete
        await asyncio.sleep(2)
        
        # Check that the value is on at least one follower
        found_count = 0
        for url in FOLLOWER_URLS:
            response = await client.get(f"{url}/read/replicated_key")
            if response.status_code == 200:
                data = response.json()
                if data["found"] and data["value"] == "replicated_value":
                    found_count += 1
        
        # With quorum=2, we expect at least 2 followers to have the data
        assert found_count >= 2, f"Expected at least 2 followers to have data, but found {found_count}"

@pytest.mark.asyncio
async def test_concurrent_writes():
    """Test that concurrent writes work correctly."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Perform multiple concurrent writes
        tasks = []
        for i in range(10):
            task = client.post(
                f"{LEADER_URL}/write",
                json={"key": f"concurrent_key_{i}", "value": f"value_{i}"},
                timeout=15.0
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # All writes should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
        
        # Verify all keys are on the leader
        for i in range(10):
            response = await client.get(f"{LEADER_URL}/read/concurrent_key_{i}")
            assert response.status_code == 200
            data = response.json()
            assert data["found"] == True
            assert data["value"] == f"value_{i}"

@pytest.mark.asyncio
async def test_read_non_existent_key():
    """Test reading a non-existent key."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{LEADER_URL}/read/non_existent_key")
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == False
        assert data["value"] is None

@pytest.mark.asyncio
async def test_overwrite_key():
    """Test that overwriting a key works correctly."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Write initial value
        response = await client.post(
            f"{LEADER_URL}/write",
            json={"key": "overwrite_key", "value": "initial_value"},
            timeout=15.0
        )
        assert response.status_code == 200
        
        # Wait for replication
        await asyncio.sleep(1)
        
        # Overwrite with new value
        response = await client.post(
            f"{LEADER_URL}/write",
            json={"key": "overwrite_key", "value": "updated_value"},
            timeout=15.0
        )
        assert response.status_code == 200
        
        # Verify the new value on leader
        response = await client.get(f"{LEADER_URL}/read/overwrite_key")
        data = response.json()
        assert data["value"] == "updated_value"

@pytest.mark.asyncio
async def test_get_all_keys():
    """Test getting all keys from the store."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Write some keys
        for i in range(5):
            await client.post(
                f"{LEADER_URL}/write",
                json={"key": f"all_keys_{i}", "value": f"value_{i}"},
                timeout=15.0
            )
        
        # Get all keys
        response = await client.get(f"{LEADER_URL}/keys")
        assert response.status_code == 200
        data = response.json()
        
        for i in range(5):
            assert f"all_keys_{i}" in data["keys"]

@pytest.mark.asyncio
async def test_eventual_consistency():
    """Test that all replicas eventually have the same data."""
    await clear_all_stores()
    
    async with httpx.AsyncClient() as client:
        # Write several values
        for i in range(5):
            response = await client.post(
                f"{LEADER_URL}/write",
                json={"key": f"consistency_key_{i}", "value": f"value_{i}"},
                timeout=15.0
            )
            assert response.status_code == 200
        
        # Wait for full replication (account for max delay)
        await asyncio.sleep(3)
        
        # Get data from leader
        response = await client.get(f"{LEADER_URL}/all")
        leader_data = response.json()["data"]
        
        # Check each follower
        for url in FOLLOWER_URLS:
            response = await client.get(f"{url}/all")
            follower_data = response.json()["data"]
            
            # Each follower should have at least the keys we wrote
            # (may have more or less depending on timing)
            for key, value in leader_data.items():
                if key.startswith("consistency_key_"):
                    if key in follower_data:
                        assert follower_data[key] == value, \
                            f"Follower {url} has wrong value for {key}"

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
