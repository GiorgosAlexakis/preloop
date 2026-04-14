#!/usr/bin/env sh

set -eu

PRELOOP_REPO="${PRELOOP_REPO:-preloop/preloop}"
INSTALL_DIR="${INSTALL_DIR:-}"
PRELOOP_DEFAULT_VERSION="${PRELOOP_DEFAULT_VERSION:-}"
PRELOOP_VERSION="${PRELOOP_VERSION:-$PRELOOP_DEFAULT_VERSION}"

detect_os() {
  case "$(uname -s)" in
    Linux) echo "linux" ;;
    Darwin) echo "darwin" ;;
    MINGW*|MSYS*|CYGWIN*|Windows_NT) echo "windows" ;;
    *)
      echo "Unsupported operating system: $(uname -s)" >&2
      exit 1
      ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "amd64" ;;
    arm64|aarch64) echo "arm64" ;;
    *)
      echo "Unsupported architecture: $(uname -m)" >&2
      exit 1
      ;;
  esac
}

resolve_version() {
  if [ -n "$PRELOOP_VERSION" ]; then
    echo "$PRELOOP_VERSION"
    return
  fi

  latest_json="$(curl -fsSL "https://api.github.com/repos/${PRELOOP_REPO}/releases/latest")"
  version="$(printf '%s' "$latest_json" | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  if [ -z "$version" ]; then
    echo "Could not determine the latest Preloop release" >&2
    exit 1
  fi
  echo "${version#v}"
}

resolve_install_dir() {
  if [ -n "$INSTALL_DIR" ]; then
    echo "$INSTALL_DIR"
    return
  fi

  if [ -w "/usr/local/bin" ]; then
    echo "/usr/local/bin"
  else
    echo "${HOME}/.local/bin"
  fi
}

OS="$(detect_os)"
ARCH="$(detect_arch)"
VERSION="$(resolve_version)"
BIN_DIR="$(resolve_install_dir)"
TAG="v${VERSION}"

EXT=""
if [ "$OS" = "windows" ]; then
  EXT=".exe"
fi

ASSET="preloop-${OS}-${ARCH}${EXT}"
URL="https://github.com/${PRELOOP_REPO}/releases/download/${TAG}/${ASSET}"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

mkdir -p "$BIN_DIR"
curl -fsSL "$URL" -o "${TMP_DIR}/preloop${EXT}"
chmod +x "${TMP_DIR}/preloop${EXT}"
mv "${TMP_DIR}/preloop${EXT}" "${BIN_DIR}/preloop${EXT}"

echo "Installed preloop ${VERSION} to ${BIN_DIR}/preloop${EXT}"
case ":$PATH:" in
  *":${BIN_DIR}:"*) ;;
  *)
    echo "Note: ${BIN_DIR} is not on your PATH."
    ;;
esac

echo ""
printf "Would you like to login to Preloop now? [y/N] "
if read -r login_ans < /dev/tty 2>/dev/null; then
  if [ "$login_ans" = "y" ] || [ "$login_ans" = "Y" ]; then
    "${BIN_DIR}/preloop${EXT}" login || true
    echo ""
    printf "Would you like to discover and onboard local agents now? [y/N] "
    if read -r discover_ans < /dev/tty 2>/dev/null; then
      if [ "$discover_ans" = "y" ] || [ "$discover_ans" = "Y" ]; then
        "${BIN_DIR}/preloop${EXT}" agents discover || true
      fi
    fi
  fi
fi
