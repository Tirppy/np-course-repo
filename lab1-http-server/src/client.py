import socket
import sys
import os
from urllib.parse import urlsplit


def http_client_request(host: str, port: int, filename: str, out_target: str | None = None):
    if not filename.startswith('/'):
        path = '/' + filename
    else:
        path = filename
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"User-Agent: lab1-client/1.0\r\n"
            f"Accept: */*\r\n"
            f"\r\n"
        )
        s.sendall(req.encode("utf-8"))
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
    raw = b"".join(chunks)
    _handle_response(raw, out_target)


def http_client_url(url: str):
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    port = parts.port or (443 if parts.scheme == "https" else 8080 if parts.port is None and parts.hostname in (None, "localhost") else 80)
    # If scheme is http and no port provided, default to 80; but for our lab server on localhost: default 8080
    if parts.scheme in ("", "http") and parts.port is None and (host == "localhost" or host == "127.0.0.1"):
        port = 8080
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Connection: close\r\n"
            f"User-Agent: lab1-client/1.0\r\n"
            f"Accept: */*\r\n"
            f"\r\n"
        )
        s.sendall(req.encode("utf-8"))

        # Read all bytes
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
        raw = b"".join(chunks)

    _handle_response(raw)


def _handle_response(raw: bytes, out_target: str | None = None):
    header_end = raw.find(b"\r\n\r\n")
    if header_end == -1:
        print("Malformed response: no header terminator")
        print(raw.decode("utf-8", errors="ignore"))
        return
    header_bytes = raw[:header_end]
    body = raw[header_end + 4 :]
    header_text = header_bytes.decode("iso-8859-1", errors="ignore")
    lines = header_text.split("\r\n")
    status_line = lines[0]
    header_pairs = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            header_pairs[k.strip().lower()] = v.strip()
    content_type = header_pairs.get("content-type", "")
    if content_type.startswith("text/html"):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            text = body.decode("iso-8859-1", errors="ignore")
        print(text)
    elif content_type.startswith("image/png"):
        path = _resolve_output_path(out_target, default_name="download.png", suggested_name=_extract_filename_from_headers(header_pairs, fallback="download.png"))
        with open(path, "wb") as f:
            f.write(body)
        print(f"Saved PNG to {path}")
    elif content_type.startswith("application/pdf"):
        path = _resolve_output_path(out_target, default_name="download.pdf", suggested_name=_extract_filename_from_headers(header_pairs, fallback="download.pdf"))
        with open(path, "wb") as f:
            f.write(body)
        print(f"Saved PDF to {path}")
    else:
        print(status_line)
        for k, v in header_pairs.items():
            print(f"{k}: {v}")
        if body:
            path = _resolve_output_path(out_target, default_name="download.bin", suggested_name=_extract_filename_from_headers(header_pairs, fallback="download.bin"))
            with open(path, "wb") as f:
                f.write(body)
            print(f"Saved body to {path}")


def _extract_filename_from_headers(headers: dict, fallback: str) -> str:
    cd = headers.get("content-disposition")
    if cd and "filename=" in cd:
        part = cd.split("filename=", 1)[1].strip().strip('"')
        if part:
            return part
    return fallback


def _resolve_output_path(out_target: str | None, default_name: str, suggested_name: str) -> str:
    if out_target is None:
        return suggested_name or default_name
    # Determine if user meant directory
    if os.path.isdir(out_target):
        return os.path.join(out_target, suggested_name)
    # If it does not exist: decide by trailing separator or absence of extension
    if not os.path.exists(out_target):
        sep = os.sep
        if out_target.endswith(("/", "\\")):
            os.makedirs(out_target, exist_ok=True)
            return os.path.join(out_target, suggested_name)
        # Heuristic: if no dot in last path component -> directory intent
        last = os.path.basename(out_target.rstrip("/\\"))
        if "." not in last:
            os.makedirs(out_target, exist_ok=True)
            return os.path.join(out_target, suggested_name)
        # Otherwise treat as file path
        parent = os.path.dirname(out_target)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        return out_target
    # Exists but not a directory: treat as file path override
    return out_target


def main():
    if len(sys.argv) == 2 and ("://" in sys.argv[1]):
        http_client_url(sys.argv[1])
        return
    if len(sys.argv) not in (4, 5):
        print("Usage (spec): python src/client.py <server_host> <server_port> <filename> [output_path]")
        print("Examples:")
        print("  python src/client.py localhost 8080 index.html")
        print("  python src/client.py localhost 8080 books/CSlab2.pdf downloads/")
        print("  python src/client.py localhost 8080 books/CSlab2.pdf downloads/custom-name.pdf")
        print("Legacy URL mode:")
        print("  python src/client.py http://localhost:8080/books/")
        return
    host = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    out_target = sys.argv[4] if len(sys.argv) == 5 else None
    http_client_request(host, port, filename, out_target)


if __name__ == "__main__":
    main()
