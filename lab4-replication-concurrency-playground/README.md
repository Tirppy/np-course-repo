Reading:
Chapter 5, Section 1 “Leaders and Followers” from “Designing Data-Intensive Applications” by Martin Kleppmann
Implement a key-value store with single-leader replication (only the leader accepts writes, replicates them on all the followers). Both the leader and the followers should execute all requests concurrently. Run one leader and 5 followers in separate docker containers using docker-compose. Configure everything through environment variables inside the compose file. Use a web API and JSON for communication.
Leader uses semi-synchronous replication (read about it in the book), the number of confirmations from followers required for a write to be reported successful to the user ("write quorum") is configurable through an env. var. set in docker compose. 
To simulate network lag, on the leader side, add a delay before sending the replicate request to a follower, in the range [MIN_DELAY, MAX_DELAY], for example [0ms, 1000ms]. The replication requests to the followers should be done concurrently, so the delays will differ.
Write an integration test to check that the system works as expected.
Analyze the system performance by making ~100 writes concurrently (10 at a time) on 10 keys:
Plot the value of the "write quorum" (test values from 1 to 5) vs. the average latency of the write operation. Explain the results.
After all the writes are completed, check if the data in the replicas matches the data on the leader. Explain the results.
