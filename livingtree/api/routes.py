    @app.post("/api/layers/save")
    async def save_layer_config(request: Request):
        """Save 3-layer provider configuration from frontend."""
        try:
            data = await request.json()
            from ..treellm.sticky_election import get_layer_config
            mgr = get_layer_config()
            layer_map = {"vector": 0, "fast": 1, "reasoning": 2}
            for name, cfg in data.items():
                if name in layer_map:
                    mgr.set_layer(
                        layer_map[name],
                        provider=cfg.get("provider", ""),
                        model=cfg.get("model", ""),
                        api_key=cfg.get("api_key", ""),
                    )
            return mgr.get_all()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/layers/reset")
    async def reset_layer_config():
        """Reset layer config to defaults."""
        from ..treellm.sticky_election import get_layer_config
        import json
        defaults = {"0": {"provider":"siliconflow","model":"BAAI/bge-large-zh-v1.5"},
                    "1": {"provider":"deepseek","model":"deepseek-v4-flash"},
                    "2": {"provider":"deepseek","model":"deepseek-v4-pro"}}
        Path(".livingtree/layer_config.json").write_text(json.dumps(defaults, indent=2))
        mgr = get_layer_config()
        mgr._load()
        return mgr.get_all()