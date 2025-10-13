import socket
import sys
import os
import base64
from urllib.parse import urlsplit, unquote

HOST, PORT = "0.0.0.0", 8080

def build_response(body: bytes, status: int = 200, content_type: str = "text/html; charset=utf-8", extra_headers: dict | None = None) -> bytes:
    reason = {200: "OK", 404: "Not Found"}.get(status, "OK")
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

def guess_mime(path: str, content: bytes | None = None) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext in {".html", ".htm"}:
        return "text/html; charset=utf-8"
    if ext == ".css":
        return "text/css; charset=utf-8"
    if ext == ".js":
        return "application/javascript; charset=utf-8"
    if ext == ".json":
        return "application/json; charset=utf-8"
    if ext == ".svg":
        return "image/svg+xml"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".gif":
        return "image/gif"
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".txt":
        return "text/plain; charset=utf-8"

    # Try to detect text payload if content is provided
    if content is not None:
        try:
            content.decode("utf-8")
            return "text/plain; charset=utf-8"
        except UnicodeDecodeError:
            pass
    return "application/octet-stream"

def serve_file(path: str, base_dir: str) -> bytes:
    inline_mode = False
    # Support /inline/<rest> path to allow displaying PNG inline (no forced download)
    if path.startswith('/inline/'):
        inline_mode = True
        path = path[len('/inline'):]  # keep leading slash before filename
    # Normalize and prevent path traversal
    requested_rel = path.lstrip("/")
    full_path = os.path.normpath(os.path.join(base_dir, requested_rel))
    base_abs = os.path.abspath(base_dir)
    full_abs = os.path.abspath(full_path)
    if not full_abs.startswith(base_abs):
        return build_response(b"<h1>404 Not Found</h1>", status=404)

    # Directory handling: ALWAYS produce a directory listing per lab specification
    if os.path.isdir(full_abs):
        try:
            entries = sorted(os.listdir(full_abs))
        except OSError:
            return build_response(b"<h1>404 Not Found</h1>", status=404)

        # Build listing (directories shown with trailing slash)
        path_prefix = path if path.startswith("/") else "/" + path
        path_prefix = path_prefix.rstrip("/") or "/"
        items = []
        if os.path.abspath(full_abs) != os.path.abspath(base_abs):  # parent link
            parent = os.path.dirname(path_prefix.rstrip("/")) or "/"
            items.append(f'<li><a href="{parent}">..</a></li>')
        for name in entries:
            entry_abs = os.path.join(full_abs, name)
            if os.path.isdir(entry_abs):
                display = name + "/"
                href = (f"{path_prefix.rstrip('/')}/{display}" if path_prefix != "/" else f"/{display}")
            else:
                display = name
                href = f"{path_prefix.rstrip('/')}/{name}" if path_prefix != "/" else f"/{name}"
            items.append(f'<li><a href="{href}">{display}</a></li>')
        listing_html = f"<h1>Directory listing for {path_prefix}</h1><ul>{''.join(items)}</ul>"
        return build_response(listing_html.encode("utf-8"), status=200)

    # Serve files: only allow specific extensions per lab spec; otherwise 404
    if os.path.isfile(full_abs):
        try:
            with open(full_abs, "rb") as f:
                body = f.read()
            ext = os.path.splitext(full_abs.lower())[1]
            allowed = {".html", ".htm", ".png", ".pdf"}  # per lab requirement
            if ext not in allowed:
                return build_response(b"<h1>404 Not Found</h1>", status=404)
            content_type = guess_mime(full_abs, body)
            extra = None
            if ext == ".pdf":  # always download PDFs
                filename = os.path.basename(full_abs)
                extra = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
            elif ext == ".png" and not inline_mode:  # download PNG unless inline path used
                filename = os.path.basename(full_abs)
                extra = {"Content-Disposition": f"attachment; filename=\"{filename}\""}
            return build_response(body, status=200, content_type=content_type, extra_headers=extra)
        except OSError:
            return build_response(b"<h1>404 Not Found</h1>", status=404)

    return build_response(b"<h1>404 Not Found</h1>", status=404)


def run_server(base_dir):
    # Ensure sample assets exist for demonstration (pixel.png)
    try:
        ensure_sample_files(base_dir)
    except Exception:
        # Non-fatal if creation fails; server can still run
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # prevents "Address already in use"
        server_socket.bind((HOST, PORT))
        server_socket.listen(1)
        print(f"Serving {base_dir} on http://{HOST}:{PORT}")

        while True:
            client_conn, client_addr = server_socket.accept()
            request = client_conn.recv(1024).decode(errors="ignore")
            if not request:
                client_conn.close()
                continue

            # Parse request line and URL components safely
            try:
                request_line = request.splitlines()[0]
                method, target, _ = request_line.split(" ", 2)
            except ValueError:
                client_conn.close()
                continue

            parts = urlsplit(target)
            raw_path = parts.path or "/"
            path = unquote(raw_path)
            response = serve_file(path, base_dir)
            client_conn.sendall(response)
            client_conn.close()

if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    run_server(base_dir)
