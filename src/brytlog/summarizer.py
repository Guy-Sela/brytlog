"""
Sends crash output to LLMs using zero external dependencies.
"""

import json
import urllib.error
import sys
from . import config
from . import llm_client

DEFAULT_SYSTEM_PROMPT = """
You are an expert software engineer who's goal is to analyze crash logs and suggest fixes.

Be consice. Include only essential information.

Output Format (PLAIN TEXT ONLY - NO MARKDOWN, NO ASTERISKS):

[Single Problem Format - Use if there is only one distinct problem]:

Problem
[State what failed, where in the code and why (max 3 lines).]

Fix
[Suggest a fix, or next step for debugging if needed. If they are explicit in the log itself, cite them verbatim. (max 3 lines).]

[Multi-Problem Format - Use and repeat ONLY if there are multiple distinct problems]:

Problem 1:
...
Fix 1:
...
Problem 2:
...
Fix 2:
...
"""

def _call_google(prompt: str, model: str, api_key: str, system_prompt: str, temperature: float, max_tokens: int, client=None) -> str:
    if not api_key:
        return "⚠️  No API_KEY found. Set the API_KEY environment variable to use Google models."

    if client is None:
        client = llm_client.get_client()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = {
        "systemInstruction": {"parts": [{"text": system_prompt or DEFAULT_SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
    }

    try:
        res = client.post(url, data, {"Content-Type": "application/json"})
        if isinstance(res, dict) and "error" in res:
            message = res["error"].get("message", res["error"])
            return f"⚠️  Google API Error: {message}"

        if "candidates" not in res:
             return f"⚠️  Google API Error: Missing 'candidates' in response. Response: {res}"

        candidate = res["candidates"][0]

        text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        # Check if the response was blocked or unfinished
        if candidate.get("finishReason") not in (None, "STOP"):
            reason = candidate.get("finishReason")
            hint = ""
            if reason == "MAX_TOKENS":
                hint = "\nHint: The model ran out of tokens. If you're using a reasoning model, it may need a higher MAX_OUTPUT for 'thinking' tokens."
            return f"{text}\n\n⚠️  Report truncated by API (Reason: {reason}). The AI's response exceeded the allowed length.{hint}"

        return text
    except urllib.error.HTTPError as e:
        try:
            error_msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            error_msg = str(e)
        return f"⚠️  Google API Error ({e.code}): {error_msg}"
    except Exception as e:
        return f"⚠️  Google API Error: {str(e)}"


def _call_anthropic(prompt: str, model: str, api_key: str, system_prompt: str, temperature: float, max_tokens: int, client=None) -> str:
    if not api_key:
        return "⚠️  No API_KEY found. Set the API_KEY environment variable to use Anthropic models."

    if client is None:
        client = llm_client.get_client()

    url = "https://api.anthropic.com/v1/messages"
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt or DEFAULT_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    try:
        res = client.post(url, data, headers)
        if isinstance(res, dict) and "error" in res:
            message = res["error"].get("message", res["error"])
            return f"⚠️  Anthropic API Error: {message}"

        if "content" not in res:
             return f"⚠️  Anthropic API Error: Missing 'content' in response. Response: {res}"

        text = res["content"][0]["text"].strip()
        if res.get("stop_reason") == "max_tokens":
            hint = "\nHint: The model ran out of tokens. If you're using a reasoning model, it may need a higher MAX_OUTPUT for 'thinking' tokens."
            return f"{text}\n\n⚠️  Report truncated by API (Reason: max_tokens). The AI's response exceeded the allowed length.{hint}"
        return text
    except urllib.error.HTTPError as e:
        try:
            error_msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            error_msg = str(e)
        return f"⚠️  Anthropic API Error ({e.code}): {error_msg}"
    except Exception as e:
        return f"⚠️  Anthropic API Error: {str(e)}"


def _call_openai_compatible(prompt: str, model: str, api_key: str | None, base_url: str, system_prompt: str, temperature: float, max_tokens: int, client=None) -> str:
    if client is None:
        client = llm_client.get_client()

    url = f"{base_url.rstrip('/')}/chat/completions"
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        res = client.post(url, data, headers)
        if isinstance(res, dict) and "error" in res:
            message = res["error"].get("message", res["error"])
            return f"⚠️  API Error: {message}"
        if not isinstance(res, dict) or "choices" not in res or not res["choices"]:
            return "⚠️  API Error: Missing 'choices' in response"
        text = res["choices"][0]["message"]["content"].strip()
        if res["choices"][0].get("finish_reason") == "length":
            hint = "\nHint: The model ran out of tokens. If you're using a reasoning model, it may need a higher MAX_OUTPUT for 'thinking' tokens."
            return f"{text}\n\n⚠️  Report truncated by API (Reason: length). The AI's response exceeded the allowed length.{hint}"
        return text
    except urllib.error.HTTPError as e:
        try:
            error_msg = e.read().decode("utf-8", errors="replace")
        except Exception:
            error_msg = str(e)
        return f"⚠️  API Error ({e.code}): {error_msg}"
    except Exception as e:
        return f"⚠️  API Error: {str(e)}"


def summarize_success(
    command: str,
    payload: str,
    provider: str,
    model: str,
    api_key: str | None,
    api_base_url: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_output: int = 1000,
    client=None
) -> str:
    user_message = f"Command:\n```bash\n{command}\n```\n\nLog Extract:\n```\n{payload}\n```"

    max_tokens = max(8192, int(max_output * 5))

    success_system_prompt = (
        "You are an expert software engineer analyzing the logs of a command that executed successfully "
        "but produced warnings or notices.\n\n"
        "Summarize the state, warnings, and any skipped tasks in 2-3 short bullet points. "
        "Keep it concise. Do NOT include markdown code blocks or asterisks. "
        "Start directly with the bullet points (using '-' as bullet)."
    )

    try:
        if provider == "google":
            return _call_google(user_message, model, api_key, success_system_prompt, temperature, max_tokens, client=client)
        elif provider == "anthropic":
            return _call_anthropic(user_message, model, api_key, success_system_prompt, temperature, max_tokens, client=client)
        else:
            if not api_base_url:
                api_base_url = config.KNOWN_PROVIDERS.get(provider)
            if not api_base_url:
                return f"⚠️  Unknown provider '{provider}' and no API_BASE_URL provided. Please set it via environment variables or flags."
            return _call_openai_compatible(user_message, model, api_key, api_base_url, success_system_prompt, temperature, max_tokens, client=client)
    except Exception as e:
        return f"⚠️  LLM report failed: {e}"

def summarize_crash(
    command: str,
    output: str,
    provider: str,
    model: str,
    api_key: str | None,
    api_base_url: str | None = None,
    system_prompt: str = "",
    temperature: float = 0.2,
    max_output: int = 1000,
    client=None
) -> str:
    user_message = f"Command:\n```bash\n{command}\n```\n\nOutput:\n```\n{output}\n```"

    # Token management:
    # 1. Provide a generous token ceiling so reasoning models have room to think,
    #    and to accommodate multiple distinct problems.
    # 2. Enforce conciseness per-problem via the prompt itself.
    max_tokens = max(8192, int(max_output * 5))

    system_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT) + f"\n\nCRITICAL: Keep your analysis concise. Limit your response to approximately {max_output} tokens per distinct problem identified."

    try:
        if provider == "google":
            return _call_google(user_message, model, api_key, system_prompt, temperature, max_tokens, client=client)
        elif provider == "anthropic":
            return _call_anthropic(user_message, model, api_key, system_prompt, temperature, max_tokens, client=client)
        else:
            # Resolve base URL from known providers if not explicitly set
            if not api_base_url:
                api_base_url = config.KNOWN_PROVIDERS.get(provider)

            if not api_base_url:
                return f"⚠️  Unknown provider '{provider}' and no API_BASE_URL provided. Please set it via environment variables or flags."

            return _call_openai_compatible(user_message, model, api_key, api_base_url, system_prompt, temperature, max_tokens, client=client)
    except Exception as e:
        return f"⚠️  LLM report failed: {e}"
