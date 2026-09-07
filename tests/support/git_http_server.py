"""Minimal local git-smart-HTTP server enforcing HTTP Basic Auth, wrapping
the real `git http-backend`. Lets tests prove GitTool.push's real HTTPS
credential path (docs/DECISIONS.md ADR-011) end-to-end -- wrong/missing
credential rejected, correct credential actually pushes -- without touching
a real GitHub repo. Test-only; not shipped with the package."""

import base64
import http.server
import os
import socketserver
import subprocess
import threading
from contextlib import contextmanager

GIT_HTTP_BACKEND = "/usr/lib/git-core/git-http-backend"


class _AuthedBackendHandler(http.server.BaseHTTPRequestHandler):
    project_root = None
    username = None
    password = None

    def _check_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode()
        except Exception:
            return False
        return decoded == f"{self.username}:{self.password}"

    def _run_backend(self):
        if not self._check_auth():
            body = b"auth required"
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="test"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        length = int(self.headers.get("Content-Length", 0))
        request_body = self.rfile.read(length) if length else b""
        path_info, _, query = self.path.partition("?")
        env = {
            **os.environ,
            "GIT_PROJECT_ROOT": str(self.project_root),
            "GIT_HTTP_EXPORT_ALL": "1",
            "PATH_INFO": path_info,
            "QUERY_STRING": query,
            "REQUEST_METHOD": self.command,
            "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(length),
            "REMOTE_USER": self.username,
        }
        proc = subprocess.run([GIT_HTTP_BACKEND], input=request_body, env=env, capture_output=True)
        header_blob, _, body = proc.stdout.partition(b"\r\n\r\n")
        status = 200
        headers = []
        for line in header_blob.decode(errors="replace").split("\r\n"):
            if not line:
                continue
            if line.lower().startswith("status:"):
                status = int(line.split(":", 1)[1].strip().split()[0])
            else:
                key, _, value = line.partition(":")
                headers.append((key.strip(), value.strip()))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._run_backend()

    def do_POST(self):
        self._run_backend()

    def log_message(self, *_args):
        pass


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def make_bare_http_repo(project_root, name="repo.git"):
    """Bare repo under project_root, receive-pack enabled for push over HTTP."""
    repo = project_root / name
    subprocess.run(["/usr/bin/git", "init", "--bare", "-q", str(repo)], check=True)
    subprocess.run(
        ["/usr/bin/git", "config", "--file", str(repo / "config"), "http.receivepack", "true"],
        check=True,
    )
    return repo


@contextmanager
def basic_auth_git_server(project_root, *, username, password):
    """Yields a base URL (e.g. http://127.0.0.1:PORT); append '/<name>.git'."""
    handler = type(
        "_BoundHandler",
        (_AuthedBackendHandler,),
        {"project_root": project_root, "username": username, "password": password},
    )
    server = _Server(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
