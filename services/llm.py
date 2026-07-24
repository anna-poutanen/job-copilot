"""Thin wrapper around the Anthropic Messages API."""
import anthropic
import config


class LLMNotConfigured(RuntimeError):
    pass


def _client():
    if not config.ANTHROPIC_API_KEY:
        raise LLMNotConfigured(
            "No Anthropic API key found. Add ANTHROPIC_API_KEY to your .env file."
        )
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def generate(system: str, prompt: str, max_tokens: int = 1200, temperature: float = 0.6) -> str:
    """Single-shot text generation. Raises LLMNotConfigured if no key is set."""
    client = _client()
    resp = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text").strip()
