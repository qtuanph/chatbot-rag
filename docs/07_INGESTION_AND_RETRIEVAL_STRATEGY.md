# 07 — Ingestion and Retrieval Strategy

> Living implementation note for large document uploads, OCR fallback, hierarchy extraction, and retrieval quality.

## Goal

The system must keep document provenance intact, preserve per-file hierarchy, and still answer across many files with high precision.

The core rule is simple:

- Store hierarchy per file.
- Link documents at retrieval time.
- Use AI selectively for ambiguous structure, not for every page.

## Recommended Pipeline

### 1. Parse Each File Independently

Each upload becomes one document record with its own tree:

- `document`
- `page` or top-level section nodes
- nested `section` or `subsection` nodes

Do not merge separate uploads into one physical tree at ingest time. That makes citations and version tracking harder.

### 2. Prefer Native Text First

For PDF and DOCX, always try native text extraction before OCR.

- If the PDF has a text layer, use it.
- If a page is scanned or text is empty, use OCR only for that page.
- If the DOCX text exists, use it directly.
- For Word files that do not use styles correctly, fall back to heuristics.

This saves cost and keeps throughput stable for large batches.

### 3. Use OCR as a Fallback, Not a Default

PaddleOCR is best when:

- the page is a scanned image
- the PDF text layer is broken
- the document contains screenshots or embedded images
- the page layout is noisy and native text is missing

Do not OCR every page if the text layer is already good. For a 10 x 500-page batch, OCR should be selective and page-level.

### 4. Detect Hierarchy with Multiple Signals

Hierarchy extraction should combine:

- native styles from DOCX
- TOC entries in PDF if present
- numbered headings like `1.`, `1.1`, `I.`, `CHƯƠNG`, `MỤC`
- short uppercase lines
- bold or title-like manual headings
- blank-line spacing and paragraph boundaries

If the file is poorly formatted, the parser should still produce a reasonable tree instead of flattening everything into chunks.

### 5. Store an Ingestion Artifact

Every parse should produce a lightweight quality artifact with:

- node count
- non-empty node count
- total extracted characters
- maximum depth
- extraction mode
- coverage ratio
- warnings

This artifact is useful for:

- deciding whether a file needs more aggressive OCR or AI cleanup
- comparing quality across uploads
- surfacing bad documents to the operator

The implementation stores this artifact in `documents.metadata` as a compact JSON payload, including a bounded node manifest for inspection.

### 6. Retrieve Across Files, Not by Pre-Merging Files

At answer time:

- search the latest non-deleted version of each file
- retrieve relevant sections from multiple files
- pull parent context for each match
- re-rank before generation

This gives the chatbot a chance to synthesize across documents while still keeping citations precise.

## Quality Policy For Large Uploads

For large batches like 10 PDFs x 500 pages:

- process files asynchronously
- batch OCR only for pages that need it
- build section-level nodes, not tiny arbitrary chunks
- keep summaries short but meaningful
- use AI only for ambiguous layout repair or consolidation

The best balance is usually: deterministic parsing first, AI second.

## Manual Headings In DOCX

When users do not use Word styles properly, treat these as heading candidates:

- numbered lines
- uppercase short lines
- lines starting with chapter-like tokens
- bold short lines with blank-line separation
- short lines that look like a label rather than a sentence

If uncertain, keep the line as a section candidate instead of discarding structure.

## Retrieval Policy

Default retrieval should:

- exclude soft-deleted documents
- prefer latest version per file name
- keep parent context intact
- preserve citations for every grounded answer

When two documents overlap or conflict, the answer should reflect the strongest cited evidence, not an invented merge.

## Implementation Notes

- The codebase should keep file-level hierarchy in `app/services/ingestion.py`.
- Retrieval policy belongs in `app/services/rag.py`.
- Document quality metadata should be attached to the document record, not hidden in transient worker state.
- This document should be updated whenever ingestion, OCR, or retrieval policy changes.