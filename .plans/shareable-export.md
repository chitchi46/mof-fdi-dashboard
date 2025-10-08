# Shareable Dashboard Export

## Goal
- Allow users to generate shareable outputs (static HTML bundle or packaged report) that capture the current dashboard state without requiring the local server.

## Scope
- Define export format (self-contained HTML, optional assets zip) that embeds filtered data and configuration.
- Provide CLI and UI triggers for export, reusing existing build pipeline where possible.
- Ensure exported bundle runs offline with minimal setup.
- Document usage and limitations (e.g., no live uploads, read-only interactions).
- Out of scope: deploying to hosted environments or auth-protected sharing.

## Deliverables
- Export command (e.g., `python scripts/export_dashboard.py`) and/or `/api/export?type=html`.
- Template HTML with embedded data (summary JSON, charts, filters) + hashed asset filenames.
- Optional zipped package including `normalized.csv`, `parse_log.json`, metadata, screenshot.
- Docs guiding users through export and distribution.
- Automated smoke test ensuring exported bundle loads in headless browser and renders expected elements.

## Work Breakdown
1. **Format Design**
   - Decide between single HTML (data embedded) vs. multi-file bundle.
   - Define metadata manifest (filters applied, generation timestamp, source files).
2. **Implementation**
   - Extend build pipeline to accept `--export` flag generating static assets with selected filters.
   - Serialize current dashboard state (filters, view) into bundle and adjust UI bootstrap to read from embedded data.
   - Handle asset paths (relative) for offline use; optionally inline CSS/JS.
3. **UI Integration**
   - Add “Export dashboard” action to UI (modal with options: include CSVs, anonymize values, etc.).
   - Provide progress feedback and link to download generated zip.
4. **Testing & QA**
   - Automated test that generates export, serves via file://, and checks for chart rendering.
   - Manual QA checklist (different filters, large data, cross-browser spot checks).
5. **Documentation**
   - Update docs/README + USAGE with export instructions, examples, limitations.
   - Add example bundle under `examples/` for reference.

## Dependencies
- Relies on CSV export infrastructure (reuse for including data files).
- Visualization upgrade should ensure charts can bootstrap from static data (no API calls).

## Risks & Mitigations
- **Large bundle size** → allow excluding heavy datasets or compress outputs.
- **Security concerns** (embedding raw data) → include warnings and options to anonymize sensitive fields.
- **Stale assets** if UI changes frequently → version bundle format and provide compatibility layer.

## Open Questions
- Should exports support password protection or obfuscation? (Probably later.)
- Need for automated screenshot thumbnails?

## Acceptance Criteria
- Users can export a filtered dashboard and open it offline with full interactivity.
- Export process documented and covered by smoke tests.
- Bundles include necessary metadata (filters, generation timestamp, version).
