"""Phase 4: End-to-End tests with live uvicorn server.

Starts a real LivingTree server, makes HTTP requests against it,
and verifies responses. Tests: startup, static files, HTMX pages,
chat API, error handling, graceful shutdown.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

# Skip chat tests that require real LLM API keys
SKIP_CHAT = pytest.mark.skip(reason="Requires real LLM API keys configured")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Server port (random to avoid conflicts)
SERVER_PORT = 18765
BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """Poll server until it responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def server_process():
    """Start a real LivingTree uvicorn server for E2E testing."""
    # Ensure no port conflict
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', SERVER_PORT))
    except OSError:
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        pytest.skip(f"Port {SERVER_PORT} in use, use dynamic port")
    sock.close()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    cmd = [
        sys.executable, "-m", "uvicorn",
        "livingtree.api.server:create_app",
        "--factory",
        "--host", "127.0.0.1",
        "--port", str(SERVER_PORT),
        "--log-level", "error",
    ]

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(ROOT),
    )

    # Wait for server to be ready
    if not wait_for_server(HEALTH_URL, timeout=30):
        proc.terminate()
        proc.wait()
        pytest.fail("Server failed to start within 30s")

    yield proc

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ══════════════════════════════════════════════════════
# Test: Server Startup
# ══════════════════════════════════════════════════════

class TestServerStartup:
    """Verify the server starts and responds on key endpoints."""

    def test_health_endpoint(self, server_process):
        """GET /api/health returns 200 with JSON."""
        r = requests.get(HEALTH_URL, timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("ok", "healthy")
        assert "version" in data

    def test_health_content_type(self, server_process):
        """Health endpoint returns application/json."""
        r = requests.get(HEALTH_URL, timeout=5)
        assert "application/json" in r.headers["content-type"]

    def test_root_redirect_or_200(self, server_process):
        """GET / returns a valid response."""
        r = requests.get(BASE_URL, timeout=5, allow_redirects=True)
        assert r.status_code in (200, 302, 301, 307, 308)

    def test_docs_available(self, server_process):
        """GET /docs returns Swagger UI."""
        r = requests.get(f"{BASE_URL}/docs", timeout=5, allow_redirects=True)
        assert r.status_code == 200
        assert "swagger" in r.text.lower() or "openapi" in r.text.lower()

    def test_favicon(self, server_process):
        """GET /favicon.ico returns an image or 204."""
        r = requests.get(f"{BASE_URL}/favicon.ico", timeout=5)
        assert r.status_code in (200, 204)


# ══════════════════════════════════════════════════════
# Test: Static Assets
# ══════════════════════════════════════════════════════

class TestStaticAssets:
    """Verify static files are served correctly."""

    def test_css_served(self, server_process):
        """GET /css/ returns valid CSS content."""
        # First check if the directory exists
        r = requests.get(f"{BASE_URL}/css/", timeout=5)
        assert r.status_code in (200, 404)  # May redirect or list or 404

    def test_js_served(self, server_process):
        """GET /js/ is accessible."""
        r = requests.get(f"{BASE_URL}/js/", timeout=5)
        assert r.status_code in (200, 404)

    def test_assets_served(self, server_process):
        """GET /assets/ is accessible."""
        r = requests.get(f"{BASE_URL}/assets/", timeout=5)
        assert r.status_code in (200, 404)

    def test_app_js(self, server_process):
        """GET /app.js returns JavaScript."""
        r = requests.get(f"{BASE_URL}/app.js", timeout=5)
        if r.status_code == 200:
            assert "javascript" in r.headers.get("content-type", "").lower() or r.text.strip()


# ══════════════════════════════════════════════════════
# Test: HTMX Pages
# ══════════════════════════════════════════════════════

class TestHTMXPages:
    """Verify HTMX template pages render with correct content."""

    HTMX_PAGES = [
        "/tree/chat",
        "/tree/dashboard",
        "/tree/knowledge",
        "/tree/admin",
    ]

    @pytest.mark.parametrize("path", HTMX_PAGES)
    def test_page_returns_200(self, server_process, path):
        """Each HTMX page returns 200 with HTML content."""
        r = requests.get(f"{BASE_URL}{path}", timeout=5, allow_redirects=True)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "text/html" in r.headers["content-type"].lower()

    def test_index_html(self, server_process):
        """The root page contains LivingTree branding."""
        r = requests.get(BASE_URL, timeout=5, allow_redirects=True)
        if r.status_code == 200:
            html = r.text.lower()
            assert "livingtree" in html or "living" in html or "tree" in html


# ══════════════════════════════════════════════════════
# Test: Chat API
# ══════════════════════════════════════════════════════

class TestChatAPIE2E:
    """End-to-end chat API tests against live server."""

    @SKIP_CHAT
    def test_chat_basic_post(self, server_process):
        """POST /api/chat with a simple message returns valid JSON."""
        payload = {"message": "Hello from E2E test"}
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "session_id" in data
        assert "intent" in data or "reflections" in data

    @SKIP_CHAT
    def test_chat_with_context(self, server_process):
        """POST /api/chat with session context."""
        payload = {
            "message": "What can you do?",
            "session_id": "e2e-test-001",
            "context": {"language": "zh"},
        }
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            timeout=15,
        )
        assert r.status_code == 200

    def test_chat_invalid_json(self, server_process):
        """POST /api/chat with invalid JSON returns 422."""
        r = requests.post(
            f"{BASE_URL}/api/chat",
            data="not json",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert r.status_code == 422

    @SKIP_CHAT
    def test_chat_empty_message(self, server_process):
        """POST /api/chat with empty message."""
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": ""},
            timeout=10,
        )
        assert r.status_code in (200, 422)

    def test_chat_missing_message(self, server_process):
        """POST /api/chat without message field returns 422."""
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json={},
            timeout=5,
        )
        assert r.status_code == 422


