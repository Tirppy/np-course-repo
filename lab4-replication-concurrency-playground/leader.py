"""
Leader node for single-leader replication key-value store.
Implements semi-synchronous replication with configurable write quorum.
"""

import os
import random
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
FOLLOWER_HOSTS = os.getenv("FOLLOWER_HOSTS", "follower1:8000,follower2:8000,follower3:8000,follower4:8000,follower5:8000").split(",")
WRITE_QUORUM = int(os.getenv("WRITE_QUORUM", "2"))
MIN_DELAY = int(os.getenv("MIN_DELAY", "0"))  # milliseconds
MAX_DELAY = int(os.getenv("MAX_DELAY", "1000"))  # milliseconds
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="Leader Key-Value Store")

# In-memory key-value store with timestamps for last-write-wins
kv_store: Dict[str, tuple] = {}  # key -> (value, timestamp)
# Lock for thread-safe operations
store_lock = asyncio.Lock()

# Shared HTTP client for replication (created on startup)
http_client: Optional[httpx.AsyncClient] = None

@app.on_event("startup")
async def startup_event():
    global http_client
    # Create a persistent HTTP client with connection pooling
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info(f"Leader started with WRITE_QUORUM={WRITE_QUORUM}, delays=[{MIN_DELAY}, {MAX_DELAY}]ms")

@app.on_event("shutdown")
async def shutdown_event():
    global http_client
    if http_client:
        await http_client.aclose()

class WriteRequest(BaseModel):
    key: str
    value: str

class WriteResponse(BaseModel):
    success: bool
    key: str
    value: str
    confirmations: int
    message: str

class ReadResponse(BaseModel):
    key: str
    value: Optional[str]
    found: bool

class ReplicateRequest(BaseModel):
    key: str
    value: str
    timestamp: float

async def replicate_to_followers(key: str, value: str, timestamp: float, quorum: int) -> int:
    """
    Replicate a write to all followers concurrently.
    Uses semi-synchronous replication - waits for quorum confirmations.
    
    The key insight: we simulate network delay, then the actual HTTP call is fast.
    For proper quorum semantics, we wait for quorum tasks to fully complete
    (delay + HTTP response), which simulates waiting for follower acknowledgment.
    
    Returns the number of successful confirmations.
    """
    global http_client
    
    # Generate delays upfront for each follower
    delays = [(host, random.randint(MIN_DELAY, MAX_DELAY) / 1000.0) for host in FOLLOWER_HOSTS]
    
    async def replicate_with_delay(host: str, delay: float) -> Tuple[bool, float]:
        """Execute replication with pre-determined delay."""
        # Simulate network latency
        await asyncio.sleep(delay)
        
        # Use shared HTTP client for faster requests
        try:
            response = await http_client.post(
                f"http://{host}/replicate",
                json={"key": key, "value": value, "timestamp": timestamp}
            )
            success = response.status_code == 200
            if success:
                logger.info(f"Replicated to {host} (delay: {delay*1000:.0f}ms)")
            else:
                logger.warning(f"Failed to replicate to {host}: {response.status_code}")
            return success, delay
        except Exception as e:
            logger.error(f"Error replicating to {host}: {e}")
            return False, delay
    
    # Create tasks for all followers - they run truly concurrently
    tasks = [
        asyncio.create_task(replicate_with_delay(host, delay))
        for host, delay in delays
    ]
    
    # Wait for quorum confirmations using FIRST_COMPLETED
    confirmations = 0
    pending_tasks = set(tasks)
    
    while pending_tasks and confirmations < quorum:
        done, pending_tasks = await asyncio.wait(
            pending_tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            try:
                success, delay = task.result()
                if success:
                    confirmations += 1
                    logger.info(f"Confirmation {confirmations}/{quorum} (delay: {delay*1000:.0f}ms)")
            except Exception as e:
                logger.error(f"Task failed: {e}")
    
    # Let remaining tasks complete in background
    if pending_tasks:
        async def complete_remaining():
            for task in pending_tasks:
                try:
                    await task
                except Exception:
                    pass
        asyncio.create_task(complete_remaining())
    
    return confirmations

@app.post("/write", response_model=WriteResponse)
async def write(request: WriteRequest):
    """
    Write a key-value pair to the store and replicate to followers.
    Uses semi-synchronous replication with configurable write quorum.
    """
    timestamp = datetime.utcnow().timestamp()
    
    # Write to leader first with timestamp for last-write-wins
    async with store_lock:
        if request.key in kv_store:
            existing_value, existing_timestamp = kv_store[request.key]
            if timestamp > existing_timestamp:
                kv_store[request.key] = (request.value, timestamp)
        else:
            kv_store[request.key] = (request.value, timestamp)
    
    logger.info(f"Write to leader: {request.key}={request.value}")
    
    # Replicate to followers
    confirmations = await replicate_to_followers(request.key, request.value, timestamp, WRITE_QUORUM)
    
    success = confirmations >= WRITE_QUORUM
    message = f"Replicated to {confirmations}/{len(FOLLOWER_HOSTS)} followers (quorum: {WRITE_QUORUM})"
    
    if not success:
        logger.warning(f"Write quorum not met: {confirmations}/{WRITE_QUORUM}")
    
    return WriteResponse(
        success=success,
        key=request.key,
        value=request.value,
        confirmations=confirmations,
        message=message
    )

@app.get("/read/{key}", response_model=ReadResponse)
async def read(key: str):
    """
    Read a value from the store.
    """
    async with store_lock:
        if key in kv_store:
            value, _ = kv_store[key]
            return ReadResponse(key=key, value=value, found=True)
        else:
            return ReadResponse(key=key, value=None, found=False)

@app.get("/keys")
async def get_keys():
    """
    Get all keys in the store.
    """
    async with store_lock:
        return {"keys": list(kv_store.keys())}

@app.get("/all")
async def get_all():
    """
    Get all key-value pairs in the store.
    """
    async with store_lock:
        # Return only values without timestamps for comparison
        data = {k: v[0] for k, v in kv_store.items()}
        return {"data": data}

@app.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "role": "leader",
        "write_quorum": WRITE_QUORUM,
        "followers": FOLLOWER_HOSTS,
        "min_delay": MIN_DELAY,
        "max_delay": MAX_DELAY
    }

@app.delete("/clear")
async def clear():
    """
    Clear all data from the store.
    """
    async with store_lock:
        kv_store.clear()
    return {"status": "cleared"}

if __name__ == "__main__":
    logger.info(f"Starting leader on port {PORT}")
    logger.info(f"Write quorum: {WRITE_QUORUM}")
    logger.info(f"Followers: {FOLLOWER_HOSTS}")
    logger.info(f"Network delay range: [{MIN_DELAY}ms, {MAX_DELAY}ms]")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
