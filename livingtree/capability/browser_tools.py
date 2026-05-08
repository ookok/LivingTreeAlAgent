"""Browser Tools — 浏览器能力注册为 ToolMarket 动态工具。

不硬编码流程。每个工具是独立的原子能力，由 LLM 意识层
通过 ToolMarket.discover() 发现后自主编排组合。

遵循自治学习原则:
  - 工具只描述能力，不规定调用顺序
  - LLM 根据目标动态选择工具链
  - 成功的工具链可被进化系统记忆复用
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger


# ═══════════════════════════════════════════════════════════════
#  Handler functions — thin wrappers, delegate to existing components
# ═══════════════════════════════════════════════════════════════


def _get_browser_adapter() -> Any:
    """Lazy import BrowserUseAdapter from client package.

    Returns None if browser gateway not available (graceful degradation).
    Auto-detects scinet proxy (localhost:7890) for overseas site access.
    """
    try:
        import sys
        client_root = Path(__file__).parent.parent.parent / "client" / "src" / "business" / "living_tree_ai"
        if str(client_root) not in sys.path:
            sys.path.insert(0, str(client_root))
        from browser_gateway.browser_use_adapter import BrowserUseAdapter
        from browser_gateway.browser_pool import get_browser_pool
        adapter = BrowserUseAdapter()
        pool = get_browser_pool()
        # Auto-detect scinet proxy for overseas access
        if not pool.proxy_url:
            _auto_set_scinet_proxy(pool)
        return adapter, pool
    except Exception as e:
        logger.debug("Browser gateway unavailable: %s", e)
        return None, None


def _auto_set_scinet_proxy(pool: Any) -> None:
    """Auto-detect scinet (localhost:7890) and set proxy on BrowserPool."""
    try:
        from livingtree.network.scinet_service import get_scinet
        scinet = get_scinet()
        if getattr(scinet.status, "running", False):
            pool.proxy_url = "http://127.0.0.1:7890"
            logger.info("Browser proxy auto-set → scinet (localhost:7890)")
    except Exception:
        pass


def _get_identity_pool() -> Any:
    """Lazy import IdentityPool from enterprise_os."""
    try:
        import sys
        client_root = Path(__file__).parent.parent.parent / "client" / "src" / "business" / "living_tree_ai"
        if str(client_root) not in sys.path:
            sys.path.insert(0, str(client_root))
        from enterprise_os.identity_pool import IdentityPool
        return IdentityPool()
    except Exception as e:
        logger.debug("IdentityPool unavailable: %s", e)
        return None


async def _browser_navigate(params: dict, world: Any = None) -> dict:
    """Navigate browser to a URL."""
    url = params.get("url", "")
    if not url:
        return {"error": "url required"}
    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available", "navigated": False, "url": url}
    try:
        session = await pool.get_session()
        await adapter.navigate(url)
        return {"navigated": True, "url": url, "session_id": session.session_id if session else ""}
    except Exception as e:
        return {"error": str(e), "navigated": False, "url": url}


async def _browser_login(params: dict, world: Any = None) -> dict:
    """Autonomous login on a website.

    LLM-driven: adapter.execute_task("login to the website with given credentials")
    Credentials auto-retrieved from IdentityPool if not explicitly provided.
    """
    url = params.get("url", "")
    username = params.get("username", "")
    password = params.get("password", "")
    site = params.get("site", "")  # e.g. "环保", "市场监管"

    if not url:
        return {"error": "url required"}

    # Auto-retrieve credentials from IdentityPool
    if not username and site:
        ip = _get_identity_pool()
        if ip:
            creds = ip.get(site)
            if creds:
                username = creds.get("username", "")
                password = creds.get("password", "")

    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available", "logged_in": False}

    try:
        task = f"Navigate to {url} and log in"
        if username:
            task += f" with username '{username}' and password '{password}'"
        result = await adapter.execute_task(task)
        logged_in = "success" in str(result).lower() or "登录成功" in str(result)

        # Save credentials for future use
        if logged_in and username and site:
            ip = _get_identity_pool()
            if ip:
                ip.set(site, username=username, password=password)

        return {"logged_in": logged_in, "site": site or url, "result": str(result)[:500]}
    except Exception as e:
        return {"error": str(e), "logged_in": False}


async def _browser_fill_form(params: dict, world: Any = None) -> dict:
    """Autonomous form filling.

    LLM-driven: identifies form fields and fills them.
    Data can come from params or from EIA/document extracts.
    """
    url = params.get("url", "")
    data = params.get("data", {})
    description = params.get("description", "")  # LLM-friendly description of what to fill

    if not url:
        return {"error": "url required"}

    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available", "filled": False}

    try:
        if data:
            result = await adapter.fill_form(url, data)
        elif description:
            task = f"On {url}, {description}. Fill all visible form fields."
            result = await adapter.execute_task(task)
        else:
            return {"error": "data or description required"}

        return {"filled": True, "url": url, "result": str(result)[:500]}
    except Exception as e:
        return {"error": str(e), "filled": False}


async def _browser_extract(params: dict, world: Any = None) -> dict:
    """Extract content from a page. LLM can request specific selectors or natural language."""
    url = params.get("url", "")
    selector = params.get("selector", "")
    query = params.get("query", "")  # natural language: "find the emission limits table"

    if not url:
        return {"error": "url required"}

    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available", "extracted": False}

    try:
        if selector:
            content = await adapter.extract_content(url, selector)
        elif query:
            task = f"On {url}, extract: {query}"
            content = await adapter.execute_task(task)
        else:
            content = await adapter.extract_content(url)

        return {"extracted": True, "url": url, "content": str(content)[:3000]}
    except Exception as e:
        return {"error": str(e), "extracted": False}


async def _browser_screenshot(params: dict, world: Any = None) -> dict:
    """Capture page screenshot for visual analysis."""
    url = params.get("url", "")
    if not url:
        return {"error": "url required"}

    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available"}

    try:
        result = await adapter.screenshot(url)
        return {"screenshot": True, "url": url, "path": str(result) if result else ""}
    except Exception as e:
        return {"error": str(e)}


async def _browser_search(params: dict, world: Any = None) -> dict:
    """Search the web via browser."""
    query = params.get("query", "")
    if not query:
        return {"error": "query required"}

    adapter, pool = _get_browser_adapter()
    if not adapter:
        return {"error": "Browser gateway not available"}

    try:
        result = await adapter.execute_task(f"Search for: {query}")
        return {"search": True, "query": query, "result": str(result)[:2000]}
    except Exception as e:
        return {"error": str(e)}


async def _credential_store(params: dict, world: Any = None) -> dict:
    """Store credentials for a site in IdentityPool (encrypted)."""
    site = params.get("site", "")
    username = params.get("username", "")
    password = params.get("password", "")
    if not site or not username or not password:
        return {"error": "site, username, password required"}

    ip = _get_identity_pool()
    if not ip:
        return {"error": "IdentityPool not available", "stored": False}

    try:
        ip.set(site, username=username, password=password)
        return {"stored": True, "site": site}
    except Exception as e:
        return {"error": str(e), "stored": False}


async def _credential_retrieve(params: dict, world: Any = None) -> dict:
    """Retrieve stored credentials from IdentityPool."""
    site = params.get("site", "")
    if not site:
        return {"error": "site required"}

    ip = _get_identity_pool()
    if not ip:
        return {"error": "IdentityPool not available"}

    try:
        creds = ip.get(site)
        if creds:
            return {"found": True, "site": site, "username": creds.get("username", "")}
        return {"found": False, "site": site}
    except Exception as e:
        return {"error": str(e), "found": False}


# ═══════════════════════════════════════════════════════════════
#  Registration — called by ToolMarket.register_seed_tools()
# ═══════════════════════════════════════════════════════════════


def register_browser_tools(market: Any) -> None:
    """Register browser capabilities as dynamic tools.

    Called by ToolMarket during seed tool registration.
    LLM discovers these via market.discover() and orchestrates.
    """

    market.register(
        "browser_navigate",
        "Navigate browser to a URL. Use before login/fill/extract.",
        category="browser",
        handler=_browser_navigate,
        input_schema={"url": "string"},
    )

    market.register(
        "browser_login",
        "Autonomous login on a website. Auto-retrieves credentials from IdentityPool if available.",
        category="browser",
        handler=_browser_login,
        input_schema={"url": "string", "site": "string",
                      "username": "string", "password": "string"},
    )

    market.register(
        "browser_fill_form",
        "Autonomous form filling. Provide data dict or natural language description.",
        category="browser",
        handler=_browser_fill_form,
        input_schema={"url": "string", "data": "json", "description": "string"},
    )

    market.register(
        "browser_extract",
        "Extract content from a page. Use CSS selector or natural language query.",
        category="browser",
        handler=_browser_extract,
        input_schema={"url": "string", "selector": "string", "query": "string"},
    )

    market.register(
        "browser_screenshot",
        "Capture a screenshot of a web page.",
        category="browser",
        handler=_browser_screenshot,
        input_schema={"url": "string"},
    )

    market.register(
        "browser_search",
        "Search the web via browser automation.",
        category="browser",
        handler=_browser_search,
        input_schema={"query": "string"},
    )

    market.register(
        "credential_store",
        "Securely store login credentials for a site (encrypted).",
        category="identity",
        handler=_credential_store,
        input_schema={"site": "string", "username": "string", "password": "string"},
    )

    market.register(
        "credential_retrieve",
        "Retrieve stored credentials for a site from IdentityPool.",
        category="identity",
        handler=_credential_retrieve,
        input_schema={"site": "string"},
    )

    logger.info("Browser tools registered (%d tools)", 8)
