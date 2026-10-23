"""Ollama client for local AI inference with health checks, retries, and privacy guards."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import urllib.error

from relationship_analyst.config import OLLAMA_DEFAULT_HOST, OLLAMA_MAX_RETRIES, OLLAMA_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Base exception for Ollama errors."""
    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when Ollama cannot be reached."""
    pass


class OllamaModelNotFoundError(OllamaClientError):
    """Raised when the specified model is not installed locally."""
    pass


class OllamaClient:
    """Client for local Ollama HTTP API with local-only privacy guarantee."""

    def __init__(self, host: str = OLLAMA_DEFAULT_HOST, timeout: int = OLLAMA_TIMEOUT_SECONDS):
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._verify_local_host(self.host)

    def _verify_local_host(self, host: str) -> None:
        """Enforce privacy constraint: inference host must be local."""
        parsed = urllib.parse.urlparse(host)
        hostname = (parsed.hostname or "").lower()
        if hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ValueError(
                f"Privacy violation: Host '{host}' is not a local address. "
                "Local Relationship Analyst strictly forbids remote AI endpoints."
            )

    def check_health(self) -> Dict[str, Any]:
        """Check if Ollama service is running and return version / status."""
        url = f"{self.host}/api/version"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "ok", "version": data.get("version", "unknown")}
        except urllib.error.URLError as e:
            return {"status": "error", "message": f"Cannot connect to Ollama at {self.host}: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_local_models(self) -> List[str]:
        """Retrieve list of available local models."""
        url = f"{self.host}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                return models
        except urllib.error.URLError as e:
            raise OllamaConnectionError(
                f"Could not reach Ollama at {self.host}. Is Ollama installed and running? ({e})"
            )
        except Exception as e:
            raise OllamaClientError(f"Error listing models: {str(e)}")

    def generate_json(
        self,
        model: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_retries: int = OLLAMA_MAX_RETRIES,
        think: bool = False,
    ) -> str:
        """
        Request JSON generation from local Ollama model with bounded retries.
        Returns the raw string output from the model.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt or "You are an analytical assistant. You must respond in valid JSON only.",
            "stream": False,
            "format": "json",
            "think": think,
            "options": {
                "temperature": temperature,
            },
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=body_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    raw_response = resp_data.get("response", "")
                    if not raw_response.strip():
                        raise OllamaClientError("Model returned an empty response.")
                    return raw_response

            except urllib.error.HTTPError as he:
                if he.code == 404:
                    raise OllamaModelNotFoundError(
                        f"Model '{model}' not found in Ollama. Run 'ollama pull {model}' to install it."
                    )
                err_body = ""
                try:
                    err_body = he.read().decode("utf-8")
                except Exception:
                    pass
                last_error = OllamaClientError(f"HTTP Error {he.code}: {he.reason} - {err_body}")
            except (urllib.error.URLError, TimeoutError) as ue:
                last_error = OllamaConnectionError(f"Connection or timeout error (attempt {attempt}/{max_retries}): {ue}")
            except Exception as e:
                last_error = e

            if attempt < max_retries:
                time.sleep(1.5 * attempt)

        raise OllamaClientError(f"Failed to generate output after {max_retries} attempts: {last_error}")
