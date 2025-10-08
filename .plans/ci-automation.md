# CI / Test Automation Rollout

## Goal
- Establish automated validation (schema tests, normalization regressions, UI smoke) and continuous integration to detect issues before release.

## Scope
- Define testing strategy (unit, integration, e2e) and coverage goals.
- Add test fixtures, scripts, and CI workflow (GitHub Actions or similar) running on push/PR.
- Integrate linting/formatting checks and static analysis as appropriate.
- Publish badges/status indicators and contributor guidelines.
- Out of scope: full CD/deployment pipeline.

## Deliverables
- `tests/` suite with coverage for normalization (fixtures), summary aggregation, and UI API endpoints.
- Playwright (or similar) e2e scripts covering upload → visualization → export flows.
- CI configuration file (`.github/workflows/ci.yml` or equivalent) running lint, unit, integration, e2e (headless), and docs build.
- Coverage reports and thresholds (e.g., ≥80% for core modules).
- Contributor guide updates (README or CONTRIBUTING) describing local test commands.

## Work Breakdown
1. **Testing Framework Setup**
   - Choose Python test runner (pytest) and configure environment (fixtures, test data).
   - Set up JS testing for frontend if needed (Vitest/Jest) and e2e (Playwright).
2. **Test Authoring**
   - Unit tests for normalization helpers, aggregation, export services.
   - Integration tests covering CLI scripts (`run_pipeline.py`, `serve_dashboard.py`).
   - E2E tests uploading sample files, interacting with filters, verifying chart JSON + CSV exports.
3. **Static Analysis & Linting**
   - Add tools (ruff/flake8, mypy optional, eslint/prettier) with configs.
   - Update `pyproject.toml` or config files accordingly.
4. **CI Workflow**
   - Author workflow file(s) running on push/PR; include caching for deps.
   - Configure artifact uploads for test reports/screenshots when failures occur.
5. **Documentation & Developer UX**
   - Update docs/README with testing instructions.
   - Add badges (build/test status) to root README.
6. **Stabilization**
   - Ensure tests are deterministic (seed randomness, control time).
   - Add runbooks for flaky test triage.

## Dependencies
- Requires synthetic/regression datasets (coordinate with `.plans/normalization-enhancements.md`).
- Visualization/export features should expose test hooks (data-test ids).

## Risks & Mitigations
- **Long CI runs** → parallelize jobs, cache dependencies, split slow tests.
- **Flaky e2e** → use robust waiting strategies, headless Chrome/Firefox.

## Open Questions
- Preferred CI platform? (Assumed GitHub Actions; confirm.)
- Need for nightly jobs (large dataset benchmarks)?

## Acceptance Criteria
- CI pipeline completes in <10 minutes with green run on main branch.
- Tests catch seeded regression (introduce deliberate failure to confirm detection).
- Documentation clearly guides contributors through local test execution.
