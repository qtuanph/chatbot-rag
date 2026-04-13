# Memory Index

This file indexes all memories for this project. Memories are stored in the `memory/` subdirectory.

## User Memories
- ✅ **user_profile.md** - Your role, goals, coding preferences, and working style
- ⏳ **user_feedback.md** - What to avoid/repeat when working with you (NOT CREATED YET)

## Project Memories
- ✅ **project_context.md** - Project goals, CORRECT architecture (BGE-m3 LOCAL, Qwen LOCAL, Gemini external for chat only)
- ✅ **implementation_gaps.md** - Critical gaps including documentation errors and security issues
- ✅ **streamlit_visualizer_requirements.md** - Streamlit tree visualizer feature requirements
- ✅ **architecture_clarifications.md** - NEW: Detailed architecture Q&A and common misconceptions

## Reference Memories
- ✅ **external_resources.md** - External systems, APIs (local vs external), documentation links

## Recent Updates (2026-04-13)

### CRITICAL: Architecture Documentation Fixed
All memory files have been updated to reflect **CORRECT** architecture:

**❌ WRONG (old docs):**
- Embedding: Google Gemini Embedding API
- Local Embedding: Future migration path

**✅ CORRECT (actual implementation):**
- **Embedding: BAAI/bge-m3 LOCAL** (sentence-transformers) ✅
- **Refiner: Qwen LOCAL** (vLLM) ✅
- **Chat LLM: Gemini external** (temporary only) ⚠️

### Key Clarifications Added
1. **project_context.md** - Added "Architecture Clarifications" section
2. **implementation_gaps.md** - Added "Documentation Incorrect" as critical blocker
3. **external_resources.md** - Separated local models from external APIs
4. **user_profile.md** - Added architecture philosophy and technology choices

### Memory Files Now Accurately Reflect:
- ✅ BAAI/bge-m3 is LOCAL (not external)
- ✅ Qwen refiner is LOCAL (not external)
- ✅ Only chat LLM uses external API (temporary)
- ✅ Documentation issues identified as critical blockers
- ✅ Streamlit visualizer requirements documented
- ✅ User preferences for local-first architecture

## Memory File Usage

When I learn something new about you or this project, I'll create/update memory files and add them to this index. You can also manually edit memories in the `memory/` directory.

### Viewing Memories
You can view these memories using:
- **VS Code** (recommended): `code .claude/memory/`
- **Obsidian** (optional): Open `.claude/memory/` as vault
- **Any text editor**: Open files directly

### Memory Types
- **user**: Information about you (role, preferences, knowledge, working style)
- **feedback**: Lessons learned from working together (what to avoid/repeat)
- **project**: Project context, goals, constraints, current status, architecture
- **reference**: External resources, APIs, links, documentation

### Current Memory Health
- **Accuracy**: ✅ All architecture info now CORRECT
- **Completeness**: ✅ All critical aspects documented
- **Clarity**: ✅ Local vs external clearly distinguished
- **Actionability**: ✅ Gaps and blockers clearly identified
