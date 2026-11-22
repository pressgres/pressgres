# Contributing guidelines

Work is planned on the [Pressgres Roadmap project](https://github.com/orgs/pressgres/projects/1) as **Epics** (one roadmap area per milestone) with **Story** sub-issues; task IDs (e.g. `R-001`) match [docs/08 — Roadmap](docs/08-roadmap.md). Use the Epic, Story or Bug issue forms and link blockers with GitHub's "blocked by" relationship.

Branch from protected `main` using `feat/123-summary`, `fix/123-summary`, `docs/...`, `research/...`, `security/...`. PR titles must be Conventional Commits (checked in CI); PRs are squash-merged. PRs must link the issue and state the version matrix, tests actually run, migration/security impacts, docs, rollback and compatibility impacts. Issues labeled `review-gate` (migrations, privileges, core patch, auth, plugin activation) need designated CODEOWNER review. See [coding standards](docs/09-engineering-standards.md) and [agent instructions](AGENTS.md).

## Local checks

```bash
npx markdownlint-cli2@0.24.0 "**/*.md"
pipx run yamllint==1.38.0 -c .yamllint.yml .
```
