"""
Leader node for single-leader replication key-value store.
Implements semi-synchronous replication with configurable write quorum.
"""

import os
import random
import asyncio
import logging
from typing import Dict, List, Optional
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

async def replicate_to_follower(client: httpx.AsyncClient, follower_host: str, key: str, value: str, timestamp: float) -> bool:
    """
    Replicate a write to a single follower with simulated network delay.
    Returns True if replication was successful.
    """
    # Simulate network delay
    delay = random.randint(MIN_DELAY, MAX_DELAY) / 1000.0  # Convert to seconds
    await asyncio.sleep(delay)
    
    try:
        response = await client.post(
            f"http://{follower_host}/replicate",
            json={"key": key, "value": value, "timestamp": timestamp},
            timeout=10.0
        )
        if response.status_code == 200:
            logger.info(f"Successfully replicated to {follower_host} (delay: {delay*1000:.0f}ms)")
            return True
        else:
            logger.warning(f"Failed to replicate to {follower_host}: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error replicating to {follower_host}: {e}")
        return False

async def replicate_to_followers(key: str, value: str, timestamp: float, quorum: int) -> int:
    """
    Replicate a write to all followers concurrently.
    Uses semi-synchronous replication - waits for quorum confirmations.
    Returns the number of successful confirmations.
    """
    async with httpx.AsyncClient() as client:
        # Create tasks for all followers
        tasks = [
            replicate_to_follower(client, host, key, value, timestamp)
            for host in FOLLOWER_HOSTS
        ]
        
        # For semi-synchronous replication, we wait for quorum confirmations
        # but also allow remaining replications to complete asynchronously
        confirmations = 0
        completed_tasks = []
        pending_tasks = set(asyncio.create_task(t) for t in tasks)
        
        # Wait for quorum or all tasks to complete
        while pending_tasks and confirmations < quorum:
            done, pending_tasks = await asyncio.wait(
                pending_tasks,
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                try:
                    result = task.result()
                    if result:
                        confirmations += 1
                except Exception as e:
                    logger.error(f"Task failed: {e}")
        
        # Let remaining tasks complete in background (fire and forget for async part)
        if pending_tasks:
            async def complete_remaining():
                nonlocal confirmations
                for task in asyncio.as_completed(pending_tasks):
                    try:
                        result = await task
                        if result:
                            confirmations += 1
                    except Exception:
                        pass
            
            # Schedule remaining tasks but don't wait
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
