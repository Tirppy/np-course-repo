# Key-Value Store with Single-Leader ReplicationReading:

Chapter 5, Section 1 “Leaders and Followers” from “Designing Data-Intensive Applications” by Martin Kleppmann

A distributed key-value store implementing single-leader replication with semi-synchronous writes, as described in Chapter 5 of "Designing Data-Intensive Applications" by Martin Kleppmann.Implement a key-value store with single-leader replication (only the leader accepts writes, replicates them on all the followers). Both the leader and the followers should execute all requests concurrently. Run one leader and 5 followers in separate docker containers using docker-compose. Configure everything through environment variables inside the compose file. Use a web API and JSON for communication.

Leader uses semi-synchronous replication (read about it in the book), the number of confirmations from followers required for a write to be reported successful to the user ("write quorum") is configurable through an env. var. set in docker compose. 

## Lab RequirementsTo simulate network lag, on the leader side, add a delay before sending the replicate request to a follower, in the range [MIN_DELAY, MAX_DELAY], for example [0ms, 1000ms]. The replication requests to the followers should be done concurrently, so the delays will differ.

Write an integration test to check that the system works as expected.

> Reading: Chapter 5, Section 1 "Leaders and Followers" from "Designing Data-Intensive Applications" by Martin KleppmannAnalyze the system performance by making ~100 writes concurrently (10 at a time) on 10 keys:

>Plot the value of the "write quorum" (test values from 1 to 5) vs. the average latency of the write operation. Explain the results.

> Implement a key-value store with single-leader replication (only the leader accepts writes, replicates them on all the followers). Both the leader and the followers should execute all requests concurrently. Run one leader and 5 followers in separate docker containers using docker-compose. Configure everything through environment variables inside the compose file. Use a web API and JSON for communication.After all the writes are completed, check if the data in the replicas matches the data on the leader. Explain the results.

>
> Leader uses semi-synchronous replication (read about it in the book), the number of confirmations from followers required for a write to be reported successful to the user ("write quorum") is configurable through an env. var. set in docker compose.
>
> To simulate network lag, on the leader side, add a delay before sending the replicate request to a follower, in the range [MIN_DELAY, MAX_DELAY], for example [0ms, 1000ms]. The replication requests to the followers should be done concurrently, so the delays will differ.
>
> Write an integration test to check that the system works as expected.
>
> Analyze the system performance by making ~100 writes concurrently (10 at a time) on 10 keys:
> Plot the value of the "write quorum" (test values from 1 to 5) vs. the average latency of the write operation. Explain the results.
> After all the writes are completed, check if the data in the replicas matches the data on the leader. Explain the results.

---

## Architecture

```
                    ┌─────────────┐
     Client ───────►│   LEADER    │ (port 8000)
     Writes         │  (leader.py)│
                    └──────┬──────┘
                           │ Replicates with
                           │ random delay [0-1000ms]
           ┌───────┬───────┼───────┬───────┐
           ▼       ▼       ▼       ▼       ▼
     ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐
     │Follower1││Follower2││Follower3││Follower4││Follower5│
     │ :8001   ││ :8002   ││ :8003   ││ :8004   ││ :8005   │
     └─────────┘└─────────┘└─────────┘└─────────┘└─────────┘
```

## Features

- **Single-Leader Replication**: Only the leader accepts writes
- **Semi-Synchronous Replication**: Configurable write quorum (1-5)
- **Simulated Network Delay**: Random delay [0-1000ms] for replication
- **Concurrent Request Handling**: All nodes handle requests concurrently
- **Last-Write-Wins Conflict Resolution**: Uses timestamps for ordering
- **JSON REST API**: Easy to use HTTP endpoints

---

## Quick Start

### 1. Build and Start

```bash
# Build Docker images
docker-compose build

# Start all containers (1 leader + 5 followers)
docker-compose up -d
```

### 2. Verify Services are Running

```bash
docker-compose ps
```

### 3. Test the API

```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8000/health"

# Write a key-value pair
$body = @{key="mykey"; value="myvalue"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/write" -Method POST -Body $body -ContentType "application/json"

# Read the value
Invoke-RestMethod -Uri "http://localhost:8000/read/mykey"
```

### 4. Stop Services

```bash
docker-compose down
```

---

## All Commands

### Docker Commands

| Command | Description |
|---------|-------------|
| `docker-compose build` | Build all Docker images |
| `docker-compose up -d` | Start all containers in background |
| `docker-compose down` | Stop and remove all containers |
| `docker-compose restart` | Restart all containers |
| `docker-compose ps` | Show container status |
| `docker-compose logs -f` | View live logs from all containers |
| `docker-compose logs leader` | View logs from leader only |
| `docker-compose logs follower1` | View logs from follower1 only |

### Using run.bat (Windows)

| Command | Description |
|---------|-------------|
| `run.bat build` | Build Docker images |
| `run.bat start` | Start all services |
| `run.bat stop` | Stop all services |
| `run.bat restart` | Restart all services |
| `run.bat logs` | View logs |
| `run.bat test` | Run integration tests |
| `run.bat performance` | Run performance analysis |
| `run.bat status` | Show container status |
| `run.bat clean` | Remove all containers and images |

---

## API Reference