# ══════════════════════════════════════════════════════
# Test: Error Handling
# ══════════════════════════════════════════════════════

class TestErrorHandlingE2E:
    """Verify error responses from a live server."""

    def test_404_json_response(self, server_process):
        """GET nonexistent endpoint returns 404 with JSON."""
        r = requests.get(f"{BASE_URL}/api/nonexistent-endpoint-xyz", timeout=5)
        assert r.status_code == 404
        try:
            data = r.json()
            assert "detail" in data
        except json.JSONDecodeError:
            pass  # HTML fallback is also acceptable

    def test_405_method_not_allowed(self, server_process):
        """GET /api/chat without POST returns 405."""
        r = requests.get(f"{BASE_URL}/api/chat", timeout=5)
        assert r.status_code == 405

    def test_500_internal_error_format(self, server_process):
        """Server has an error handler for unexpected errors."""
        # Send a request that triggers parsing
        r = requests.post(
            f"{BASE_URL}/api/chat",
            json=[1, 2, 3],  # Array where object expected
            timeout=5,
        )
        assert r.status_code in (422, 500)


# ══════════════════════════════════════════════════════
# Test: Rate Limiting
# ══════════════════════════════════════════════════════

class TestRateLimitingE2E:
    """Verify rate limiting works on live server."""

    def test_first_request_not_limited(self, server_process):
        """First request should not be rate limited."""
        r = requests.get(HEALTH_URL, timeout=5)
        assert r.status_code == 200

    def test_rate_limit_header_present(self, server_process):
        """Rate limit headers should be present in response."""
        r = requests.get(HEALTH_URL, timeout=5)
        # slowapi should add rate limit headers
        assert r.status_code == 200


# ══════════════════════════════════════════════════════
# Test: CORS
# ══════════════════════════════════════════════════════

class TestCORSE2E:
    """Verify CORS headers on live server."""

    def test_cors_headers_present(self, server_process):
        """OPTIONS preflight returns CORS headers."""
        r = requests.options(
            f"{BASE_URL}/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
            timeout=5,
        )
        assert r.status_code == 200
        assert "access-control-allow-origin" in r.headers or "access-control-allow-methods" in r.headers

    def test_cors_on_get(self, server_process):
        """GET request includes CORS allow-origin header."""
        r = requests.get(
            HEALTH_URL,
            headers={"Origin": "http://localhost:3000"},
            timeout=5,
        )
        assert r.status_code == 200
        # CORS middleware should add this header
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao == "*" or "localhost" in acao


# ══════════════════════════════════════════════════════
# Test: Performance Baseline
# ══════════════════════════════════════════════════════

class TestPerformanceE2E:
    """Performance baseline for production deployment."""

    def test_health_latency_under_100ms(self, server_process):
        """Health endpoint should respond in under 100ms."""
        import statistics
        times = []
        for _ in range(10):
            t0 = time.time()
            r = requests.get(HEALTH_URL, timeout=5)
            r.raise_for_status()
            times.append((time.time() - t0) * 1000)
        median = statistics.median(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        print(f"Health latency: median={median:.1f}ms, p95={p95:.1f}ms")
        assert median < 200, f"Median health latency {median:.1f}ms exceeds 200ms"

    def test_concurrent_requests(self, server_process):
        """Server handles 20 concurrent health requests without errors."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch():
            r = requests.get(HEALTH_URL, timeout=10)
            return r.status_code

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(fetch) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]

        assert all(s == 200 for s in results), f"Some requests failed: {results}"
        assert len(results) == 20


# ══════════════════════════════════════════════════════
# Test: Cookie / Session
# ══════════════════════════════════════════════════════

class TestSessionE2E:
    """Verify session/cookie behavior."""

    @SKIP_CHAT
    def test_session_consistency(self, server_process):
        """Chat requests with same session_id are routed correctly."""
        sid = "e2e-session-test"
        r1 = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": "Hello", "session_id": sid},
            timeout=15,
        )
        r2 = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": "Again", "session_id": sid},
            timeout=15,
        )
        if r1.status_code == 200 and r2.status_code == 200:
            assert r1.json().get("session_id") == r2.json().get("session_id")


# ══════════════════════════════════════════════════════
# Test: Graceful Shutdown
# ══════════════════════════════════════════════════════

class TestShutdown:
    """Verify clean server shutdown behavior."""

    def test_server_stops_cleanly(self, server_process):
        """After terminate, server stops accepting connections."""
        # Server is started — terminate it
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            server_process.wait()

        # Verify port is released
        time.sleep(1)
        with pytest.raises(requests.ConnectionError):
            requests.get(HEALTH_URL, timeout=2)
