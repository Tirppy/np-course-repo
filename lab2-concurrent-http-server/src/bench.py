import argparse
import socket
import threading
import time
from urllib.parse import urlsplit


def do_get(host: str, port: int, path: str, results: list[int], timeout: float | None = 5.0):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if timeout and timeout > 0:
                s.settimeout(timeout)
            s.connect((host, port))
            req = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Connection: close\r\n"
                f"User-Agent: bench/1.0\r\n"
                f"Accept: */*\r\n\r\n"
            )
            s.sendall(req.encode())
            # read response status line
            data = s.recv(4096)
            if not data:
                results.append(0)
                return
            line = data.split(b"\r\n", 1)[0].decode(errors="ignore")
            parts = line.split(" ")
            code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            results.append(code)
    except Exception:
        results.append(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("port", type=int)
    ap.add_argument("path")
    ap.add_argument("--concurrency", "-c", type=int, default=10)
    ap.add_argument("--per-worker", type=int, default=1)
    ap.add_argument("--rate", type=float, default=0.0, help="requests/sec per worker, 0 = as fast as possible")
    ap.add_argument("--duration", type=float, default=0.0, help="seconds to run in rate mode (overrides per-worker)")
    ap.add_argument("--timeout", type=float, default=5.0, help="socket timeout in seconds (default 5.0)")
    args = ap.parse_args()

    codes: list[int] = []

    def worker():
        if args.rate > 0 and args.duration > 0:
            interval = 1.0 / args.rate
            end = time.perf_counter() + args.duration
            while time.perf_counter() < end:
                do_get(args.host, args.port, args.path, codes, timeout=args.timeout)
                time.sleep(interval)
        else:
            for _ in range(args.per_worker):
                do_get(args.host, args.port, args.path, codes, timeout=args.timeout)

    threads = [threading.Thread(target=worker) for _ in range(args.concurrency)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    dt = time.perf_counter() - t0

    total = len(codes)
    from collections import Counter
    hist = Counter(codes)

    print(f"Requests: {total} in {dt:.3f}s -> {total/dt if dt>0 else 0:.2f} req/s")
    for k in sorted(hist):
        print(f"  {k}: {hist[k]}")


if __name__ == "__main__":
    main()
