from __future__ import annotations

import argparse
import json
from typing import Any

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - convenience guard for local manual use
    raise SystemExit(
        "Missing dependency: openai. Install it with `pip install openai` before running this script."
    ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test tenant public chat API with OpenAI-compatible request format."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost/api/v1/public/v1",
        help="Public API base URL, for example: https://your-domain/api/v1/public/v1",
    )
    parser.add_argument("--api-key", required=True, help="Tenant API key")
    parser.add_argument("--message", required=True, help="End-user message sent to the chatbot")
    parser.add_argument("--model", default="chatbot-rag", help="Model name exposed by public API")
    parser.add_argument("--stream", action="store_true", help="Enable SSE streaming")
    parser.add_argument("--thinking-mode", action="store_true", help="Enable thinking mode markers in streaming")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=float, default=180.0)
    return parser


def print_stream(completion) -> None:
    citations: list[dict[str, Any]] = []
    usage: dict[str, Any] = {}

    for chunk in completion:
        data = chunk.model_dump()
        if data.get("thinking") is True:
            print("\n[thinking:start]\n", end="")
            continue
        if data.get("thinking") is False:
            print("\n[thinking:end]\n", end="")
            continue
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        delta = ((choice.get("delta") or {}).get("content")) or ""
        if delta:
            print(delta, end="", flush=True)

        if data.get("citations"):
            citations = list(data.get("citations") or [])
        if data.get("usage"):
            usage = dict(data.get("usage") or {})

    print("\n")
    print("=== Citations ===")
    print(json.dumps(citations, ensure_ascii=False, indent=2))
    print("=== Usage ===")
    print(json.dumps(usage, ensure_ascii=False, indent=2))


def print_non_stream(data: dict[str, Any]) -> None:
    choices = data.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    content = message.get("content") or ""
    citations = data.get("citations") or []
    usage = data.get("usage") or {}

    print(content)
    print("\n=== Citations ===")
    print(json.dumps(citations, ensure_ascii=False, indent=2))
    print("=== Usage ===")
    print(json.dumps(usage, ensure_ascii=False, indent=2))


def main() -> int:
    args = build_parser().parse_args()
    client = OpenAI(base_url=args.base_url, api_key=args.api_key, timeout=args.timeout)
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.message}],
        "stream": args.stream,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    if args.thinking_mode:
        payload["extra_body"] = {"thinking_mode": True}

    completion = client.chat.completions.create(**payload)
    if args.stream:
        print_stream(completion)
        return 0

    print_non_stream(completion.model_dump())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
