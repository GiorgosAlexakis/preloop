#!/usr/bin/env bash
# release.sh - Preloop release orchestration script
#
# Usage:
#   ./scripts/release.sh 0.8.0
#
# What it does:
#   1. Validates version tag format (semver)
#   2. Updates Chart.yaml version + appVersion
#   3. Packages the Helm chart
#   4. Generates/updates Helm repo index.yaml
#
# After running this script:
#   - Commit the updated Chart.yaml
#   - Tag the commit: git tag v0.8.0
#   - Push: git push && git push --tags
#   - The CI/CD pipeline will build and push Docker images
#   - Upload helm-releases/*.tgz + index.yaml to your Helm repo

set -euo pipefail

VERSION="${1:?Usage: $0 <version> (e.g. 0.8.0)}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHART_DIR="$ROOT_DIR/helm/preloop"
RELEASE_DIR="$ROOT_DIR/helm-releases"

# ─── Validate semver ────────────────────────────────────────────────
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
  echo "Error: '$VERSION' is not a valid semver version (expected: X.Y.Z or X.Y.Z-suffix)"
  exit 1
fi
echo "==> Releasing Preloop v${VERSION}"

# ─── Update Chart.yaml ──────────────────────────────────────────────
echo "==> Updating helm/preloop/Chart.yaml"
sed -i.bak "s/^version:.*/version: ${VERSION}/" "$CHART_DIR/Chart.yaml"
sed -i.bak "s/^appVersion:.*/appVersion: \"${VERSION}\"/" "$CHART_DIR/Chart.yaml"
rm -f "$CHART_DIR/Chart.yaml.bak"

echo "    Chart version: $(grep '^version:' "$CHART_DIR/Chart.yaml")"
echo "    App version:   $(grep '^appVersion:' "$CHART_DIR/Chart.yaml")"

# ─── Validate chart ─────────────────────────────────────────────────
echo "==> Linting Helm chart"
if command -v helm &>/dev/null; then
  helm lint "$CHART_DIR"
else
  echo "    Warning: helm not found, skipping lint"
fi

# ─── Package chart ──────────────────────────────────────────────────
mkdir -p "$RELEASE_DIR"
echo "==> Packaging Helm chart"
if command -v helm &>/dev/null; then
  helm package "$CHART_DIR" --destination "$RELEASE_DIR"

  # ─── Generate index ─────────────────────────────────────────────
  echo "==> Generating Helm repo index"
  REPO_URL="${HELM_REPO_URL:-https://charts.preloop.ai}"
  helm repo index "$RELEASE_DIR" --url "$REPO_URL"
  echo "    Index generated at $RELEASE_DIR/index.yaml"
else
  echo "    Warning: helm not found, skipping package + index steps"
fi

# ─── Summary ────────────────────────────────────────────────────────
echo ""
echo "=== Release v${VERSION} prepared ==="
echo ""
echo "Next steps:"
echo "  1. Review changes:  git diff helm/preloop/Chart.yaml"
echo "  2. Commit:          git add -A && git commit -m 'release: v${VERSION}'"
echo "  3. Tag:             git tag v${VERSION}"
echo "  4. Push:            git push && git push --tags"
echo "  5. Upload chart:    Upload helm-releases/preloop-${VERSION}.tgz + index.yaml to Helm repo"
echo ""
