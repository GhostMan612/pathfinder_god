# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""LLM backends with graceful 3-tier fallback."""

from .backends import LLMResult, LLMRouter
from .gateway import LlmGateway, get_gateway

__all__ = ["LLMResult", "LLMRouter", "LlmGateway", "get_gateway"]
