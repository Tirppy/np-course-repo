"""
Follower node for single-leader replication key-value store.
Receives replicated writes from the leader.
"""

import os
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
FOLLOWER_ID = os.getenv("FOLLOWER_ID", "follower")
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title=f"Follower Key-Value Store - {FOLLOWER_ID}")

# In-memory key-value store with timestamps for conflict resolution
kv_store: Dict[str, tuple] = {}  # key -> (value, timestamp)
# Lock for thread-safe operations
store_lock = asyncio.Lock()

class ReplicateRequest(BaseModel):
    key: str
    value: str
    timestamp: float

class ReplicateResponse(BaseModel):
    success: bool
    key: str
    follower_id: str
    message: str

class ReadResponse(BaseModel):
    key: str
    value: Optional[str]
    found: bool
    timestamp: Optional[float]

@app.post("/replicate", response_model=ReplicateResponse)
async def replicate(request: ReplicateRequest):
    """
    Receive a replicated write from the leader.
    Uses timestamp for conflict resolution (last-write-wins).
    """
    async with store_lock:
        # Check if we should apply this write (last-write-wins based on timestamp)
        if request.key in kv_store:
            existing_value, existing_timestamp = kv_store[request.key]
            if request.timestamp <= existing_timestamp:
                logger.info(f"[{FOLLOWER_ID}] Skipping stale write for {request.key}")
                return ReplicateResponse(
                    success=True,
                    key=request.key,
                    follower_id=FOLLOWER_ID,
                    message="Skipped stale write"
                )
        
        # Apply the write
        kv_store[request.key] = (request.value, request.timestamp)
        logger.info(f"[{FOLLOWER_ID}] Replicated: {request.key}={request.value}")
    
    return ReplicateResponse(
        success=True,
        key=request.key,
        follower_id=FOLLOWER_ID,
        message="Successfully replicated"
    )

@app.get("/read/{key}", response_model=ReadResponse)
async def read(key: str):
    """
    Read a value from the store.
    """
    async with store_lock:
        if key in kv_store:
            value, timestamp = kv_store[key]
            return ReadResponse(key=key, value=value, found=True, timestamp=timestamp)
        else:
            return ReadResponse(key=key, value=None, found=False, timestamp=None)

@app.get("/keys")
async def get_keys():
    """
    Get all keys in the store.
    """
    async with store_lock:
        return {"keys": list(kv_store.keys()), "follower_id": FOLLOWER_ID}

@app.get("/all")
async def get_all():
    """
    Get all key-value pairs in the store.
    """
    async with store_lock:
        # Return only values without timestamps for comparison
        data = {k: v[0] for k, v in kv_store.items()}
        return {"data": data, "follower_id": FOLLOWER_ID}

@app.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "role": "follower",
        "follower_id": FOLLOWER_ID,
        "keys_count": len(kv_store)
    }

@app.delete("/clear")
async def clear():
    """
    Clear all data from the store.
    """
    async with store_lock:
        kv_store.clear()
    return {"status": "cleared", "follower_id": FOLLOWER_ID}

if __name__ == "__main__":
    logger.info(f"Starting follower '{FOLLOWER_ID}' on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
