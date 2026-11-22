# Architecture and flow diagrams

Mermaid source files are standalone `.mmd` files for editing and rendering in Mermaid Live Editor or CI. **Ordinary Markdown cannot portably import an external `.mmd` as an inline rendered diagram** on GitHub. To avoid drift, treat `.mmd` as the single source of truth; link to them from the PRD. Optionally generate SVG/PNG in CI using Mermaid CLI and embed generated images in docs (not checked in here).

- [System architecture](system.mmd)
- [Installer flowchart](install.mmd)
- [Plugin install state flow](plugin-install.mmd)
- [Migration pipeline](migration.mmd)
- [Request/query sequence](request-sequence.mmd)
- [Old vs new ID model](id-model.mmd)
- [Roadmap dependency graph](roadmap.mmd)

Suggested CI: `mmdc -i diagrams/system.mmd -o docs/assets/system.svg` (install pinned `@mermaid-js/mermaid-cli`; run a loop for all diagrams; avoid unpinned dependencies). Generated SVGs can be referenced from Markdown after CI creates them (for example, using an image link to `assets/system.svg`).
