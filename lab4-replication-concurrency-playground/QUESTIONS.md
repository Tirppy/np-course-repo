# Lab 4: True/False Questions

## Theoretical Questions (Concepts from Kleppmann)

### Single-Leader Replication

1. **In single-leader replication, any node can accept write requests.**
   - [ ] True
   - [x] False
   - *Explanation: Only the leader accepts writes; followers receive replicated data.*

2. **Single-leader replication eliminates write conflicts because all writes are ordered by the leader.**
   - [x] True
   - [ ] False
   - *Explanation: Since all writes go through one node, they are naturally serialized.*

3. **In single-leader replication, followers can serve read requests.**
   - [x] True
   - [ ] False
   - *Explanation: Followers can serve reads, though data may be slightly stale.*

4. **Single-leader replication provides strong consistency for reads from followers.**
   - [ ] True
   - [x] False
   - *Explanation: Reads from followers may return stale data due to replication lag.*

### Replication Modes

5. **Synchronous replication waits for ALL followers to confirm before responding to the client.**
   - [x] True
   - [ ] False
   - *Explanation: Synchronous = wait for all; provides highest durability but highest latency.*

6. **Asynchronous replication provides the highest durability guarantee.**
   - [ ] True
   - [x] False
   - *Explanation: Asynchronous has lowest durability - data may be lost if leader fails before replication.*

7. **Semi-synchronous replication waits for a configurable number of followers (quorum) before confirming a write.**
   - [x] True
   - [ ] False
   - *Explanation: Semi-synchronous balances latency and durability by waiting for a subset of followers.*

8. **With a write quorum of 1, the system has the same durability as synchronous replication.**
   - [ ] True
   - [x] False
   - *Explanation: Quorum=1 means only 1 follower confirms; if that follower fails, data may be lost.*

### Consistency and Conflicts

9. **Last-write-wins (LWW) conflict resolution uses timestamps to determine which value to keep.**
   - [x] True
   - [ ] False
   - *Explanation: LWW keeps the value with the highest timestamp, discarding older values.*

10. **Eventual consistency guarantees that all replicas will have identical data immediately after a write.**
    - [ ] True
    - [x] False
    - *Explanation: "Eventually" consistent means replicas converge over time, not immediately.*

11. **In a single-leader system with LWW, concurrent writes to the same key will always result in consistent data across all replicas.**
    - [x] True
    - [ ] False
    - *Explanation: Since the leader assigns timestamps, all replicas apply the same ordering.*

---

## Practical Questions (System Behavior)

### Latency and Quorum

12. **Increasing the write quorum will decrease write latency.**
    - [ ] True
    - [x] False
    - *Explanation: Higher quorum = wait for more followers = higher latency.*

13. **With 5 followers and random delays [0-1000ms], a write quorum of 1 has expected latency of approximately 167ms.**
    - [x] True
    - [ ] False
    - *Explanation: E[min of 5 uniform] = MAX_DELAY × 1/6 = 1000 × 1/6 ≈ 167ms.*

14. **With 5 followers and random delays [0-1000ms], a write quorum of 5 has expected latency of approximately 833ms.**
    - [x] True
    - [ ] False
    - *Explanation: E[max of 5 uniform] = MAX_DELAY × 5/6 = 1000 × 5/6 ≈ 833ms.*

15. **The P99 latency (99th percentile) represents the latency experienced by 99% of requests.**
    - [ ] True
    - [x] False
    - *Explanation: P99 means 99% of requests were FASTER than this value; it's the slowest 1%.*

16. **If all replicas have the same data after writes complete, the system achieved eventual consistency.**
    - [x] True
    - [ ] False
    - *Explanation: Eventual consistency means all replicas converge to the same state over time.*

### Docker and Configuration

17. **The `docker-compose restart` command reloads environment variables from docker-compose.yml.**
    - [ ] True
    - [x] False
    - *Explanation: `restart` just restarts the container; use `up -d --force-recreate` to reload env vars.*

18. **Environment variables in docker-compose.yml are passed to containers at startup.**
    - [x] True
    - [ ] False
    - *Explanation: Env vars defined in the compose file are injected into containers when they start.*

19. **In Docker Compose, containers on the same network can communicate using their service names as hostnames.**
    - [x] True
    - [ ] False
    - *Explanation: Docker's internal DNS resolves service names to container IPs.*

---

## Code Questions (Implementation Details)

### Python/FastAPI

20. **`asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)` waits for all tasks to complete.**
    - [ ] True
    - [x] False
    - *Explanation: FIRST_COMPLETED returns as soon as ANY task completes.*

21. **`asyncio.create_task()` immediately executes the coroutine.**
    - [ ] True
    - [x] False
    - *Explanation: It schedules the coroutine to run; actual execution depends on the event loop.*

22. **Using `async with httpx.AsyncClient() as client:` creates a new HTTP client for each request.**
    - [x] True
    - [ ] False
    - *Explanation: This context manager creates and closes a client each time.*

23. **A shared persistent HTTP client reduces connection overhead compared to creating a new client per request.**
    - [x] True
    - [ ] False
    - *Explanation: Persistent clients reuse connections, avoiding TCP/TLS handshake overhead.*

24. **In FastAPI, `@app.on_event("startup")` runs after the first request is received.**
    - [ ] True
    - [x] False
    - *Explanation: Startup events run when the application starts, before any requests.*

25. **`await asyncio.sleep(delay)` blocks the entire event loop for the duration.**
    - [ ] True
    - [x] False
    - *Explanation: `asyncio.sleep` yields control to the event loop, allowing other tasks to run.*

### Replication Logic

26. **In the implementation, delays are generated BEFORE creating replication tasks.**
    - [x] True
    - [ ] False
    - *Explanation: `delays = [(host, random.randint(...)) for host in FOLLOWER_HOSTS]` runs first.*

27. **The leader returns success to the client before all followers have confirmed the write.**
    - [x] True
    - [ ] False
    - *Explanation: With quorum < 5, the leader returns after quorum confirmations; remaining complete in background.*

28. **If a follower fails to receive a replication request, the leader will retry indefinitely.**
    - [ ] True
    - [x] False
    - *Explanation: The implementation doesn't retry; failed replications are logged and counted as failures.*

29. **The timestamp for conflict resolution is generated by the follower when it receives the write.**
    - [ ] True
    - [x] False
    - *Explanation: The timestamp is generated by the LEADER and sent with the replication request.*

30. **`random.randint(MIN_DELAY, MAX_DELAY)` generates a random integer including both endpoints.**
    - [x] True
    - [ ] False
    - *Explanation: `random.randint(a, b)` returns N such that a <= N <= b (inclusive).*

---

## Answer Key

| # | Answer | # | Answer | # | Answer |
|---|--------|---|--------|---|--------|
| 1 | False | 11 | True | 21 | False |
| 2 | True | 12 | False | 22 | True |
| 3 | True | 13 | True | 23 | True |
| 4 | False | 14 | True | 24 | False |
| 5 | True | 15 | False | 25 | False |
| 6 | False | 16 | True | 26 | True |
| 7 | True | 17 | False | 27 | True |
| 8 | False | 18 | True | 28 | False |
| 9 | True | 19 | True | 29 | False |
| 10 | False | 20 | False | 30 | True |

---

## Score Interpretation

- **27-30 correct**: Excellent understanding of distributed systems concepts
- **21-26 correct**: Good grasp of the material, review weak areas
- **15-20 correct**: Needs more study on replication and async programming
- **Below 15**: Review Chapter 5 of Kleppmann and the lab implementation
