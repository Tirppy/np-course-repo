"""
Performance Analysis for the Key-Value Store with Single-Leader Replication.

This script:
1. Makes ~100 writes (sequentially to properly measure quorum latency) on 10 keys
2. Plots write quorum (1-5) vs latency metrics (mean, median, p95, p99)
3. Checks if replica data matches leader data
"""

import asyncio
import time
import statistics
import subprocess
import sys
import os
import httpx
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple

# Configuration
LEADER_URL = "http://localhost:8000"
FOLLOWER_URLS = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8004",
    "http://localhost:8005",
]

# Test parameters
NUM_KEYS = 10
WRITES_PER_KEY = 10  # Total writes = 100

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

async def write_single(client: httpx.AsyncClient, key: str, value: str) -> Tuple[bool, float]:
    """
    Perform a single write and return (success, latency).
    """
    start_time = time.time()
    try:
        response = await client.post(
            f"{LEADER_URL}/write",
            json={"key": key, "value": value},
            timeout=30.0
        )
        latency = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return data["success"], latency
        return False, latency
    except Exception as e:
        latency = time.time() - start_time
        print(f"Error writing {key}: {e}")
        return False, latency

async def run_performance_test(write_quorum: int) -> List[float]:
    """
    Run performance test with a specific write quorum.
    Runs writes SEQUENTIALLY to properly measure the effect of quorum on latency.
    Returns list of latencies for successful writes.
    """
    print(f"\n{'='*60}")
    print(f"Testing with WRITE_QUORUM = {write_quorum}")
    print(f"{'='*60}")
    
    # Clear stores before test
    await clear_all_stores()
    
    latencies = []
    successful_writes = 0
    failed_writes = 0
    
    # Generate all write operations
    write_operations = []
    for key_idx in range(NUM_KEYS):
        for write_idx in range(WRITES_PER_KEY):
            key = f"key_{key_idx}"
            value = f"value_{key_idx}_{write_idx}_{write_quorum}"
            write_operations.append((key, value))
    
    print(f"Total write operations: {len(write_operations)}")
    
    # Execute writes SEQUENTIALLY to properly measure individual latency
    async with httpx.AsyncClient() as client:
        for idx, (key, value) in enumerate(write_operations):
            success, latency = await write_single(client, key, value)
            if success:
                successful_writes += 1
                latencies.append(latency)
            else:
                failed_writes += 1
            
            # Progress indicator every 20 writes
            if (idx + 1) % 20 == 0:
                print(f"  Progress: {idx + 1}/{len(write_operations)} writes completed")
    
    print(f"Successful writes: {successful_writes}")
    print(f"Failed writes: {failed_writes}")
    if latencies:
        print(f"Average latency: {statistics.mean(latencies)*1000:.2f} ms")
        print(f"Min latency: {min(latencies)*1000:.2f} ms")
        print(f"Max latency: {max(latencies)*1000:.2f} ms")
    
    return latencies

async def check_data_consistency() -> Dict[str, any]:
    """
    Check if the data in replicas matches the data on the leader.
    Returns a dictionary with consistency analysis.
    """
    print("\n" + "="*60)
    print("Checking Data Consistency")
    print("="*60)
    
    # Wait for async replication to complete
    print("Waiting for async replication to complete...")
    await asyncio.sleep(3)
    
    async with httpx.AsyncClient() as client:
        # Get leader data
        response = await client.get(f"{LEADER_URL}/all")
        leader_data = response.json()["data"]
        
        print(f"\nLeader has {len(leader_data)} keys")
        
        consistency_results = {
            "leader_keys": len(leader_data),
            "followers": {}
        }
        
        # Compare with each follower
        for i, url in enumerate(FOLLOWER_URLS):
            follower_name = f"follower{i+1}"
            response = await client.get(f"{url}/all")
            follower_data = response.json()["data"]
            
            # Count matches and mismatches
            matching_keys = 0
            mismatched_keys = 0
            missing_keys = 0
            extra_keys = 0
            
            for key, value in leader_data.items():
                if key in follower_data:
                    if follower_data[key] == value:
                        matching_keys += 1
                    else:
                        mismatched_keys += 1
                        print(f"  {follower_name}: Key '{key}' mismatch - Leader: '{value}', Follower: '{follower_data[key]}'")
                else:
                    missing_keys += 1
            
            for key in follower_data:
                if key not in leader_data:
                    extra_keys += 1
            
            consistency_results["followers"][follower_name] = {
                "total_keys": len(follower_data),
                "matching": matching_keys,
                "mismatched": mismatched_keys,
                "missing": missing_keys,
                "extra": extra_keys
            }
            
            match_percentage = (matching_keys / len(leader_data) * 100) if leader_data else 100
            print(f"{follower_name}: {len(follower_data)} keys, {matching_keys} matching ({match_percentage:.1f}%), {mismatched_keys} mismatched, {missing_keys} missing")
    
    return consistency_results

