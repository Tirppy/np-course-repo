# Lab 4: Key-Value Store with Single-Leader Replication

## Overview

This lab implements a distributed key-value store based on the **single-leader replication** pattern described in Chapter 5 of "Designing Data-Intensive Applications" by Martin Kleppmann. The system demonstrates semi-synchronous replication with configurable write quorum, network delay simulation, and concurrent request handling.

---

## 1. System Architecture

### 1.1 Components

The system consists of **6 Docker containers**:
- **1 Leader Node**: Accepts all write requests and replicates to followers
- **5 Follower Nodes**: Receive replicated data from the leader, serve read requests

```
                    ┌─────────────────┐
                    │     Client      │
                    └────────┬────────┘
                             │ Write Request
                             ▼
                    ┌─────────────────┐
                    │     Leader      │
                    │   (Port 8000)   │
                    └────────┬────────┘
                             │ Replication (with simulated delay)
         ┌───────────┬───────┼────────────┬───────────┐
         ▼           ▼       ▼            ▼           ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
  │Follower1│ │Follower2│ │Follower3│ │Follower4│ │Follower5│
  │  :8001  │ │  :8002  │ │  :8003  │ │  :8004  │ │  :8005  │
  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

[IMAGE: Architecture diagram showing leader-follower topology with ports]

### 1.2 Technology Stack

- **Language**: Python 3.11
- **Web Framework**: FastAPI with Uvicorn (async support)
- **HTTP Client**: httpx (async HTTP requests)
- **Containerization**: Docker + Docker Compose
- **Communication**: REST API with JSON payloads

---

## 2. Single-Leader Replication

### 2.1 Concept (from Kleppmann)

In single-leader replication:
1. **One replica is designated as the leader** - all writes must go through it
2. **Other replicas are followers** - they receive a replication stream from the leader
3. **Reads can be served by any replica** (with potential staleness)

This ensures **no write conflicts** since all writes are ordered by the single leader.

### 2.2 Implementation

**Leader Node (`leader.py`)**:
- Accepts write requests via `POST /write`
- Stores data locally with timestamps
- Replicates to all followers concurrently
- Waits for write quorum before responding to client

**Follower Node (`follower.py`)**:
- Receives replicated writes via `POST /replicate`
- Stores data with last-write-wins conflict resolution
- Serves read requests via `GET /read/{key}`

---

## 3. Semi-Synchronous Replication

### 3.1 Concept (from Kleppmann)

Kleppmann describes three replication modes:

| Mode | Description | Trade-off |
|------|-------------|-----------|
| **Synchronous** | Wait for ALL followers | High durability, high latency |
| **Asynchronous** | Don't wait for any follower | Low latency, risk of data loss |
| **Semi-synchronous** | Wait for SOME followers (quorum) | Balanced trade-off |

### 3.2 Implementation

The leader implements **semi-synchronous replication** with a configurable **write quorum**:

```python
# Wait for quorum confirmations using FIRST_COMPLETED
while pending_tasks and confirmations < quorum:
    done, pending_tasks = await asyncio.wait(
        pending_tasks,
        return_when=asyncio.FIRST_COMPLETED
    )
    for task in done:
        success, delay = task.result()
        if success:
            confirmations += 1
```

- **WRITE_QUORUM=1**: Return after 1 follower confirms (fastest, least durable)
- **WRITE_QUORUM=5**: Return after all 5 followers confirm (slowest, most durable)

---

## 4. Configuration via Environment Variables

All configuration is done through `docker-compose.yml`:

```yaml
environment:
  - FOLLOWER_HOSTS=follower1:8000,follower2:8000,...
  - WRITE_QUORUM=3        # Number of confirmations required
  - MIN_DELAY=0           # Minimum network delay (ms)
  - MAX_DELAY=1000        # Maximum network delay (ms)
  - PORT=8000
```

| Variable | Description | Default |
|----------|-------------|---------|
| `WRITE_QUORUM` | Followers needed to confirm write | 2 |
| `MIN_DELAY` | Minimum simulated network delay | 0ms |
| `MAX_DELAY` | Maximum simulated network delay | 1000ms |
| `FOLLOWER_HOSTS` | Comma-separated list of follower addresses | - |

---

## 5. Network Delay Simulation

### 5.1 Implementation

To simulate real-world network conditions, a random delay is added **before** sending each replication request:

```python
async def replicate_with_delay(host: str, delay: float):
    # Simulate network latency (different for each follower)
    await asyncio.sleep(delay)
    
    # Send actual replication request
    response = await http_client.post(
        f"http://{host}/replicate",
        json={"key": key, "value": value, "timestamp": timestamp}
    )
```

### 5.2 Concurrent Replication

All 5 replication requests are sent **concurrently** with independent random delays:

```python
# Generate independent delays for each follower
delays = [(host, random.randint(MIN_DELAY, MAX_DELAY) / 1000.0) 
          for host in FOLLOWER_HOSTS]

