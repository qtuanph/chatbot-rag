# Changelog

All notable changes to the **chatbot-rag** platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.10.4] - 2026-07-29

### Changed
- Converted project license to **Proprietary & Confidential Closed-Source Software License**.
- Updated `LICENSE`, `README.md`, and `CONTRIBUTING.md` to reflect proprietary ownership.

## [v0.10.3] - 2026-07-29

### Added
- Documented Tier 0 FAQ O(1) Cache (~20ms response time).
- Documented automatic open escalation record creation on AI refusal ("Chưa đủ căn cứ").
- Updated API Contracts with FAQ and Escalation endpoints.

## [v0.10.2] - 2026-07-29

### Added
- Added Shadcn `FieldDescription` helper text across 5 main administrative forms (Tenants, FAQs, Users, Billing Settings, Providers).
- Added Cache Hit Rate (%) and response speed metric card to Analytics Dashboard (`/analytics`).

## [v0.10.1] - 2026-07-27

### Added
- Platform Billing Settings in SQLite database (`platform_settings` table).
- Dynamic runtime reload of token prices, hard budget, user RPM, and warning thresholds.

## [v0.10.0] - 2026-07-25

### Added
- Shared Knowledge Bases & multi-tenant access control architecture.
- Tiered cache implementation (L1 Exact Redis, L2 Semantic Qdrant).
- Admin chat audit persistence flow.
