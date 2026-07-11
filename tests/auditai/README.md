# AuditAI smoke suite (optional)

Optional RAG quality / safety checks using [AuditAI](https://github.com/iZenDeveloper/auditai).

Dataset questions are derived from this repo’s **public README** (faithfulness, relevancy, prompt-injection probes).

## Quick start (offline mock judge)

```bash
pip install "git+https://github.com/iZenDeveloper/auditai.git@v0.1.0"

# terminal 1 — README-grounded mock HTTP target
python tests/auditai/mock_adapter.py

# terminal 2
auditai run --config tests/auditai/auditai.yml
# reports → tests/auditai/auditai-out/
```

## Real LLM-as-judge (BYOK)

Edit `auditai.yml`:

```yaml
judge:
  provider: xai          # or openai
  model: grok-4.3        # or gpt-4o-mini
```

```bash
export XAI_API_KEY=...   # or OPENAI_API_KEY
python tests/auditai/mock_adapter.py &
auditai run --config tests/auditai/auditai.yml
```

## Point at the real stack

When the FastAPI chat API is up, set `target.url` to your OpenAI-compatible endpoint (e.g. `POST /v1/chat/completions`) and adjust `body_template` / `response_map` if needed.

## CI

Copy `workflow-auditai.yml.example` → `.github/workflows/auditai.yml` if you want opt-in CI. It is **`workflow_dispatch` only** (no automatic PR gate) until you opt in and uncomment the Action step + secrets.
