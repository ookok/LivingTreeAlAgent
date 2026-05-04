"""DeepSeek pricing config — local pricing in CNY.

Pricing source: https://api-docs.deepseek.com/zh-cn/quick_start/pricing
DeepSeek-v4-pro currently 75% discount until 2026-05-31.
No litellm dependency — standalone pricing data for cost tracking.
"""

# DeepSeek official pricing (元/1M tokens)
DEEPSEEK_PRICING = {
    "deepseek-v4-flash": {
        "input_cost_per_1m": 1.0,
        "output_cost_per_1m": 2.0,
        "max_tokens": 384_000,
    },
    "deepseek-v4-pro": {
        "input_cost_per_1m": 3.0,
        "output_cost_per_1m": 6.0,
        "max_tokens": 384_000,
        "supports_reasoning": True,
    },
}


def pricing_info() -> dict:
    """Return pricing summary in 元/1M tokens."""
    return {
        "deepseek-v4-flash": "输入 ¥1/M  输出 ¥2/M",
        "deepseek-v4-pro":  "输入 ¥3/M  输出 ¥6/M (2.5折，优惠至 2026-05-31)",
    }