def update_write_quorum(quorum: int):
    """
    Update the write quorum in the docker-compose.yml file.
    This requires restarting the leader container.
    """
    import re
    
    with open("docker-compose.yml", "r") as f:
        content = f.read()
    
    # Update WRITE_QUORUM value
    content = re.sub(
        r'(WRITE_QUORUM=)\d+',
        f'\\g<1>{quorum}',
        content
    )
    
    with open("docker-compose.yml", "w") as f:
        f.write(content)

async def restart_leader():
    """Restart the leader container to apply new configuration."""
    print("Restarting leader container...")
    cwd = os.path.dirname(os.path.abspath(__file__)) or "."
    # Use up -d --force-recreate to reload environment variables from docker-compose.yml
    # docker-compose restart doesn't reload env vars, it just restarts the same container
    subprocess.run(["docker-compose", "up", "-d", "--force-recreate", "leader"], 
                   capture_output=True, 
                   cwd=cwd)
    await asyncio.sleep(5)  # Wait for leader to restart
    await wait_for_services(timeout=30)

def calculate_percentile(data: List[float], percentile: float) -> float:
    """Calculate the given percentile of a list of values."""
    sorted_data = sorted(data)
    index = (percentile / 100) * (len(sorted_data) - 1)
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_data):
        return sorted_data[-1]
    weight = index - lower
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

