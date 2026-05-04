"""OpenCode Bridge — Discover and use opencode's LLM credentials in LivingTree.

Reads ~/.opencode/config.toml to extract any configured LLM providers
(API keys, base URLs, models). Adds them to LivingTree's auto-election
pool so LivingTree can use opencode's free/paid LLM access transparently.

Also reads ~/.opencode/credentials.json or env-based credentials.

Usage:
    bridge = OpenCodeBridge()
    providers = bridge.discover_providers()
    # → [{"name": "opencode-deepseek", "api_key": "sk-...", "base_url": "..."}, ...]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class OpenCodeBridge:
    """Discovers opencode's LLM credentials for LivingTree to use."""

    CONFIG_PATHS = [
        Path.home() / ".opencode" / "config.toml",
        Path.home() / ".opencode" / "config.json",
        Path.home() / ".config" / "opencode" / "config.toml",
        Path.home() / ".local" / "share" / "opencode" / "auth.json",
    ]

    def discover_providers(self) -> list[dict[str, Any]]:
        providers = []

        for config_path in self.CONFIG_PATHS:
            if not config_path.exists():
                continue

            discovered = self._parse_config(config_path)
            if discovered:
                providers.extend(discovered)
                logger.debug(f"OpenCode bridge: found {len(discovered)} providers from {config_path}")

        providers += self._parse_env_credentials()
        return providers

    async def discover_for_election(self) -> list[dict[str, Any]]:
        providers = self.discover_providers()
        models = []

        for p in providers:
            api_key = p.get("api_key", "")
            base_url = p.get("base_url", "")
            model = p.get("model", "")

            if api_key and "livingtree" not in str(base_url).lower():
                if not model:
                    model = self._guess_model(p.get("name", ""), base_url)

                models.append({
                    "name": f"opencode-{p.get('name', 'unknown')}",
                    "model": model,
                    "api_key": api_key,
                    "base_url": base_url,
                    "source": "opencode_bridge",
                })

        serve_models = await self._discover_serve()
        models.extend(serve_models)

        if models:
            logger.info(f"OpenCode bridge: {len(models)} models available for election")

        return models

    async def _discover_serve(self) -> list[dict[str, Any]]:
        try:
            from .opencode_serve import discover_opencode_serve
            serve_info = await discover_opencode_serve()
            if serve_info:
                return [{
                    "name": "opencode-serve",
                    "model": "opencode-serve",
                    "api_key": "",
                    "base_url": serve_info["base_url"],
                    "source": "opencode_serve",
                }]
        except Exception:
            pass
        return []

    def get_best_provider(self) -> dict[str, Any] | None:
        providers = self.discover_for_election()
        return providers[0] if providers else None

    # ── Private ──

    def _parse_config(self, path: Path) -> list[dict[str, Any]]:
        if path.suffix == ".toml":
            return self._parse_toml(path)
        elif path.suffix == ".json":
            return self._parse_json(path)
        return []

    def _parse_toml(self, path: Path) -> list[dict[str, Any]]:
        if tomllib is None:
            return self._parse_toml_fallback(path)

        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        providers = []

        model_section = data.get("model", {})
        if model_section:
            api_key = model_section.get("api_key", "")
            base_url = model_section.get("base_url", "")
            model_val = model_section.get("model", "")
            provider_name = model_section.get("provider", "")
            if api_key and api_key != "livingtree-local":
                providers.append({
                    "name": provider_name or "default",
                    "api_key": api_key,
                    "base_url": base_url,
                    "model": model_val,
                })

        providers_section = data.get("providers", {})
        if isinstance(providers_section, dict):
            for name, section in providers_section.items():
                if isinstance(section, dict):
                    api_key = section.get("api_key", "")
                    base_url = section.get("base_url", "")
                    model_val = section.get("model", "")
                    if api_key and api_key != "livingtree-local":
                        providers.append({
                            "name": name,
                            "api_key": api_key,
                            "base_url": base_url or "",
                            "model": model_val,
                        })

        return providers

    def _parse_toml_fallback(self, path: Path) -> list[dict[str, Any]]:
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []

        providers = []
        current_section = None
        current_data = {}

        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                if current_section and current_data.get("api_key"):
                    if current_data.get("api_key") != "livingtree-local":
                        providers.append({
                            "name": current_section,
                            "api_key": current_data.get("api_key", ""),
                            "base_url": current_data.get("base_url", ""),
                            "model": current_data.get("model", ""),
                        })
                current_section = line[1:-1].strip()
                current_data = {}
            elif "=" in line and current_section is not None:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                current_data[key] = val

        if current_section and current_data.get("api_key"):
            if current_data.get("api_key") != "livingtree-local":
                providers.append({
                    "name": current_section,
                    "api_key": current_data.get("api_key", ""),
                    "base_url": current_data.get("base_url", ""),
                    "model": current_data.get("model", ""),
                })

        return providers

    def _parse_json(self, path: Path) -> list[dict[str, Any]]:
        import json
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        providers = []

        if path.name == "auth.json":
            return self._parse_auth_json(data)

        if isinstance(data, dict):
            for key, section in data.items():
                if isinstance(section, dict) and section.get("api_key"):
                    providers.append({
                        "name": key,
                        "api_key": section.get("api_key", ""),
                        "base_url": section.get("base_url", ""),
                        "model": section.get("model", ""),
                    })

            providers_section = data.get("providers", {})
            if isinstance(providers_section, dict):
                for name, section in providers_section.items():
                    if isinstance(section, dict):
                        api_key = section.get("api_key", "")
                        if api_key and api_key != "livingtree-local":
                            providers.append({
                                "name": name,
                                "api_key": api_key,
                                "base_url": section.get("base_url", ""),
                                "model": section.get("model", ""),
                            })

        return providers

    def _parse_auth_json(self, data: dict) -> list[dict[str, Any]]:
        providers = []
        if isinstance(data, dict):
            for provider_name, auth in data.items():
                if isinstance(auth, dict):
                    api_key = auth.get("api_key") or auth.get("key") or auth.get("token") or ""
                    base_url = auth.get("base_url") or auth.get("api_base") or ""
                    model = auth.get("model") or auth.get("default_model") or ""
                    if api_key:
                        providers.append({
                            "name": provider_name,
                            "api_key": api_key,
                            "base_url": base_url,
                            "model": model,
                        })

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    api_key = item.get("api_key") or item.get("key") or ""
                    provider = item.get("provider") or item.get("name") or "unknown"
                    model = item.get("model") or item.get("default_model") or ""
                    base_url = item.get("base_url") or item.get("api_base") or ""
                    if api_key:
                        providers.append({
                            "name": provider,
                            "api_key": api_key,
                            "base_url": base_url,
                            "model": model,
                        })

        return providers

    def _parse_env_credentials(self) -> list[dict[str, Any]]:
        import os
        providers = []

        env_providers = [
            ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-v4-flash"),
            ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1", "claude-sonnet-4-20250514"),
            ("LONGCAT_API_KEY", "https://api.longcat.chat/openai/v1", "LongCat-Flash-Lite"),
            ("GOOGLE_API_KEY", "https://generativelanguage.googleapis.com/v1beta", "gemini-2.5-flash"),
        ]

        for env_key, base_url, model in env_providers:
            val = os.environ.get(env_key, "")
            if val:
                providers.append({
                    "name": env_key.lower().replace("_api_key", ""),
                    "api_key": val,
                    "base_url": base_url,
                    "model": model,
                })

        return providers

    @staticmethod
    def _guess_model(name: str, base_url: str) -> str:
        url_lower = base_url.lower()
        name_lower = name.lower()

        if "deepseek" in url_lower or "deepseek" in name_lower:
            return "deepseek-v4-flash"
        if "openai" in url_lower:
            return "gpt-4o-mini"
        if "anthropic" in url_lower or "claude" in name_lower:
            return "claude-sonnet-4-20250514"
        if "longcat" in url_lower:
            return "LongCat-Flash-Lite"
        if "gemini" in url_lower or "google" in url_lower:
            return "gemini-2.5-flash"

        return "gpt-4o-mini"
