# Large-Scale Performance Optimization

## Goal
- Ensure the pipeline and dashboard remain responsive with large datasets (≥100k rows, dozens of measures/regions) through efficient data processing, caching, and rendering strategies.

## Scope
- Benchmark current pipeline and UI to establish baselines.
- Implement data reduction (downsampling, windowing) and caching for dashboard summaries.
- Move heavy computations off the main thread (Web Workers) and optimize rendering loops.
- Introduce instrumentation for monitoring performance regressions.
- Out of scope: distributed processing or backend storage redesign.

## Deliverables
- Benchmark report (pipeline runtime, memory footprint, UI frame times) with sample datasets.
- Optimized aggregation layer (pre-computed cubes, memoization keyed by filters).
- LTTB or similar downsampling for high-density timeseries + ability to view raw detail on demand.
- Web Worker implementation for JSON parsing/aggregation to keep UI thread responsive.
- Performance dashboards/logging (simple metrics output, optional `stats.json`).
- Automated performance tests (CI job or manual script) detecting regressions.

## Work Breakdown
1. **Benchmarking**
   - Create large synthetic dataset (varied measures, regions, years) + capture pipeline runtime/memory.
   - Profile dashboard operations (load, filter change, export) using browser dev tools.
2. **Pipeline Optimizations**
   - Optimize normalization loops (vectorize numeric parsing where possible, avoid redundant conversions).
   - Cache intermediate tables (e.g., normalized DataFrame) for reuse between exports.
3. **Summary/Data Layer**
   - Build multi-dimensional cache (year × measure × region) to avoid recomputation.
   - Provide aggregated + raw slices so UI can request appropriate granularity.
4. **Downsampling & Tiling**
   - Implement LTTB or percentile-based reduction for timeseries > N points.
   - Offer toggles for full-resolution downloads vs. downsampled display.
5. **Concurrency & Workers**
   - Offload heavy parsing/aggregation to Web Worker; define message protocol.
   - Ensure progress feedback + cancellation support.
6. **Rendering Efficiency**
   - Profile new visualization layer (see `.plans/visual-quality-upgrade.md`) for CPU usage.
   - Implement virtualization for legends/tooltips when many series.
7. **Monitoring & Tests**
   - Add performance test suite run locally/CI (e.g., `pytest-benchmark` + Playwright perf harness).
   - Document benchmarks and thresholds; fail build when regressions exceed tolerance.

## Dependencies
- Visualization upgrade plan for rendering improvements.
- CSV export plan to ensure caching strategies align (shared aggregation layer).

## Risks & Mitigations
- **Premature optimization** → rely on baseline metrics to prioritize.
- **Complex caching** → implement consistent invalidation (hash filters) and instrumentation for cache hits/misses.
- **Worker overhead** → batch operations to amortize serialization costs.

## Open Questions
- Are there hard requirements for mobile performance?
- Should caching persist between sessions (IndexedDB) or remain in-memory per session?

## Acceptance Criteria
- Pipeline processes 100k-row dataset in ≤30s (target) and dashboard interactions stay <200ms for filter changes.
- Downsampling toggles maintain visual fidelity while reducing render time by ≥50% on stress dataset.
- Performance metrics tracked and documented; regression tests in place.
