"""Test relay server API endpoints with aiohttp test client."""
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase


class TestRelayAPI(AioHTTPTestCase):
    async def get_application(self):
        from relay_server import P2PRelayServer
        server = P2PRelayServer(port=0)
        return server._app

    # ── Health ──

    async def test_health(self):
        resp = await self.client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

    # ── Login ──

    async def test_login_success(self):
        resp = await self.client.post("/login", json={"username": "admin", "password": "admin123"})
        assert resp.status == 200
        data = await resp.json()
        assert "api_key" in data
        assert data["username"] == "admin"

    async def test_login_wrong_password(self):
        resp = await self.client.post("/login", json={"username": "admin", "password": "wrong"})
        assert resp.status == 401

    async def test_login_missing_fields(self):
        resp = await self.client.post("/login", json={"username": "admin"})
        assert resp.status == 400

    # ── Status (requires auth) ──

    async def test_status_unauthorized(self):
        resp = await self.client.get("/status")
        assert resp.status == 401

    async def test_status_with_key(self):
        # Login first to get api_key
        login_resp = await self.client.post("/login", json={"username": "admin", "password": "admin123"})
        api_key = (await login_resp.json())["api_key"]

        resp = await self.client.get("/status", headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status == 200

    # ── Admin (without login, should redirect to login page) ──

    async def test_admin_unauthenticated(self):
        resp = await self.client.get("/admin")
        assert resp.status == 200
        assert "login" in (await resp.text()).lower()

    async def test_admin_login_page(self):
        resp = await self.client.get("/admin/login")
        assert resp.status == 200
        assert "login" in (await resp.text()).lower()

    # ── Peer endpoints ──

    async def test_peer_register(self):
        resp = await self.client.post("/peers/register", json={
            "peer_id": "test-peer-1", "port": 9999, "metadata": {"username": "test"}
        })
        assert resp.status == 200

    async def test_peer_discover(self):
        # Register a peer first
        await self.client.post("/peers/register", json={
            "peer_id": "test-peer-2", "port": 8888, "metadata": {}
        })
        resp = await self.client.get("/peers/discover")
        assert resp.status == 200
        data = await resp.json()
        assert "peers" in data

    # ── Cost report (requires auth) ──

    async def test_cost_report(self):
        login_resp = await self.client.post("/login", json={"username": "admin", "password": "admin123"})
        api_key = (await login_resp.json())["api_key"]

        resp = await self.client.post("/cost/report", json={
            "provider": "deepseek", "tokens_in": 1000, "tokens_out": 500
        }, headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status == 200

    # ── LLM Proxy (requires subscription pool configured) ──

    async def test_llm_proxy_no_subscription(self):
        login_resp = await self.client.post("/login", json={"username": "admin", "password": "admin123"})
        api_key = (await login_resp.json())["api_key"]

        resp = await self.client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "hi"}]
        }, headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status == 503  # No subscription configured

    # ── Web search (requires external network) ──

    async def test_web_search(self):
        login_resp = await self.client.post("/login", json={"username": "admin", "password": "admin123"})
        api_key = (await login_resp.json())["api_key"]

        resp = await self.client.post("/web/search", json={
            "query": "test"
        }, headers={"Authorization": f"Bearer {api_key}"})
        # May fail if no external network, but shouldn't be 401
        assert resp.status != 401

    # ── Metrics ──

    async def test_metrics(self):
        resp = await self.client.get("/metrics")
        assert resp.status == 200
        text = await resp.text()
        assert "relay_uptime_seconds" in text
        assert "relay_peers_online" in text


class TestRelayHelpers:
    def test_password_hash(self):
        from relay_server import _hash_password
        h1 = _hash_password("admin123")
        h2 = _hash_password("admin123")
        assert h1 == h2
        assert len(h1) == 64  # SHA256

    def test_ensure_accounts_default_admin(self):
        from relay_server import ACCOUNT_STORE, _ensure_accounts
        ACCOUNT_STORE.clear()
        _ensure_accounts()
        assert "admin" in ACCOUNT_STORE
        assert ACCOUNT_STORE["admin"]["is_admin"]

    def test_client_id_generation(self):
        from livingtree.capability.remote_assist import generate_client_id, get_client_id
        cid = generate_client_id()
        assert len(cid) == 10
        assert cid.isdigit()
