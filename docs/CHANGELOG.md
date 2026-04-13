# Changelog

## [Unreleased] - 2026-04-13

### Added
- Streamlit Tree Visualizer with hierarchical document exploration
- Tree API endpoints (GET /tree, /nodes, /search)
- Rule-based text refiner (0GB VRAM, 500x faster than Qwen)
- Comprehensive test suite (68 tests)
- CORS support for Streamlit (port 8501)

### Changed
- Replaced Qwen AI refiner with rule-based refiner
- Updated documentation to reflect BGE-m3 local embedding
- Strengthened security (strong passwords, secrets)

### Fixed
- Thread safety in tree.py vector store initialization
- Removed dead code (old refiner.py)
- Fixed incorrect architecture documentation

### Technical Debt
- Docker image rebuilt with all latest code
- Pytest added to requirements.txt
- Service health checks improved
