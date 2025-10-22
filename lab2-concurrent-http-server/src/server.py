import os
import sys
import socket
import threading
import time
from collections import deque, defaultdict
from urllib.parse import urlsplit, unquote

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 8081))
DELAY_MS = int(os.environ.get("DELAY_MS", 1000))  # simulate work per request
COUNTER_MODE = os.environ.get("COUNTER_MODE", "naive")  # naive | locked
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", 5))  # per-IP requests per WINDOW_SEC
WINDOW_SEC = float(os.environ.get("WINDOW_SEC", 1.0))

# Request counters (path -> count)
request_counts: dict[str, int] = defaultdict(int)
counts_lock = threading.Lock()

# Rate limiter data: ip -> deque[timestamps]
ip_windows: dict[str, deque] = defaultdict(deque)
rate_lock = threading.Lock()


def build_response(body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8", extra_headers: dict | None = None) -> bytes:
    reason = {200: "OK", 404: "Not Found", 429: "Too Many Requests"}.get(status, "OK")
    headers = [
        f"HTTP/1.1 {status} {reason}",
        f"Content-Type: {content_type}",
        f"Content-Length: {len(body)}",
        "Connection: close",
    ]
    if extra_headers:
        for k, v in extra_headers.items():
            headers.append(f"{k}: {v}")
    headers.extend(["", ""])  # end of headers
    return "\r\n".join(headers).encode("utf-8") + body


def guess_mime(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext in {".html", ".htm"}:
        return "text/html; charset=utf-8"
    if ext == ".png":
        return "image/png"
    if ext == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def allow_request(ip: str) -> bool:
    now = time.monotonic()
    with rate_lock:
        q = ip_windows[ip]
        # drop older than window
        cutoff = now - WINDOW_SEC
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) < RATE_LIMIT:
            q.append(now)
            return True
        return False


def increment_counter(path: str):
    # Normalize path representation for counting
    p = path.rstrip("/") or "/"
    if COUNTER_MODE == "naive":
        # introduce a small timing window to surface races
        current = request_counts.get(p, 0)
        time.sleep(0.005)
        request_counts[p] = current + 1
    else:
        with counts_lock:
            request_counts[p] += 1


def render_dir_listing(dir_abs: str, base_abs: str, req_path: str) -> bytes:
    try:
        entries = sorted(os.listdir(dir_abs))
    except OSError:
        return build_response(b"<h1>404 Not Found</h1>", status=404)

    prefix = req_path if req_path.startswith("/") else "/" + req_path
    prefix = prefix.rstrip("/") or "/"

    rows = []

    # parent link row
    if os.path.abspath(dir_abs) != os.path.abspath(base_abs):
        parent = os.path.dirname(prefix.rstrip("/")) or "/"
        parent_hits = request_counts.get(parent.rstrip("/"), 0)
        rows.append(f"<tr><td><a href=\"{parent}\">..</a></td><td>{parent_hits}</td></tr>")

    for name in entries:
        entry_abs = os.path.join(dir_abs, name)
        if os.path.isdir(entry_abs):
            display = name + "/"
            href = (f"{prefix.rstrip('/')}/{display}" if prefix != "/" else f"/{display}")
            hits = request_counts.get(href.rstrip("/"), 0)
        else:
            display = name
            href = f"{prefix.rstrip('/')}/{name}" if prefix != "/" else f"/{name}"
            # Show the number stored for this file path
            hits = request_counts.get(href.rstrip("/"), 0)
        rows.append(f"<tr><td><a href=\"{href}\">{display}</a></td><td>{hits}</td></tr>")

    table = (
        "<table border=\"1\" cellspacing=\"0\" cellpadding=\"6\">"
        "<thead><tr><th>File/Directory</th><th>Hits</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )
    html = f"<h1>Directory listing for {prefix}</h1>{table}"
    return build_response(html.encode("utf-8"), 200, "text/html; charset=utf-8")


def handle_request(path: str, base_dir: str) -> bytes:
    # Directory handling
    requested_rel = path.lstrip("/")
    full_abs = os.path.abspath(os.path.normpath(os.path.join(base_dir, requested_rel)))
    base_abs = os.path.abspath(base_dir)
    if not full_abs.startswith(base_abs):
        return build_response(b"<h1>404 Not Found</h1>", status=404)

    if os.path.isdir(full_abs):
        # Count directory opens as hits too
        increment_counter(path)
        return render_dir_listing(full_abs, base_abs, path)

    if os.path.isfile(full_abs):
        ext = os.path.splitext(full_abs.lower())[1]
        if ext not in {".html", ".htm", ".png", ".pdf"}:
            return build_response(b"<h1>404 Not Found</h1>", status=404)
        try:
            with open(full_abs, "rb") as f:
                body = f.read()
        except OSError:
            return build_response(b"<h1>404 Not Found</h1>", status=404)
        increment_counter(path)
        ctype = guess_mime(full_abs)
        extra = None
        if ext in {".pdf", ".png"}:
            filename = os.path.basename(full_abs)
            extra = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
        return build_response(body, 200, ctype, extra)

    return build_response(b"<h1>404 Not Found</h1>", status=404)


def handle_client(conn: socket.socket, addr, base_dir: str):
    try:
        # Basic request read
        data = conn.recv(2048)
        if not data:
            return
        try:
            req_line = data.split(b"\r\n", 1)[0].decode(errors="ignore")
            method, target, _ = req_line.split(" ", 2)
        except Exception:
            return
        parts = urlsplit(target)
        path = unquote(parts.path or "/")

        # Rate limiting
        ip = addr[0]
        if not allow_request(ip):
            conn.sendall(build_response(b"<h1>429 Too Many Requests</h1>", 429))
            return

        # Simulate work
        time.sleep(DELAY_MS / 1000.0)

        resp = handle_request(path, base_dir)
        conn.sendall(resp)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_server(base_dir: str):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(128)
        print(f"[lab2] Serving {base_dir} on http://{HOST}:{PORT} | mode={COUNTER_MODE} delay={DELAY_MS}ms rate={RATE_LIMIT}/s")
        while True:
            conn, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr, base_dir), daemon=True)
            t.start()


if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "content"
    run_server(base_dir)
