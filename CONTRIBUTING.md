# Contributing Guide

Thank you for contributing to `chatbot-rag`.

## Ground Rules

- Be respectful and constructive.
- Follow project architecture and guardrails in [`AGENTS.md`](AGENTS.md).
- Do not introduce hardcoded secrets, fake fixes, or bypass logic.
- Keep changes focused and production-safe.

## Development Setup

1. Fork the repository and clone your fork.
2. Create a branch from `main`:
   - `feat/<name>` for features
   - `fix/<name>` for bug fixes
3. Start the stack locally:

```bash
cp .env.example .env
DOCKER_BUILDKIT=1 docker compose up -d --build
```

## Coding Standards

- Python: format with `black`, lint with `flake8`.
- Frontend: keep UI consistent with existing design system.
- Respect CSR layering:
  - Route: HTTP only
  - Service: business logic
  - Repository: data access

Required checks:

```bash
python -m black app --line-length=120
python -m flake8 app --select=F,E1,E2,E4,E9,W --ignore=E203,E501,W293,W292,W391,W503,W504
```

## Commit & PR Rules

- Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: ...`
  - `fix: ...`
  - `docs: ...`
  - `perf: ...`
  - `chore: ...`
- Include clear description, impact, and test evidence in PR.
- Update docs when behavior/config changes:
  - API changes -> `docs/3_API_CONTRACTS.md`
  - config/env changes -> `docs/7_CURRENT_SETTINGS.json` and `.env.example`
  - deployment changes -> `docs/4_DEPLOYMENT.md`
  - major bug fix -> `docs/6_KNOWN_ISSUES.json`

## Security & Legal

- Never commit secrets, keys, customer data, or private documents.
- By contributing, you agree your contribution is licensed under [`GNU AGPL-3.0`](LICENSE).
- For security issues, do not open public issues. See [`SECURITY.md`](SECURITY.md).
- Do not submit contributions intended to remove license obligations, attribution, or source-availability requirements.

## Strict Open-Source Enforcement

This project is open-source, but compliance is strict:

- Modified public deployments must provide corresponding source code under AGPL-3.0.
- Forks must not impersonate or market themselves as the official project.
- Trademark/name/logo use is restricted by [`TRADEMARK_POLICY.md`](TRADEMARK_POLICY.md).
- Violations may result in takedown requests and legal enforcement.
