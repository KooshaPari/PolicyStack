# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] — 2026-04-25

### Added
- **Federation Merge Integration**: Complete federation merge with CLI, extensions, policies, schemas, and scripts (commit b5d81a1)
- **PolicyStack ↔ policy-engine PyO3 Bindings**: End-to-end integration tests covering RuleEvaluator round-trip and Python wrapper layer (commit b981c9b)
- **Test Coverage Matrix**: Comprehensive test coverage documentation matrix (commit c9fbcc2)
- **User Journeys & Traceability**: 6 real end-to-end user journeys with specification traces (commit 0484bd5)
- **Spec Documentation Suite**: PRD, ADR, FUNCTIONAL_REQUIREMENTS, PLAN, and tracker documentation (commits 77fbece, c392762, e1d8df8)
- **VitePress Documentation Site**: Docsite scaffold with verification harness (commit 866f619, bf21e84)
- **AgilePlus Scaffolding**: Feature specification and project governance integration (commit 679bcfb)

### Changed
- **Error Code Standardization**: Unified error codes to kebab-case across all policy wrappers (commit 66bdf16)
- **Governance Standards**: Applied Phenotype governance standards to codebase (commit 90dd8d9)
- **Reusable CI Workflows**: Migrated to template-commons reusable workflows for consistent CI/CD (commit e2fa932)
- **Legacy Tooling Anti-Pattern Gate**: Added WARN mode enforcement for legacy tool usage patterns (commit b9c8adf)

### Fixed
- **Baseline Test Suite**: Resolved all 16 baseline test failures and cleaned lint violations (commit 985254b)
- **PyO3 Import Errors**: Unblocked wrapper import errors via conftest mocks (commit 261fd26)

### Security
- **Legacy Tool Enforcement Gate**: CI gate to prevent anti-patterns in legacy tooling (commit b9c8adf)
