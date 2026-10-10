"""Local browser viewer for the recovered Blustone .jet files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
import webbrowser


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from jet_decoder import inspect_file, quick_fingerprint, quick_kind  # noqa: E402


SKIP_DIRECTORIES = {".git", "node_modules", "__pycache__", ".venv", "venv"}
CLIENT_DISCONNECTS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


class ViewerState:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._cache_lock = threading.Lock()
        self._files_cache: tuple[float, list[dict[str, object]]] | None = None

    def safe_file(self, relative: str) -> Path:
        normalized = unquote(relative).replace("\\", "/")
        if not normalized or normalized.startswith("/"):
            raise ValueError("A relative JET path is required")
        parts = [part for part in normalized.split("/") if part]
        if any(part in (".", "..") for part in parts):
            raise ValueError("Path traversal is not allowed")
        candidate = (self.root / Path(*parts)).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("The requested path is outside the configured root")
        if not candidate.is_file() or candidate.suffix.lower() != ".jet":
            raise ValueError("Only existing .jet files are available")
        return candidate

    def _scan(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for directory, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(
                name for name in dirnames if name not in SKIP_DIRECTORIES and not name.startswith(".")
            )
            for filename in sorted(filenames):
                if not filename.lower().endswith(".jet"):
                    continue
                path = Path(directory) / filename
                try:
                    stat = path.stat()
                    with path.open("rb") as handle:
                        sample = handle.read(4096)
                        if stat.st_size > 1024:
                            handle.seek(max(0, stat.st_size - 512))
                            sample += handle.read(512)
                    relative_path = path.relative_to(self.root)
                    relative = relative_path.as_posix()
                    parent = relative_path.parent.as_posix()
                    rows.append(
                        {
                            "path": relative,
                            "name": filename,
                            "directory": "" if parent == "." else parent,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "kind": quick_kind(sample),
                            "fingerprint": quick_fingerprint(sample),
                        }
                    )
                except OSError:
                    # A file disappearing during the scan should not prevent
                    # the rest of the offline corpus from being browsable.
                    continue
        rows.sort(key=lambda row: (str(row["name"]).lower(), str(row["path"]).lower()))
        return rows

    def files(self, force: bool = False) -> list[dict[str, object]]:
        now = __import__("time").monotonic()
        with self._cache_lock:
            if force or self._files_cache is None or now - self._files_cache[0] > 30:
                self._files_cache = (now, self._scan())
            return self._files_cache[1]


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class RequestHandler(BaseHTTPRequestHandler):
    state: ViewerState
    index_html: bytes

    server_version = "BlustoneJETViewer/0.1"

    def log_message(self, format: str, *args: object) -> None:
        # Keep the terminal useful without dumping binary request details.
        sys.stdout.write(f"{self.address_string()} - {format % args}\n")

    def _send(self, status: int, body: bytes, content_type: str, *, download_name: str | None = None) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if download_name:
                safe_name = download_name.replace('"', "")
                self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except CLIENT_DISCONNECTS:
            self.close_connection = True

    def _error(self, status: int, message: str) -> None:
        self._send(status, json_bytes({"error": message}), "application/json; charset=utf-8")

    def _query(self) -> dict[str, list[str]]:
        return parse_qs(urlsplit(self.path).query, keep_blank_values=False)

    def do_GET(self) -> None:  # noqa: N802
        route = urlsplit(self.path).path
        try:
            if route == "/" or route == "/index.html":
                self._send(HTTPStatus.OK, self.index_html, "text/html; charset=utf-8")
                return
            if route == "/api/files":
                force = self._query().get("refresh") == ["1"]
                rows = self.state.files(force=force)
                self._send(
                    HTTPStatus.OK,
                    json_bytes({"root": str(self.state.root), "count": len(rows), "files": rows}),
                    "application/json; charset=utf-8",
                )
                return
            if route == "/api/file":
                self._handle_file()
                return
            if route == "/api/blob":
                self._handle_blob()
                return
            self._error(HTTPStatus.NOT_FOUND, "Not found")
        except CLIENT_DISCONNECTS:
            self.close_connection = True
        except ValueError as error:
            self._error(HTTPStatus.BAD_REQUEST, str(error))
        except FileNotFoundError:
            self._error(HTTPStatus.NOT_FOUND, "JET file not found")
        except OSError as error:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Could not read file: {error}")
        except Exception as error:  # pragma: no cover - last-resort local UI error
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Viewer error: {error}")

    def do_HEAD(self) -> None:  # noqa: N802
        # Browsers and media tools commonly probe playable resources with
        # HEAD before issuing a ranged GET.
        self.do_GET()

    def _requested_path(self) -> Path:
        values = self._query().get("path", [])
        if len(values) != 1:
            raise ValueError("Missing path query parameter")
        return self.state.safe_file(values[0])

    def _handle_file(self) -> None:
        path = self._requested_path()
        analysis, _variants = inspect_file(path)
        analysis["path"] = path.relative_to(self.state.root).as_posix()
        self._send(HTTPStatus.OK, json_bytes(analysis), "application/json; charset=utf-8")

    def _handle_blob(self) -> None:
        path = self._requested_path()
        variant = self._query().get("variant", ["raw"])[0]
        analysis, variants = inspect_file(path)
        if variant not in variants:
            raise ValueError("Unknown decoded variant")
        body = variants[variant]
        media = next((item for item in analysis["media"] if item["id"] == variant), None)  # type: ignore[index]
        if media:
            content_type = str(media["mime"])
            suffix = str(media["suffix"])
        elif variant.startswith("inflated"):
            content_type = "application/octet-stream"
            suffix = ".bin"
        else:
            content_type = "application/octet-stream"
            suffix = ".jet"
        download = self._query().get("download") == ["1"]
        self._send_rangeable(body, content_type, path.stem + suffix if download else None)

    def _send_rangeable(self, body: bytes, content_type: str, download_name: str | None) -> None:
        total = len(body)
        range_header = self.headers.get("Range")
        start = 0
        end = total - 1
        status = HTTPStatus.OK
        if range_header and range_header.startswith("bytes="):
            value = range_header[6:].split(",", 1)[0].strip()
            left, separator, right = value.partition("-")
            try:
                if not separator:
                    raise ValueError
                if left:
                    start = int(left)
                    end = int(right) if right else total - 1
                else:
                    amount = int(right)
                    start = max(0, total - amount)
                if start < 0 or start >= total or end < start:
                    raise ValueError
                end = min(end, total - 1)
                status = HTTPStatus.PARTIAL_CONTENT
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{total}")
                self.end_headers()
                return
        payload = body[start : end + 1]
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Accept-Ranges", "bytes")
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if download_name:
                self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except CLIENT_DISCONNECTS:
            self.close_connection = True


def run_server(root: Path, port: int, open_browser: bool) -> None:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Root directory does not exist: {root}")
    state = ViewerState(root)
    index_path = HERE / "index.html"
    index_html = index_path.read_bytes()
    class BoundRequestHandler(RequestHandler):
        pass

    BoundRequestHandler.state = state
    BoundRequestHandler.index_html = index_html
    server = ThreadingHTTPServer(("127.0.0.1", port), BoundRequestHandler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"JET viewer root: {root}")
    print(f"Open: {url}")
    print("Press Ctrl+C to stop. Source files are read-only.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping JET viewer.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Browse recovered Blustone JET files locally")
    parser.add_argument(
        "--root",
        type=Path,
        default=HERE.parents[1],
        help="repository/evidence root to scan (default: this Blustone repository)",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser automatically")
    args = parser.parse_args()
    run_server(args.root, args.port, not args.no_browser)


if __name__ == "__main__":
    main()