### Leader Endpoints (http://localhost:8000)

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/health` | GET | Health check & config | `GET /health` |
| `/write` | POST | Write a key-value pair | `POST /write` with `{"key":"x","value":"y"}` |
| `/read/{key}` | GET | Read a value by key | `GET /read/mykey` |
| `/keys` | GET | List all keys | `GET /keys` |
| `/all` | GET | Get all key-value pairs | `GET /all` |
| `/clear` | DELETE | Clear all data | `DELETE /clear` |

### Follower Endpoints (http://localhost:8001-8005)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/read/{key}` | GET | Read a value |
| `/all` | GET | Get all data |
| `/replicate` | POST | (Internal) Receive replication from leader |

---

## API Examples (PowerShell)

### Write Data

```powershell
$body = @{key="username"; value="john_doe"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/write" -Method POST -Body $body -ContentType "application/json"
```

**Response:**
```json
{
  "success": true,
  "key": "username",
  "value": "john_doe",
  "confirmations": 2,
  "message": "Replicated to 2/5 followers (quorum: 2)"
}
```

### Read Data from Leader

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/read/username"
```

**Response:**
```json
{
  "key": "username",
  "value": "john_doe",
  "found": true
}
```

### Read Data from Follower

```powershell
Invoke-RestMethod -Uri "http://localhost:8001/read/username"
```

### Get All Data

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/all"
```

### Clear All Data

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/clear" -Method DELETE
```

---

## API Examples (curl)

### Write Data

```bash
curl -X POST http://localhost:8000/write \
  -H "Content-Type: application/json" \
  -d '{"key":"username","value":"john_doe"}'
```

### Read Data

```bash
curl http://localhost:8000/read/username
```

### Get All Data

```bash
curl http://localhost:8000/all
```

---

## Testing

### Run Integration Tests

```bash
# Using pytest directly
pytest test_integration.py -v

# Or using run.bat
run.bat test
```

### Run Performance Analysis

```bash
# Full analysis (quorums 1-5)
python performance_analysis.py

# Quick analysis (quorums 1, 3, 5)
python performance_analysis.py --quick

# Or using run.bat
run.bat performance
```

The performance analysis will:
1. Test write latency for each quorum value (1-5)
2. Generate a plot: `latency_vs_quorum.png`
3. Check data consistency across all replicas
4. Print detailed analysis and recommendations

---

## Configuration

Environment variables in `docker-compose.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `WRITE_QUORUM` | 2 | Number of follower confirmations required |
| `MIN_DELAY` | 0 | Minimum replication delay (ms) |
| `MAX_DELAY` | 1000 | Maximum replication delay (ms) |
| `FOLLOWER_HOSTS` | follower1:8000,... | Comma-separated follower addresses |

### Change Write Quorum

Edit `docker-compose.yml`:
```yaml
leader:
  environment:
    - WRITE_QUORUM=3  # Change this value (1-5)
```

Then restart:
```bash
docker-compose restart leader
```

---

## Service Ports

| Service | Internal Port | External Port | URL |
|---------|---------------|---------------|-----|
| Leader | 8000 | 8000 | http://localhost:8000 |
| Follower 1 | 8000 | 8001 | http://localhost:8001 |
| Follower 2 | 8000 | 8002 | http://localhost:8002 |
| Follower 3 | 8000 | 8003 | http://localhost:8003 |
| Follower 4 | 8000 | 8004 | http://localhost:8004 |
| Follower 5 | 8000 | 8005 | http://localhost:8005 |

---

## How It Works

### Semi-Synchronous Replication

1. Client sends a write request to the **leader**
2. Leader stores the data locally with a timestamp
3. Leader sends replication requests to **all 5 followers concurrently**
4. Each replication has a random delay (0-1000ms) to simulate network latency
5. Leader waits for **WRITE_QUORUM** confirmations
6. Once quorum is met, leader returns success to client
7. Remaining replications continue asynchronously

### Write Quorum Trade-offs

| Quorum | Latency | Durability | Consistency |
|--------|---------|------------|-------------|
| 1 | Lowest | Lowest | Weakest |
| 2 | Low | Medium | Medium |
| 3 | Medium | Good | Good |
| 4 | High | High | High |
| 5 | Highest | Maximum | Strongest |

### Conflict Resolution

Uses **Last-Write-Wins (LWW)** based on timestamps:
- Each write gets a timestamp from the leader
- If a newer write arrives, it overwrites the old value
- If an older write arrives (out of order), it's ignored

---

## Project Structure

```
lab4-replication-concurrency-playground/
├── leader.py              # Leader node implementation
├── follower.py            # Follower node implementation
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile             # Container build instructions
├── requirements.txt       # Python dependencies
├── test_integration.py    # Integration tests
├── performance_analysis.py # Performance analysis script
├── pytest.ini             # Pytest configuration
├── run.bat                # Windows helper script
├── README.md              # This file
└── latency_vs_quorum.png  # Generated performance plot
```

---

## Troubleshooting

### Containers not starting
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Check container logs
```bash
docker-compose logs leader
docker-compose logs follower1
```

### Reset everything
```bash
docker-compose down -v
docker-compose build
docker-compose up -d
```

### Port already in use
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID)
taskkill /PID <PID> /F
```
