"""LiteLLM local configuration — local DeepSeek pricing in CNY.

Pricing source: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
DeepSeek-v4-pro 当前 2.5折，优惠至 2026-05-31。

不请求远程价格表 — 使用本地定价。
"""

import litellm

litellm.suppress_debug_info = True
litellm.local_model_cost_map = True

# DeepSeek official pricing (元/1M tokens)
DEEPSEEK_PRICING = {
    "deepseek/deepseek-v4-flash": {
        "input_cost_per_token": 1.0 / 1_000_000,
        "output_cost_per_token": 2.0 / 1_000_000,
        "max_tokens": 384_000,
        "litellm_provider": "deepseek",
        "mode": "chat",
    },
    "deepseek/deepseek-v4-pro": {
        "input_cost_per_token": 3.0 / 1_000_000,
        "output_cost_per_token": 6.0 / 1_000_000,
        "max_tokens": 384_000,
        "litellm_provider": "deepseek",
        "mode": "chat",
        "supports_reasoning": True,
    },
}

for model_id, pricing in DEEPSEEK_PRICING.items():
    try:
        litellm.register_model({model_id: pricing})
    except Exception:
        pass


def pricing_info() -> dict:
    """Return pricing summary in 元/1M tokens."""
    return {
        "deepseek-v4-flash": "输入 ¥1/M  输出 ¥2/M",
        "deepseek-v4-pro":  "输入 ¥3/M  输出 ¥6/M (2.5折，优惠至 2026-05-31)",
    }
