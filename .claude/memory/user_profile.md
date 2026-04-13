---
name: user
description: User profile and preferences for chatbot-rag project
type: user
---

# User Profile - chatbot-rag Project

## Basic Information
- **Project Role**: Lead Developer / Architect
- **Experience Level**: Senior
- **Primary Language**: Vietnamese
- **Working Style**: Detail-oriented, architecture-first

## Technical Background
- Strong knowledge of:
  - FastAPI and async Python
  - Docker and containerization
  - RAG (Retrieval Augmented Generation) systems
  - Vector databases (Qdrant)
  - LLM integration (local vLLM, external APIs)
  - Hierarchical document indexing
  - Vietnamese NLP (EasyOCR, BGE-m3)

## Communication Preferences
- **Language**: Vietnamese for explanations, English for code
- **Style**: Direct, technical, detailed
- **Likes**:
  - Detailed technical explanations with reasoning
  - Architecture diagrams before implementation
  - Understanding "why" behind decisions
  - Clean, maintainable code
  - Proper error handling
  - Good documentation
- **Dislikes**:
  - Generic advice
  - Obvious instructions
  - Skipping details
  - "Just trust me" without explanations

## Development Environment
- **OS**: Windows 11
- **Shell**: bash (Git Bash or WSL)
- **Docker**: Installed and running
- **Python**: 3.12
- **GPU**: NVIDIA (for local models)

## Project-Specific Preferences

### Architecture Philosophy
- **Docker-first deployment** - Everything containerized
- **Self-hosted solutions** - Prefer local over SaaS when possible
- **On-premise focus** - Deploy on customer infrastructure
- **Vietnamese enterprise** - Optimize for Vietnamese documents
- **Hierarchical indexing** - NOT flat chunking (preserves structure)

### Technology Choices
- **Embedding**: BAAI/bge-m3 LOCAL (not Google Gemini Embedding)
- **Refiner**: Qwen LOCAL (not external APIs)
- **Chat LLM**: Gemini API temporary, will migrate to local vLLM
- **OCR**: EasyOCR (vi+en) with GPU support
- **Storage**: RustFS (S3-compatible) - not local disk
- **Database**: PostgreSQL + Qdrant + Redis

### Strong Preferences
1. **Local-first** - Keep everything local when possible
2. **Hierarchical structure** - Preserve document hierarchy
3. **Interactive visualization** - Streamlit tree viewer for documents
4. **Vietnamese optimization** - UI messages in Vietnamese
5. **Production-ready** - Proper error handling, monitoring, logging

### Anti-Patterns (Dislikes)
1. Flat chunking without hierarchy
2. External dependencies when local works
3. Black-box solutions without understanding
4. Skipping architecture planning
5. "Works on my machine" without Docker

## Working Style

### Planning Phase
- **Wants**: Detailed architecture before coding
- **Expects**: Multiple approaches considered
- **Likes**: Trade-offs explained clearly
- **Needs**: Critical files identified upfront

### Implementation Phase
- **Prefers**: Incremental implementation
- **Values**: Tests alongside code (not after)
- **Wants**: Progress visible and measurable
- **Expects**: Clear commit messages

### Code Quality
- **Standards**: Clean, maintainable, documented
- **Error Handling**: Proper exceptions, not silent failures
- **Logging**: Structured logs for debugging
- **Security**: Strong credentials, CORS, rate limiting

## Goals for This Project

### Primary Goals
1. **Build production-ready RAG chatbot** - Not a prototype
2. **Implement hierarchical document retrieval** - Preserve structure
3. **Support multiple formats** - PDF, DOCX, XLSX, images
4. **Deploy on-premise** - Customer infrastructure
5. **Optimize for Vietnamese** - Language, OCR, UI

### Secondary Goals
1. **Interactive tree visualization** - Streamlit "Giant Tree"
2. **Full offline capability** - Migrate chat to local vLLM
3. **Enterprise features** - Backup, monitoring, logging
4. **Performance optimization** - Fast retrieval, efficient embedding
5. **Comprehensive testing** - 60%+ coverage

## Current Priorities (April 2026)

### Immediate (Week 1)
1. Fix import errors (blocking)
2. Fix documentation (incorrect architecture info)
3. Strengthen security (weak passwords)
4. Add CORS for Streamlit

### Short-term (Week 2-3)
1. **Build Streamlit Tree Visualizer** - Main feature
2. Add comprehensive tests
3. Implement logging
4. Setup monitoring

### Medium-term (Week 4+)
1. Production hardening
2. Performance optimization
3. Backup automation
4. Migrate chat LLM to local vLLM

## Feedback & Lessons Learned

### What Works Well
- Adapter pattern for external services
- Async ingestion with Celery
- Hierarchical document indexing
- Local embedding (BAAI/bge-m3)
- Docker-based deployment

### What Needs Improvement
- Documentation accuracy (says Gemini, code uses BGE-m3)
- Test coverage (currently zero)
- Monitoring (no structured logging)
- Security (weak passwords)

### Preferences for AI Assistant
- **Do**: Explain reasoning, show code examples, ask clarifying questions
- **Don't**: Skip details, assume without asking, ignore constraints
- **Like**: "Here's why I recommend X, with trade-offs"
- **Dislike**: "Just do X" without explanation

## Development Habits
- **Read**: Documentation thoroughly before coding
- **Plan**: Architecture before implementation
- **Test**: Incrementally, not at the end
- **Document**: As code evolves, not after
- **Review**: Own code before committing

## Communication Style
- **Direct**: Gets to the point quickly
- **Technical**: Uses correct terminology
- **Vietnamese**: Explanations in native language
- **English**: Code and technical terms
- **Detailed**: Wants full context, not summaries

## Last Updated
- 2026-04-13: Clarified architecture preferences (BGE-m3 local, not Gemini), added Streamlit visualizer as priority, documented communication style