# Create concurrent tasks
tasks = [
    asyncio.create_task(replicate_with_delay(host, delay))
    for host, delay in delays
]
```

This means:
- Follower 1 might get delay of 100ms
- Follower 2 might get delay of 800ms
- Follower 3 might get delay of 250ms
- etc.

The leader returns when `WRITE_QUORUM` followers have confirmed.

---

## 6. Conflict Resolution: Last-Write-Wins

### 6.1 Problem

With concurrent writes to the same key, different replicas might receive updates in different orders.

### 6.2 Solution

Each write includes a **timestamp** assigned by the leader. Followers use **last-write-wins (LWW)** resolution:

```python
async def replicate(request: ReplicateRequest):
    if request.key in kv_store:
        existing_value, existing_timestamp = kv_store[request.key]
        # Only update if new timestamp is greater
        if request.timestamp > existing_timestamp:
            kv_store[request.key] = (request.value, request.timestamp)
    else:
        kv_store[request.key] = (request.value, request.timestamp)
```

This ensures **eventual consistency** - all replicas converge to the same state.

---

## 7. API Endpoints

### Leader API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/write` | POST | Write a key-value pair |
| `/read/{key}` | GET | Read a value by key |
| `/keys` | GET | List all keys |
| `/health` | GET | Health check |
| `/clear` | DELETE | Clear all data |

### Follower API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/replicate` | POST | Receive replicated write from leader |
| `/read/{key}` | GET | Read a value by key |
| `/keys` | GET | List all keys |
| `/health` | GET | Health check |

### Example Request/Response

**Write Request:**
```bash
curl -X POST http://localhost:8000/write \
  -H "Content-Type: application/json" \
  -d '{"key": "user:1", "value": "Alice"}'
```

**Response:**
```json
{
  "success": true,
  "key": "user:1",
  "value": "Alice",
  "confirmations": 3,
  "message": "Replicated to 3/5 followers (quorum: 3)"
}
```

---

## 8. Integration Tests

### 8.1 Test Cases

The integration test suite (`test_integration.py`) covers:

1. **Basic Write/Read**: Write to leader, read from leader
2. **Replication**: Write to leader, verify data appears on followers
3. **Multi-key Operations**: Write multiple keys, verify all replicated
4. **Concurrent Writes**: Multiple simultaneous writes to same key
5. **Quorum Behavior**: Verify confirmations match quorum setting
6. **Last-Write-Wins**: Verify latest timestamp wins on conflicts
7. **Read from Followers**: Verify followers serve correct data
8. **Data Consistency**: Leader and all followers have identical data

### 8.2 Running Tests

```bash
# Start the containers
docker-compose up -d

# Run integration tests
python -m pytest test_integration.py -v
```

### 8.3 Test Results

[IMAGE: Screenshot of pytest output showing all 9 tests passing]

```
test_integration.py::test_health_check PASSED
test_integration.py::test_write_and_read PASSED
test_integration.py::test_replication_to_followers PASSED
test_integration.py::test_multiple_keys PASSED
test_integration.py::test_concurrent_writes PASSED
test_integration.py::test_write_quorum PASSED
test_integration.py::test_last_write_wins PASSED
test_integration.py::test_read_from_followers PASSED
test_integration.py::test_data_consistency PASSED

9 passed in 12.34s
```

---

## 9. Performance Analysis

### 9.1 Test Setup

- **Total writes**: 100 (10 keys × 10 writes each)
- **Execution**: Sequential writes to properly measure quorum effect
- **Network delay**: Random uniform distribution [0ms, 1000ms]
- **Quorum values tested**: 1, 2, 3, 4, 5

### 9.2 Write Quorum vs. Latency

[IMAGE: Plot showing latency_vs_quorum.png - X-axis: Quorum (1-5), Y-axis: Latency (0-1.0s), 4 lines for Mean/Median/P95/P99]

#### Results Table

| Quorum | Mean | Median | P95 | P99 |
|--------|------|--------|-----|-----|
| 1 | 0.188s | 0.160s | 0.505s | 0.598s |
| 2 | 0.349s | 0.319s | 0.727s | 0.821s |
| 3 | 0.490s | 0.507s | 0.794s | 0.871s |
| 4 | 0.702s | 0.711s | 0.916s | 0.977s |
| 5 | 0.839s | 0.882s | 0.996s | 1.001s |

### 9.3 Explanation of Results

#### Why Latency Increases with Quorum

The latency follows the **order statistics** of uniform random variables:

With 5 followers, each getting a random delay from uniform[0, 1000ms]:

| Quorum | Waits for | Expected Latency | Formula |
|--------|-----------|------------------|---------|
| 1 | Fastest (min) | ~167ms | 1000 × 1/6 |
| 2 | 2nd fastest | ~333ms | 1000 × 2/6 |
| 3 | 3rd fastest (median) | ~500ms | 1000 × 3/6 |
| 4 | 4th fastest | ~667ms | 1000 × 4/6 |
| 5 | Slowest (max) | ~833ms | 1000 × 5/6 |

