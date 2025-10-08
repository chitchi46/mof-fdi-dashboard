# Dashboard CSV Export Overhaul

## Goal
- Allow users to download CSV outputs that reflect the current dashboard state (filters, selected view, measure scope) with minimal latency.

## Scope
- API design for exporting normalized slices and aggregated outputs per view (timeseries, yoy diff, composition, heatmap matrix, boxplot stats).
- UI affordances (export menu/button, progress feedback) tied to active filters.
- Server-side generation with caching and streaming for large datasets.
- Documentation and tests covering export formats.
- Out of scope: PDF/image export, scheduled delivery.

## Deliverables
- `/api/export` endpoint (or equivalent) supporting `type`, `filters`, `format`, `locale` params.
- Reusable export service layer that reuses aggregation utilities (single code path with dashboard).
- UI export controls with per-view defaults + advanced options modal.
- CSV schema documentation (column descriptions, units, sample rows) in `docs/USAGE.md`.
- Automated tests (unit + integration) for each export type.

## Work Breakdown
1. **Requirements & Format Spec**
   - Define required export types and column schemas.
   - Align naming conventions (snake_case, units) with `schema.yaml`.
   - Decide on compression (optional `.zip` for multi-file exports).
2. **Backend Implementation**
   - Refactor aggregation logic into dedicated module (if not already separate) for reuse.
   - Implement export serialization (CSV writer, optional streaming) with filter application (side, metric, region, year range, measure list).
   - Add caching (e.g., keyed by hash of inputs + filters) to avoid recomputation for identical requests.
   - Harden error handling/timeouts; write audit entries to `parse_log.json` or separate export log.
3. **Frontend Integration**
   - Add export button/menu (e.g., “Download CSV”) with primary action = current view, secondary list for other types.
   - Show spinner/toast for long running downloads; disable when no data.
   - Ensure exported file names encode dataset + filters (e.g., `investviz_timeseries_assets_asia_2010-2024.csv`).
4. **Docs & Examples**
   - Update `docs/USAGE.md` with table mapping views → export outputs, sample commands.
   - Provide sample exported files in `examples/` for QA regression.
5. **Testing**
   - Unit tests for serialization helpers.
   - Integration tests hitting `/api/export` with synthetic datasets.
   - End-to-end test (Playwright) verifying UI triggers server and downloads expected CSV.

## Dependencies
- Region filter implementation (see `.plans/region-analysis.md`).
- Aggregation improvements (see `.plans/normalization-enhancements.md` for shared data structures).

## Risks & Mitigations
- **Large exports** may block server → stream responses, enforce row limits + warn user.
- **Inconsistent filters** between UI and API → centralize filter state serialization (e.g., query param hash).
- **CSV schema drift** → version each export type and add automated contract tests.

## Open Questions
- Do we need zipped multi-tab exports? (e.g., one file per measure?)
- Should exports include metadata header rows (source, filters) as comments?
- Support for TSV/Parquet/JSON in addition to CSV?

## Acceptance Criteria
- Users can download per-view CSV reflecting current filters within <5 seconds for sample datasets.
- Export schemas documented and covered by tests.
- No regressions in existing normalized output (pipeline still produces baseline CSVs).
