# Releasing Preloop

Use this checklist before every GitHub release or pre-release.

## Workflow

1. Review `CHANGELOG.md` and confirm the release scope is complete.
2. Run the release prep script:

```bash
./scripts/release.sh 0.8.0-beta.1
```

The script updates:

- `VERSION`
- `pyproject.toml`
- `frontend/package.json`
- `frontend/package-lock.json`
- `helm/preloop/Chart.yaml`
- `README.md`
- `CHANGELOG.md`

It can also optionally:

- commit the release prep changes
- create `v<version>`
- push the current branch and tag
- watch the GitHub `Release` workflow with `gh`

## Pre-Release Checklist

### Repo and docs

- [ ] `CHANGELOG.md` is accurate and grouped under the target version heading.
- [ ] `README.md` install steps, feature matrix, and edition boundaries still match the OSS release.
- [ ] `ARCHITECTURE.md` still reflects the shipped product.
- [ ] Contributor-facing repo files are in place: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates.

### Versioning and packaging

- [ ] `./scripts/release.sh <version>` was run for the target version.
- [ ] `VERSION`, Python package version, frontend version, and Helm chart version all match.
- [ ] Docker, Helm, and GitHub release docs point to the same canonical image names and install paths.
- [ ] GitHub release notes do not advertise artifacts or commands that are not actually published.
- [ ] Release assets include the CLI binaries, Python packages, Helm chart, `docker-compose.release.yaml`, and installer scripts.

### Validation

- [ ] Backend tests pass.
- [ ] Frontend build/tests pass.
- [ ] Any release-blocking smoke tests pass for login, MCP connectivity, tool execution, approvals, and audit visibility.
- [ ] Helm chart lint/package succeeds if Helm artifacts are part of the release.

### Deployment and security

- [ ] Production docs and manifests use the correct auth env vars: `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES`.
- [ ] No default development secrets remain in compose files, Helm values, or example release commands.
- [ ] External dependencies are acceptable for OSS users, especially version checks and push proxy behavior.

### GitHub release

- [ ] Tag uses the expected format: `v<version>`.
- [ ] Release is marked as a pre-release when the version contains a suffix like `-beta.1`.
- [ ] Release body includes accurate changelog notes and working install instructions.
- [ ] Uploaded assets match the release notes.
- [ ] PyPI prereleases are expected to use PEP 440 normalization, so `0.8.0-beta.1` is published as `0.8.0b1`.

## First Public OSS Release Gate

Before `v0.8.0-beta.1`, confirm these release-facing areas are resolved:

- Deployment manifests and docs use `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES` consistently.
- Docker Compose, Helm defaults, and GitHub release notes all reference the same image names.
- GitHub releases distinguish between the Python package (`preloop`, including `preloop-sync`) and the standalone CLI binaries.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, and GitHub contribution templates are present.
- OSS vs Enterprise messaging in public docs is internally consistent.

## Suggested Commands

```bash
# Prepare release files
./scripts/release.sh 0.8.0-beta.1

# Optional: package Helm artifacts too
./scripts/release.sh 0.8.0-beta.1 --package-chart

# Non-interactive full release flow
./scripts/release.sh 0.8.0-beta.1 --yes --commit --tag --push-branch --push-tag --monitor-release
```
