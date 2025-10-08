# Additional MOF Dataset Support

## Goal
- Extend the pipeline to handle additional Ministry of Finance direct investment tables beyond 6d-1-1/6d-2, ensuring consistent normalization and visualization.

## Scope
- Identify priority tables (e.g., quarterly series, industry breakdowns) and gather samples.
- Update normalization heuristics/dictionaries to accommodate new layouts (multi-level headers, extra columns).
- Expand tests, docs, and examples showcasing the new datasets.
- Adjust dashboard summaries and filters to handle new measures/segments gracefully.
- Out of scope: fully generic ingestion of all MOF publications (focus on agreed subset first).

## Deliverables
- Dataset inventory with metadata (source URL, frequency, unique fields).
- Updated normalization logic + fixtures verifying correct output for each new table.
- Example normalized CSVs + parse logs for QA.
- Documentation updates (README, docs/README, USAGE) enumerating supported datasets and caveats.
- Optional CLI helper to download latest MOF files.

## Work Breakdown
1. **Dataset Discovery**
   - Collaborate with stakeholders to prioritize tables; collect sample CSV/Excel files.
   - Document schema variations (extra segments, fiscal vs. calendar year, units).
2. **Normalization Adjustments**
   - Extend header detection to handle deeper hierarchies or repeated blocks.
   - Map new metrics/segments to schema enumerations or extend schema if needed.
   - Ensure unit detection covers new unit/scale combinations.
3. **Validation & Testing**
   - Create fixtures + expected outputs; add regression tests.
   - Validate with domain experts (spot check against known totals).
4. **Dashboard Adaptation**
   - Confirm new measures integrate into summaries without clutter (maybe ranking, filtering by measure group).
   - Update UI labels/translations for new metrics/segments.
5. **Documentation & Release**
   - Update docs with supported dataset table and usage notes.
   - Provide example notebook or walkthrough analyzing new dataset.

## Dependencies
- Normalization enhancements (see `.plans/normalization-enhancements.md`) will aid in handling varied inputs.
- Visualization & export improvements ensure new metrics appear consistently.

## Risks & Mitigations
- **Schema drift** from MOF updates → monitor source, add parser versioning.
- **Excel-specific quirks** → leverage pandas/openpyxl if CSV not available, with tests.

## Open Questions
- Need to support Excel ingestion in this phase?
- Are there licensing or redistribution constraints per dataset?

## Acceptance Criteria
- At least two additional MOF tables successfully normalized and visualized end-to-end.
- Tests and documentation clearly state support level and limitations.