**Mathematical Explanation:**

For n uniform random variables on [0, 1], the expected value of the k-th order statistic is:

$$E[X_{(k)}] = \frac{k}{n+1}$$

With n=5 followers and MAX_DELAY=1000ms:
- Quorum 1 (k=1): $E = \frac{1}{6} \times 1000 = 167ms$
- Quorum 5 (k=5): $E = \frac{5}{6} \times 1000 = 833ms$

Our observed results closely match these theoretical values!

#### Why P95/P99 Approach 1000ms

Since MAX_DELAY=1000ms is the upper bound, the slowest possible delay is ~1000ms. At higher quorums:
- We must wait for slower followers
- The tail latencies (P95, P99) approach the maximum delay

---

## 10. Data Consistency Analysis

### 10.1 Verification Method

After all 100 writes complete, we check:
1. Number of keys on each node
2. Value match between leader and each follower
3. Identification of any mismatches

### 10.2 Results

```
Leader has 10 keys

follower1: 10 keys, 10 matching (100.0%), 0 mismatched, 0 missing
follower2: 10 keys, 10 matching (100.0%), 0 mismatched, 0 missing
follower3: 10 keys, 10 matching (100.0%), 0 mismatched, 0 missing
follower4: 10 keys, 10 matching (100.0%), 0 mismatched, 0 missing
follower5: 10 keys, 10 matching (100.0%), 0 mismatched, 0 missing

All replicas have CONSISTENT data with the leader!
```

### 10.3 Explanation

**Why is data consistent across all replicas?**

1. **Single Leader**: All writes go through one node, ensuring total ordering
2. **Timestamps**: Leader assigns monotonic timestamps to each write
3. **Last-Write-Wins**: All replicas apply the same conflict resolution rule
4. **Eventual Consistency**: Even if replication is delayed, all replicas eventually converge

**Even with:**
- Concurrent writes to the same keys
- Different network delays to each follower
- Semi-synchronous replication (not all followers confirm immediately)

...all replicas end up with **identical data** because they all apply writes in timestamp order.

---

## 11. Trade-offs Summary

| Quorum | Latency | Durability | Consistency | Use Case |
|--------|---------|------------|-------------|----------|
| 1 | Lowest (~0.2s) | Lowest | Weakest | Speed-critical, loss-tolerant |
| 2 | Low (~0.35s) | Medium | Medium | Balanced for most apps |
| 3 | Medium (~0.5s) | Good | Good | Majority quorum (recommended) |
| 4 | High (~0.7s) | High | High | Important data |
| 5 | Highest (~0.84s) | Maximum | Strongest | Critical data, sync replication |

### Recommendations

- **For speed-critical applications**: Use WRITE_QUORUM=1-2
- **For balanced approach**: Use WRITE_QUORUM=3 (majority quorum)
- **For critical data**: Use WRITE_QUORUM=4-5

---

## 12. How to Run

### Prerequisites
- Docker and Docker Compose installed
- Python 3.11+ (for running tests locally)

### Start the System

```bash
# Build and start all containers
docker-compose up -d --build

# Verify all containers are running
docker-compose ps
```

### Run Integration Tests

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest test_integration.py -v
```

### Run Performance Analysis

```bash
python performance_analysis.py
```

This will:
1. Test all quorum values (1-5)
2. Perform 100 writes for each quorum
3. Generate `latency_vs_quorum.png` plot
4. Check data consistency across replicas

### Stop the System

```bash
docker-compose down
```

---

## 13. File Structure

```
lab4-replication-concurrency-playground/
├── docker-compose.yml      # Container orchestration
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
├── leader.py               # Leader node implementation
├── follower.py             # Follower node implementation
├── test_integration.py     # Integration test suite
├── performance_analysis.py # Performance testing & plotting
├── README.md               # Quick start guide
├── REPORT.md               # This report
├── latency_vs_quorum.png   # Generated performance plot
└── run.bat                 # Windows batch script to run all
```

---

## 14. Conclusion

This lab successfully demonstrates:

1. **Single-leader replication** - All writes through leader, replicated to followers
2. **Semi-synchronous replication** - Configurable write quorum for durability/latency trade-off
3. **Concurrent request handling** - Both leader and followers handle requests concurrently
4. **Network delay simulation** - Random delays simulate real network conditions
5. **Eventual consistency** - All replicas converge to identical state using last-write-wins

The performance analysis confirms the theoretical relationship between write quorum and latency, following the order statistics of uniform random variables. Higher quorum means waiting for slower followers, increasing latency but improving durability.

---

## References

1. Kleppmann, M. (2017). *Designing Data-Intensive Applications*. O'Reilly Media. Chapter 5: Replication.
2. FastAPI Documentation: https://fastapi.tiangolo.com/
3. Docker Compose Documentation: https://docs.docker.com/compose/
