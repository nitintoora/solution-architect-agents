import os
import time
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 8192,
    model: str | None = None,
    retries: int = 3,
    retry_delay: float = 5.0,
) -> str:
    """Call Claude and return the response text.

    Retries on transient API errors with a fixed delay. Raises on permanent
    failures (auth errors, invalid requests) without retrying.

    Args:
        model: Model ID override. If None, falls back to ANTHROPIC_MODEL env var,
               then to claude-opus-4-6. Agents pass their own model for cost tiering.
    """
    effective_model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    client = _get_client()

    for attempt in range(1, retries + 1):
        try:
            message = client.messages.create(
                model=effective_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return message.content[0].text
        except anthropic.AuthenticationError:
            raise
        except anthropic.BadRequestError:
            raise
        except anthropic.APIError as exc:
            if attempt == retries:
                raise
            print(f"  API error (attempt {attempt}/{retries}): {exc} — retrying in {retry_delay}s")
            time.sleep(retry_delay)

    # Unreachable, but satisfies type checkers
    raise RuntimeError("call_claude: exhausted retries")
