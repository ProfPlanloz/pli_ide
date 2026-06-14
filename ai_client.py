"""AI integration for debugging and code generation.

Supported providers (selectable in the configuration):
  - 'ollama':    local Ollama (no API key needed), default port 11434
  - 'anthropic': Anthropic API (Claude), API key required
  - 'openai':    OpenAI-compatible APIs (OpenAI, Groq, Mistral, LM Studio, ...)

Uses the standard library only (urllib) — no extra dependencies needed.
"""

import json
import re
import urllib.error
import urllib.request

from i18n import t

REQUEST_TIMEOUT = 180  # seconds — local models can be slow

PROVIDER_DEFAULTS = {
    "ollama": {"model": "llama3.2", "base_url": "http://localhost:11434"},
    "anthropic": {"model": "claude-sonnet-4-6", "base_url": "https://api.anthropic.com"},
    "openai": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
}

CODE_BLOCK = re.compile(r"```[^\n`]*\n(.*?)```", re.DOTALL)


class AIError(Exception):
    """Human-readable error message for display in the dialog."""


def extract_code_blocks(text):
    """Extract the contents of all ``` code blocks from an AI reply."""
    return [m.group(1).rstrip("\n") for m in CODE_BLOCK.finditer(text)]


class AIClient:
    def __init__(self, config):
        self.config = config

    # ------------------------------------------------------------- public

    def describe_backend(self):
        provider = (self.config.get("ai_provider") or "ollama").lower()
        model = self.config.get("ai_model") or "?"
        return f"{provider} / {model}"

    def chat(self, system_prompt, user_prompt):
        """Send a request to the configured backend.
        Returns the reply text or raises AIError."""
        provider = (self.config.get("ai_provider") or "ollama").lower()
        if provider == "ollama":
            return self._chat_ollama(system_prompt, user_prompt)
        if provider == "anthropic":
            return self._chat_anthropic(system_prompt, user_prompt)
        if provider == "openai":
            return self._chat_openai(system_prompt, user_prompt)
        raise AIError(t("ai.unknown_provider", provider=provider))

    # ------------------------------------------------------------ backends

    def _chat_ollama(self, system_prompt, user_prompt):
        base = (self.config.get("ai_base_url") or PROVIDER_DEFAULTS["ollama"]["base_url"]).rstrip("/")
        model = self.config.get("ai_model") or PROVIDER_DEFAULTS["ollama"]["model"]
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            data = self._post_json(f"{base}/api/chat", payload, {})
        except AIError as e:
            raise AIError(t("ai.ollama_hint", error=str(e), model=model)) from e

        content = (data.get("message") or {}).get("content", "")
        if not content:
            raise AIError(t("ai.empty_response", provider="Ollama", detail=json.dumps(data)[:300]))
        return content

    def _chat_anthropic(self, system_prompt, user_prompt):
        key = self.config.get("ai_api_key")
        if not key:
            raise AIError(t("ai.no_key"))
        base = (self.config.get("ai_base_url") or PROVIDER_DEFAULTS["anthropic"]["base_url"]).rstrip("/")
        model = self.config.get("ai_model") or PROVIDER_DEFAULTS["anthropic"]["model"]
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        data = self._post_json(f"{base}/v1/messages", payload, headers)

        parts = [block.get("text", "") for block in data.get("content", [])
                 if block.get("type") == "text"]
        content = "\n".join(p for p in parts if p)
        if not content:
            raise AIError(t("ai.empty_response", provider="Anthropic", detail=json.dumps(data)[:300]))
        return content

    def _chat_openai(self, system_prompt, user_prompt):
        key = self.config.get("ai_api_key")
        base = (self.config.get("ai_base_url") or PROVIDER_DEFAULTS["openai"]["base_url"]).rstrip("/")
        model = self.config.get("ai_model") or PROVIDER_DEFAULTS["openai"]["model"]
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        # Local OpenAI-compatible servers (e.g. LM Studio) need no key
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        data = self._post_json(f"{base}/chat/completions", payload, headers)

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AIError(t("ai.unexpected_response", detail=json.dumps(data)[:300]))
        if not content:
            raise AIError(t("ai.empty_response", provider="OpenAI", detail=""))
        return content

    # ------------------------------------------------------------- internal

    @staticmethod
    def _post_json(url, payload, headers):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        for key, value in headers.items():
            request.add_header(key, value)

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                detail = ""
            raise AIError(t("ai.http_error", code=e.code, url=url, detail=detail)) from e
        except urllib.error.URLError as e:
            raise AIError(t("ai.no_connection", url=url, reason=e.reason)) from e
        except TimeoutError as e:
            raise AIError(t("ai.timeout", url=url, seconds=REQUEST_TIMEOUT)) from e
        except json.JSONDecodeError as e:
            raise AIError(t("ai.invalid_json", url=url, error=e)) from e