def plot_results(quorum_latencies: Dict[int, List[float]]):
    """
    Plot write quorum vs latency metrics (mean, median, p95, p99).
    X-axis: all 5 quorum values (1-5)
    Y-axis: 0 to 1.0 seconds
    Lines: mean, median, p95, p99
    """
    quorums = sorted(quorum_latencies.keys())
    
    # Calculate metrics for each quorum (in seconds)
    means = [statistics.mean(quorum_latencies[q]) for q in quorums]
    medians = [statistics.median(quorum_latencies[q]) for q in quorums]
    p95s = [calculate_percentile(quorum_latencies[q], 95) for q in quorums]
    p99s = [calculate_percentile(quorum_latencies[q], 99) for q in quorums]
    
    plt.figure(figsize=(10, 6))
    
    # Plot all 4 lines
    plt.plot(quorums, means, marker='o', linewidth=2, markersize=8, 
             color='blue', label='Mean')
    plt.plot(quorums, medians, marker='s', linewidth=2, markersize=8, 
             color='green', label='Median')
    plt.plot(quorums, p95s, marker='^', linewidth=2, markersize=8, 
             color='orange', label='P95')
    plt.plot(quorums, p99s, marker='d', linewidth=2, markersize=8, 
             color='red', label='P99')
    
    plt.xlabel('Write Quorum', fontsize=12)
    plt.ylabel('Write Latency (seconds)', fontsize=12)
    plt.title('Write Quorum vs Write Latency\n(Semi-Synchronous Replication)', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.xticks([1, 2, 3, 4, 5])
    plt.ylim(0, 1.0)  # Y-axis from 0 to 1.0 seconds
    plt.xlim(0.5, 5.5)  # X-axis with some padding
    plt.legend(loc='upper left', fontsize=10)
    
    # Add value annotations for each point
    for q_idx, q in enumerate(quorums):
        plt.annotate(f'{means[q_idx]:.2f}s', (q, means[q_idx]), 
                    textcoords="offset points", xytext=(5, 5), ha='left', fontsize=8, color='blue')
        plt.annotate(f'{medians[q_idx]:.2f}s', (q, medians[q_idx]), 
                    textcoords="offset points", xytext=(5, -10), ha='left', fontsize=8, color='green')
    
    plt.tight_layout()
    plt.savefig('latency_vs_quorum.png', dpi=150)
    print("\nPlot saved as 'latency_vs_quorum.png'")
    plt.show()

def print_analysis(quorum_latencies: Dict[int, List[float]], consistency_results: Dict):
    """
    Print analysis and explanation of results.
    """
    print("\n" + "="*60)
    print("ANALYSIS AND EXPLANATION")
    print("="*60)
    
    print("\n1. WRITE QUORUM VS LATENCY ANALYSIS:")
    print("-" * 40)
    print("""
The relationship between write quorum and latency is explained by the 
semi-synchronous replication mechanism:

- With WRITE_QUORUM=1: The leader only needs ONE follower to confirm 
  the write before returning success. It waits for the fastest follower,
  so latency is minimal.

- With WRITE_QUORUM=2-3: The leader must wait for 2-3 followers to confirm.
  Latency increases because we now wait for the 2nd or 3rd fastest follower.

- With WRITE_QUORUM=4-5: The leader must wait for most or all followers.
  Latency significantly increases as we're now waiting for slower followers,
  including those with higher simulated network delays.

The network delay simulation (0-1000ms random delay) amplifies this effect.
With 5 followers and random delays, the expected wait time increases with
higher quorums because we need to wait for more "slow" followers.

Mathematical intuition: If delays are uniformly distributed [0, MAX_DELAY],
- Quorum=1: Expected latency ≈ MAX_DELAY/6 (min of 5 uniform random vars)
- Quorum=5: Expected latency ≈ 5*MAX_DELAY/6 (max of 5 uniform random vars)
""")
    
    print("\n2. DATA CONSISTENCY ANALYSIS:")
    print("-" * 40)
    
    if consistency_results:
        leader_keys = consistency_results.get("leader_keys", 0)
        print(f"Leader has {leader_keys} keys")
        
        all_consistent = True
        for follower, stats in consistency_results.get("followers", {}).items():
            if stats["mismatched"] > 0 or stats["missing"] > 0:
                all_consistent = False
        
        if all_consistent:
            print("""
All replicas have CONSISTENT data with the leader!

This is the expected outcome because:
1. Single-leader replication ensures all writes go through one node
2. The leader assigns timestamps to writes for ordering
3. Followers apply writes in timestamp order (last-write-wins)
4. After waiting for replication to complete, all nodes converge

Even with concurrent writes to the same keys, the timestamp-based
conflict resolution ensures all replicas end up with the same final value.
""")
        else:
            print("""
Some replicas have INCONSISTENT data!

Possible reasons:
1. Replication not yet complete (async portion still in progress)
2. Network delays caused some replication messages to be delayed
3. With lower write quorums, not all followers receive immediate updates

This demonstrates the trade-off in semi-synchronous replication:
- Lower quorum = faster writes but potential temporary inconsistency
- Higher quorum = slower writes but better consistency guarantees

Note: Eventually, all replicas should converge to the same state
as the async replication completes.
""")
    
    print("\n3. TRADE-OFF SUMMARY:")
    print("-" * 40)
    print("""
| Quorum | Latency    | Durability | Consistency |
|--------|------------|------------|-------------|
|   1    | Lowest     | Lowest     | Weakest     |
|   2    | Low        | Medium     | Medium      |
|   3    | Medium     | Good       | Good        |
|   4    | High       | High       | High        |
|   5    | Highest    | Maximum    | Strongest   |

Recommendations:
- For speed-critical apps: Use quorum=1-2
- For balanced approach: Use quorum=2-3 (majority)
- For critical data: Use quorum=4-5
""")

async def main():
    """Main function to run the performance analysis."""
    print("="*60)
    print("PERFORMANCE ANALYSIS: Key-Value Store with Leader Replication")
    print("="*60)
    
    # Always test all 5 quorum values for complete graph
    quorum_values = [1, 2, 3, 4, 5]
    
    try:
        # Wait for services to be ready
        print("\nWaiting for services to be ready...")
        await wait_for_services()
        
        quorum_latencies = {}
        
        for quorum in quorum_values:
            # Update configuration and restart leader
            print(f"\nConfiguring write quorum = {quorum}...")
            update_write_quorum(quorum)
            await restart_leader()
            
            # Run performance test
            latencies = await run_performance_test(quorum)
            quorum_latencies[quorum] = latencies
        
        # Check data consistency after all tests
        consistency_results = await check_data_consistency()
        
        # Plot results
        print("\nGenerating plot...")
        plot_results(quorum_latencies)
        
        # Print analysis
        print_analysis(quorum_latencies, consistency_results)
        
        # Summary statistics
        print("\n" + "="*60)
        print("SUMMARY STATISTICS")
        print("="*60)
        print(f"{'Quorum':<8} {'Mean':<12} {'Median':<12} {'P95':<12} {'P99':<12} {'Count':<8}")
        print("-" * 64)
        for quorum in sorted(quorum_latencies.keys()):
            latencies = quorum_latencies[quorum]
            mean_val = statistics.mean(latencies)
            median_val = statistics.median(latencies)
            p95_val = calculate_percentile(latencies, 95)
            p99_val = calculate_percentile(latencies, 99)
            print(f"{quorum:<8} {mean_val:.3f}s{'':<6} {median_val:.3f}s{'':<6} {p95_val:.3f}s{'':<6} {p99_val:.3f}s{'':<6} {len(latencies):<8}")
        
    except Exception as e:
        print(f"Error during performance analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
