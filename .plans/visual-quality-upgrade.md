# Visualization Quality Upgrade

## Goal
- Deliver publication-ready charts with clear axes, typography, color schemes, responsive layouts, and rich interaction (tooltips, legends, annotations) across all dashboard views.

## Scope
- Evaluate whether to refactor current Canvas implementation or adopt a charting library (ECharts/uPlot/etc.), then execute chosen approach.
- Upgrade styling: axes ticks, labels, gridlines, color palettes, font usage, responsive sizing, high-DPI rendering.
- Improve interactions: tooltips with numeric formatting, crosshair, legend toggles, animations, annotation overlays.
- Ensure accessibility (color contrast, keyboard navigation hooks) and localization support.
- Update screenshot/QA scripts and documentation.
- Out of scope: full theming system or alternate light mode (unless time permits).

## Deliverables
- Design brief summarizing visual/interaction requirements and library decision.
- Refactored chart rendering module(s) with shared utilities for scales, formatting, layout.
- Enhanced legend/tooltip components supporting multi-series overlays.
- Annotation API (expose from summary or external config) for highlighting events/outliers.
- Updated CSS/styling aligned with design tokens.
- Documentation with before/after visuals and usage tips.
- Automated visual regression tests (e.g., Playwright screenshot diff) for key views.

## Work Breakdown
1. **Discovery & Design**
   - Audit current charts, gather stakeholder feedback, define success metrics (readability, frame rate).
   - Prototype candidate libraries or improved Canvas renderers; select approach based on performance + maintainability.
   - Create design tokens (colors, spacing, typography) and chart layout guidelines.
2. **Rendering Architecture**
   - Abstract data → chart-series transformation (common scales, formatting helpers).
   - Implement base chart component (axes, grid, responsive canvas/SVG) and extend for each view (timeseries, yoy diff, composition, heatmap, boxplot).
   - Ensure devicePixelRatio-aware canvas sizing and resize observers.
3. **Interaction Layer**
   - Build tooltips with crosshair, value formatting, multi-series display.
   - Implement legend toggles, overlay toggles, highlight selected series.
   - Add keyboard focus & accessible descriptions (ARIA labels).
4. **Annotations & Highlighting**
   - Define annotation schema (events, breaks, outliers) consumed from summary or external config.
   - Render markers/bands with tooltips; allow toggling.
5. **Styling & Theming**
   - Apply color palettes (color-blind safe), define gradients for heatmaps, unify fonts.
   - Add margin/padding auto-calculation to prevent label clipping.
6. **Quality Assurance**
   - Write unit tests for formatting utilities.
   - Add visual regression snapshots for each view/resolution.
   - Performance benchmark (render time <16ms for 5k points, maintain 60fps interactions).
7. **Docs & Rollout**
   - Update README/docs with new screenshots and configuration options.
   - Provide migration notes if chart API changed, including version bump.

## Dependencies
- Region/filter and export work may alter data payloads; coordinate interfaces.
- Annotation schema may depend on pipeline enhancements (see `.plans/normalization-enhancements.md`).

## Risks & Mitigations
- **Library bloat** → evaluate bundle size; enable code-splitting or tree-shaking.
- **Performance regressions** → benchmark early, keep fallback to current renderer.
- **Complexity** → modularize components, document API for maintainers.

## Open Questions
- Target minimum browser set? (IE/legacy support not planned.)
- Need for dark/light theme toggle at this stage?
- Should charts support image/PDF export concurrently with CSV work?

## Acceptance Criteria
- Visual QA passes for all views on retina and standard displays.
- Tooltips, legends, and annotations operate consistently with filters/overlays.
- Stakeholders sign off on readability improvements (side-by-side comparison available).
