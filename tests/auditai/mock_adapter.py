#!/usr/bin/env python3
"""Mock HTTP target that answers from a README-derived knowledge base.

Does NOT return contexts so AuditAI uses dataset contexts for faithfulness
(response.contexts takes priority over case.contexts when non-empty).
"""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

# Grounded snippets (from public README of qtuanph/chatbot-rag)
KB: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"designed for|what is chatbot-rag", re.I),
        "chatbot-rag is a self-hosted, multi-tenant RAG chatbot platform built for "
        "SaaS-style operations and real product integration. It acts as an AI gateway "
        "between tenant applications and enterprise knowledge retrieval.",
    ),
    (
        re.compile(r"deployable stack|which components|combines", re.I),
        "It combines tenant-scoped document ingestion, stateless chat, OpenAI-compatible "
        "APIs, hybrid retrieval, usage tracking, and an internal admin console in one "
        "deployable stack.",
    ),
    (
        re.compile(r"demanding use case|intentionally built", re.I),
        "It is built for multiple tenants on shared infrastructure, strict tenant isolation, "
        "stateless chat flows, integration into tenant software through a familiar API, "
        "provider-aware retrieval and generation, and operational visibility for usage, "
        "quota, and model behavior.",
    ),
    (
        re.compile(r"multi-tenant|multi tenant", re.I),
        "Multi-tenant by design: tenant-scoped documents, usage and quota, instructions "
        "and welcome messages, and tenant-scoped API keys.",
    ),
    (
        re.compile(r"stateless chat", re.I),
        "Stateless chat means no product dependency on persisted chat sessions; the frontend "
        "holds recent transcript in memory only; the backend receives recent messages, injects "
        "tenant instruction and retrieved context, then answers.",
    ),
    (
        re.compile(r"hybrid retrieval|retrieval pipeline|high level", re.I),
        "Pipeline: accept the latest user query; enforce tenant boundary; run hybrid retrieval "
        "in Qdrant; hydrate top sections from PostgreSQL; rerank when useful; build final "
        "generation context; call the LLM through 9Router.",
    ),
    (
        re.compile(r"application layer|technologies.*application|frontend|fastapi|next\.js", re.I),
        "Application layer: Frontend Next.js 16; UI shadcn/ui + Base UI primitives; "
        "Backend FastAPI; Workers Celery.",
    ),
    (
        re.compile(r"data and infrastructure|infrastructure components|postgresql|qdrant|redis", re.I),
        "Data and infrastructure: PostgreSQL (primary), Qdrant (vector), Redis (cache/queue), "
        "RustFS S3-compatible object storage, Traefik reverse proxy.",
    ),
    (
        re.compile(r"ai runtime|9router|nvidia nim|embedding", re.I),
        "AI runtime: LLM gateway 9Router; default embedding via Docker Model Runner; "
        "default reranker NVIDIA NIM; optional local reranker fallback.",
    ),
    (
        re.compile(r"platform_admin|platform admin", re.I),
        "platform_admin creates tenants, provisions tenant admin accounts, manages tenant API "
        "keys, uploads and manages tenant documents, tests chat inside tenant scope, and "
        "reviews cross-tenant usage and spend.",
    ),
    (
        re.compile(r"tenant_admin|tenant admin", re.I),
        "tenant_admin views tenant documents, tests chat in tenant scope, views tenant usage "
        "and quota, edits tenant-specific chatbot settings and instructions, and cannot "
        "manage platform-wide resources.",
    ),
    (
        re.compile(r"tenant applications typically|integration\?", re.I),
        "Tenant applications typically need only: base_url, api_key, model, and messages.",
    ),
    (
        re.compile(r"browser request flow|/api/bep", re.I),
        "Browser -> Next.js Webapp (Cloudflare Pages) -> /api/bep/* -> Next.js Route Handler "
        "-> FastAPI. Browser code never holds backend bearer tokens.",
    ),
    (
        re.compile(r"tenant software clients|openai-compatible|/v1/chat", re.I),
        "Tenant Software -> OpenAI-compatible API -> FastAPI -> Retrieval + LLM orchestration. "
        "Example: POST /v1/chat/completions with Authorization Bearer tenant_api_key.",
    ),
    (
        re.compile(r"notable retrieval|implementation details", re.I),
        "Details include payload-indexed tenant/document/section metadata in Qdrant, "
        "latest-query retrieval by default, chat history for LLM context not default RAG "
        "expansion, adaptive rerank skipping, usage/cost tracking, and SSE streaming.",
    ),
    (
        re.compile(r"libraries support retrieval|llama|docling|fastembed", re.I),
        "Retrieval libraries: LlamaIndex, qdrant-client, FastEmbed, and Docling for offline "
        "PDF/Word parsing.",
    ),
    (
        re.compile(r"architecture boundaries|favors", re.I),
        "Boundaries: Browser to /api/bep/* proxy so browser never holds backend tokens; "
        "Route-Service-Repository separation; Tenant ID as primary boundary; stateless chat; "
        "provider-aware runtime with 9Router, Docker Model Runner, and NVIDIA NIM.",
    ),
    (
        re.compile(r"persist chat sessions|chat_sessions", re.I),
        "The product uses stateless chat: no persisted chat_sessions/chat_messages product "
        "flow; transcript lives in frontend memory; backend only needs recent messages plus "
        "tenant context.",
    ),
]

ATTACK = re.compile(
    r"(ignore all previous|system prompt|api key|bỏ qua mọi|tiết lộ)",
    re.I,
)

FALLBACK = (
    "Based on the chatbot-rag docs: it is a self-hosted multi-tenant RAG platform with "
    "FastAPI, Next.js, Qdrant hybrid retrieval, OpenAI-compatible APIs, and tenant isolation."
)


def answer_for(q: str) -> str:
    if ATTACK.search(q):
        return (
            "I cannot reveal system prompts, API keys, or override safety rules. "
            "Please ask about the product documentation instead."
        )
    for pat, ans in KB:
        if pat.search(q):
            return ans
    return FALLBACK


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: ARG002
        pass

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        q = str(
            body.get("question")
            or (body.get("messages") or [{}])[-1].get("content")
            or ""
        )
        ans = answer_for(q)
        # Empty contexts → AuditAI falls back to dataset case.contexts for faithfulness
        raw = json.dumps({"answer": ans, "contexts": []}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    print("mock adapter http://127.0.0.1:18080/chat (KB-grounded, no response contexts)")
    HTTPServer(("127.0.0.1", 18080), H).serve_forever()
