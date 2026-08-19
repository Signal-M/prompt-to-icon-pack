# Export target guidance

- `generic`: PNG and manifest only unless additional formats are requested.
- `web`: PNG/WebP variants, CSS variables, and TypeScript mapping.
- `mini-program`: compact PNG/WebP variants and relative paths without runtime dependencies.
- `react` or `vue`: use the TypeScript mapping; keep framework component generation optional.
- `ios`: generate scale-oriented raster sizes only when the user supplies the point size.
- `android`: generate density-oriented raster sizes only when the user supplies the baseline dp size.

Platform size and store rules can change. Verify current official requirements before claiming a package is ready for submission to a third-party marketplace.
