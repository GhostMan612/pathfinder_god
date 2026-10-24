# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .model import SemanticSpineError, normalize_vector


class OllamaEmbedder:
    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:11450",
        model: str = "embeddinggemma-2:270m",
        dimensions: int = 256,
        timeout_s: float = 120.0,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise SemanticSpineError("Ollama embeddings must use an explicit local loopback HTTP endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise SemanticSpineError("Ollama endpoint must be a bare loopback base URL")
        if dimensions not in (128, 256, 512, 768):
            raise SemanticSpineError("Invalid embedding dimensions")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout_s = timeout_s
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix

    def _request(self, path: str, data: dict | None = None) -> dict:
        body = None if data is None else json.dumps(data).encode("utf-8")
        request = Request(
            self.endpoint + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                result = json.load(response)
        except (HTTPError, URLError, ValueError, TimeoutError, OSError) as exc:
            raise SemanticSpineError(f"Local Ollama request failed: {type(exc).__name__}") from exc
        if not isinstance(result, dict):
            raise SemanticSpineError("Malformed Ollama response")
        return result

    def identity(self) -> str:
        payload = self._request("/api/tags")
        models = payload.get("models")
        if not isinstance(models, list):
            raise SemanticSpineError("Malformed Ollama tags response")
        for item in models:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            target = self.model
            matches = (
                name == target
                or (":" not in target and name == target + ":latest")
                or (target.endswith(":latest") and name == target[:-7])
            )
            if matches:
                digest = str(item.get("digest", ""))
                if len(digest) < 32:
                    raise SemanticSpineError("Ollama did not provide a usable model digest")
                return f"ollama:{name}@{digest}:d{self.dimensions}:q{self.query_prefix!r}:p{self.document_prefix!r}"
        raise SemanticSpineError("Requested embedding model is not installed locally")

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        if not texts:
            return []
        prefix = self.query_prefix if query else self.document_prefix
        payload = self._request(
            "/api/embed",
            {"model": self.model, "input": [prefix + text for text in texts], "dimensions": self.dimensions, "truncate": False},
        )
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise SemanticSpineError("Ollama returned an unexpected embedding batch")
        return [normalize_vector(vector, self.dimensions) for vector in vectors]
