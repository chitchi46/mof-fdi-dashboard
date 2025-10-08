# Normalization Pipeline Enhancements

## Goal
- Improve the ingestion pipeline so metric/side detection, unit scaling, and quality flags are more accurate and require less manual correction.

## Scope
- Strengthen heuristics (and optional configuration) for detecting `metric`, `side`, and other categorical fields.
- Automate unit and scale factor detection (parse headers/footnotes for multipliers, currency).
- Enhance quality flags: detect structural breaks, missing segments, suspicious deltas beyond current MAD outlier logic.
- Provide configuration overrides and audit logging for manual adjustments.
- Update tests, documentation, and parse logs; ensure backward compatibility of normalized schema.

## Deliverables
- Refactored detection utilities (likely a new module in `src/mof_investviz/normalize_helpers.py`).
- Expanded unit dictionaries (e.g., `units.yml`) with conversion factors.
- Configurable rules (YAML/JSON) allowing overrides per dataset (e.g., file pattern → metric).
- Updated `NormalizeResult.stats` to surface detection confidence + reasons.
- Extended tests covering new heuristics and edge cases.
- Documentation describing detection rules and override procedures.

## Work Breakdown
1. **Research & Data Gathering**
   - Inventory wording variants for metrics/sides/units from sample datasets.
   - Capture problematic cases (mixed languages, abbreviations) for regression fixtures.
2. **Refactor Detection Logic**
   - Modularize detection functions with scoring (weights, thresholds) and structured explanations (for logging/UI display).
   - Introduce fallback order: explicit overrides → dictionary match → regex heuristics → default `unknown`.
   - Extend to additional attributes if needed (e.g., `segment_industry`).
3. **Unit & Scale Automation**
   - Parse header tokens (兆円, 百万円, USD) and capture both unit + scale factor.
   - Support multi-factor conversions (currency -> yen) when metadata available.
   - Emit warnings when conflicting units found in a single table.
4. **Quality Flag Enhancements**
   - Implement structural break detection (e.g., change point algorithms, sudden schema change).
   - Extend outlier detection with YoY % thresholds, rolling std dev.
   - Log flags with detailed reasons for downstream display.
5. **Configuration & Overrides**
   - Define optional config file (per dataset) to set explicit metric/side/unit mapping when heuristics fail.
   - Allow CLI/script arguments to specify override file.
6. **Testing & Validation**
   - Create fixture datasets covering each rule.
   - Add unit tests for detection modules and integration tests for `normalize_file`.
   - Update `parse_log.sample.json` to show new metadata.
7. **Docs & Release**
   - Document detection logic and override process in docs/README + USAGE.
   - Communicate changes in CHANGELOG (if introduced) and bump schema version if necessary.

## Dependencies
- May reuse region dictionary infrastructure for unit dictionaries (shared config loader).
- Visualization improvements may consume new quality flags; coordinate schema.

## Risks & Mitigations
- **False positives** in heuristics → include confidence scores + fallback to manual overrides.
- **Complex configuration** → provide sensible defaults and simple override examples.
- **Performance**? Additional parsing should remain lightweight; profile with large files.

## Open Questions
- Should we support machine learning-based detection later? (Keep architecture open.)
- Need for currency conversion (USD/EUR) at this stage or future release?

## Acceptance Criteria
- Detection accuracy improves (target ≥ 98% correct metric/side assignment on benchmark datasets).
- Unit scaling automated for all provided samples; manual overrides documented.
- Enhanced quality flags available in normalized output and parse logs.
