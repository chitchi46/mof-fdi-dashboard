# Region-Segmented Analysis

## Goal
- Normalize region/area information into `segment_region` and expose it as a first-class filter/dimension in the dashboard so users can compare geographies (single or multiple) across all views.

## Scope
- Build a canonical region dictionary (JP/EN aliases, ISO codes, groupings) and version it.
- Enhance normalization to detect region columns/headers/footnotes and populate `segment_region`.
- Extend summary data structures and API payloads to support region slicing.
- Add multi-select region filters and region-aware legends/labels across all charts.
- Update documentation, parse logs, and tests.
- Out of scope: country-level drilldowns beyond the dictionary, UI internationalization.

## Deliverables
- `src/mof_investviz/normalize.py`: region extraction logic with unit tests.
- Region dictionary asset (e.g. `data/dictionaries/regions.yml`) with version metadata.
- Updated summary builder capable of grouping by region (new helper module if needed).
- Dashboard UI enhancements: region multi-select, clear filter indicators, persisted state.
- Updated docs (README, docs/README, docs/USAGE) describing region analysis workflow.
- Automated tests covering region normalization + UI smoke (Playwright or equivalent).

## Work Breakdown
1. **Discovery & Dictionary**
   - Collect region labels from sample datasets; classify frequent patterns (kanji, katakana, English).
   - Define canonical keys (e.g., ISO-2/3, JP-specific groups) and produce `regions.yml` + schema.
   - Document fallback strategy for unknown regions (e.g., `Unknown`, `Other`).
2. **Normalization Enhancements**
   - Identify columns/headers that map to region info (regexes, header heuristics, footnotes).
   - Implement parser functions returning normalized region IDs + display labels.
   - Update `NormalizeResult.meta` with detected region coverage.
   - Add unit tests using fixtures that cover ambiguous cases.
3. **Summary/Aggregation Layer**
   - Introduce aggregation utilities (e.g., `aggregate_by_region`) returning per-region timeseries, compositions, heatmaps.
   - Ensure existing `summary.json` retains backwards compatibility while adding region-aware sections (or version bump).
4. **Dashboard UI/UX**
   - Add region multi-select with search + “select all” option; persist to URL hash/localStorage.
   - Update all views to respect active regions (stacked/overlay choices, color key per region).
   - Provide quick chips indicating active filters + reset control.
5. **Docs & Logging**
   - Document workflow in `docs/README.md` and `docs/USAGE.md` (upload, filter, download by region).
   - Extend `parse_log.json` to summarize region detection results.
6. **Validation**
   - Add regression tests (unit + integration) ensuring region filters alter outputs.
   - Manual QA checklist (upload known dataset, test multi-select, download CSVs verifying filters).

## Dependencies
- Requires region dictionary asset and agreement on taxonomy with stakeholders.
- Dashboard CSV export work should align with region filters (coordinate with `.plans/dashboard-csv-export.md`).

## Risks & Mitigations
- **Ambiguous labels** (e.g., “アジア計”) → maintain alias table + heuristic weight, log unresolved items.
- **Performance hit** when slicing by many regions → pre-aggregate summary, debounce UI updates.
- **Backward compatibility** with existing summary consumers → version schema and supply defaults when no region dimension is requested.

## Open Questions
- Do we need hierarchical regions (continent → subregion) at launch?
- Should unknown regions be displayed or hidden by default?
- Expected maximum number of simultaneous regions for UI usability?

## Acceptance Criteria
- Uploading a dataset with region info populates `segment_region` ≥ 95% accuracy on sample files.
- Dashboard exposes region filters affecting all chart types and CSV downloads.
- Documentation reflects the new workflow, and automated tests cover dictionary + UI.
