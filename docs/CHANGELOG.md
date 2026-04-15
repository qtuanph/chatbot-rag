# Changelog

## [Unreleased] - 2026-04-15

### Added
- 2-stage retrieval pipeline (Sections → Chunks)
- `document_sections` table in PostgreSQL for section-level storage
- `SectionRepository` for managing sections in PostgreSQL
- Section extraction from Markdown via heading-based splitting
- Rule-based text refiner (0GB VRAM, 500x faster than Qwen)
- Tree API endpoints (GET /tree, /nodes, /search)
- Comprehensive test suite (68 tests)

### Changed
- Replaced Qwen AI refiner with rule-based refiner
- Retrieval now uses 2-stage: coarse section search (≥ 0.30) → fine chunk search (≥ 0.35)
- Removed webapp (Nuxt.js) frontend — will be replaced with Svelte
- Removed Streamlit dependencies from requirements.txt
- Updated documentation to reflect BGE-m3 local embedding
- Strengthened security (strong passwords, secrets, JWT entropy)

### Fixed
- Thread safety in tree.py vector store initialization
- Removed dead code (old refiner.py)
- Fixed incorrect architecture documentation
