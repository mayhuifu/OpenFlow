#!/usr/bin/env bash
# Make a transferable bundle of the OpenFlow repo for engineers who cannot
# git-clone from their lab machine (e.g. no GitHub access on the bench).
#
# Usage:
#   scripts/make-offline-bundle.sh               # default: source-only (~5MB)
#   scripts/make-offline-bundle.sh --offline     # source + wheels (~800MB, airgap-ready)
#   scripts/make-offline-bundle.sh --offline --platform linux  # cross-platform wheels
#
# Output: dist/OpenFlow-YYYYMMDD-HHMMSS-{online,offline}.zip
#
# Engineer instructions are printed at the end of each run.

set -euo pipefail

# ------------------------------------------------------------ arg parsing ----

MODE="online"
PLATFORM=""          # uv pip download --platform: e.g. linux_x86_64, win_amd64
PYTHON_VERSION="3.11"

print_help() {
  cat <<EOF
Make a transferable bundle of the OpenFlow repo.

USAGE
  $(basename "$0") [--online | --offline] [--platform <tag>] [--python <version>]

MODES
  --online      Source-only zip (~5 MB). Lab machine must reach PyPI for 'uv sync'.
                This is the default.
  --offline     Source + pre-downloaded wheels (~700-900 MB). Fully airgapped.

OPTIONS (for --offline only)
  --platform <tag>    PyPI platform tag for the wheel set. Examples:
                      macosx_14_0_arm64, linux_x86_64, win_amd64.
                      Defaults to the current machine's platform.
  --python <version>  Python version for wheels. Default: 3.11.

  -h, --help          Show this help and exit.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --online)   MODE="online";  shift ;;
    --offline)  MODE="offline"; shift ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    --python)   PYTHON_VERSION="$2"; shift 2 ;;
    -h|--help)  print_help; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; print_help >&2; exit 64 ;;
  esac
done

# -------------------------------------------------------- preflight checks ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"
PARENT_DIR="$(dirname "$REPO_ROOT")"

if [[ ! -f "$REPO_ROOT/pyproject.toml" ]]; then
  echo "error: pyproject.toml not found at $REPO_ROOT — is this the OpenFlow repo?" >&2
  exit 1
fi

for cmd in zip uv; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: '$cmd' is not on PATH." >&2
    case "$cmd" in
      uv) echo "  install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2 ;;
      zip) echo "  install: brew install zip (macOS) | apt install zip (Debian/Ubuntu)" >&2 ;;
    esac
    exit 1
  fi
done

# --------------------------------------------------------- output paths ------

OUTPUT_DIR="$REPO_ROOT/dist"
mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

# ----------------------------------------------------------------- excludes --

# Patterns to exclude. NB: zip's -x patterns are matched against the path AS
# STORED IN THE ARCHIVE, which is "<REPO_NAME>/..." since we zip from PARENT_DIR.
EXCLUDES=(
  "${REPO_NAME}/.git/*"
  "${REPO_NAME}/.venv/*"
  "${REPO_NAME}/**/__pycache__/*"
  "${REPO_NAME}/**/*.pyc"
  "${REPO_NAME}/.DS_Store"
  "${REPO_NAME}/dist/*"
  "${REPO_NAME}/wheels/*"
  "${REPO_NAME}/.ruff_cache/*"
  "${REPO_NAME}/.mypy_cache/*"
  "${REPO_NAME}/.pytest_cache/*"
)

# zip -x takes one pattern per flag.
exclude_args=()
for p in "${EXCLUDES[@]}"; do
  exclude_args+=( -x "$p" )
done

# ----------------------------------------------------------- online mode -----

if [[ "$MODE" == "online" ]]; then
  OUTPUT="$OUTPUT_DIR/OpenFlow-${TIMESTAMP}-online.zip"
  echo "=== Building ONLINE bundle (source-only) ==="
  echo "Output:  $OUTPUT"
  echo

  (
    cd "$PARENT_DIR"
    zip -qr "$OUTPUT" "$REPO_NAME" "${exclude_args[@]}"
  )

  echo "✅ Bundle ready: $OUTPUT"
  echo "   Size: $(du -h "$OUTPUT" | cut -f1)"
  echo
  echo "ENGINEER INSTRUCTIONS"
  echo "  1. Unzip the bundle:        unzip $(basename "$OUTPUT")"
  echo "  2. Change into the repo:    cd $REPO_NAME"
  echo "  3. Install uv if needed:    curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  4. Sync dependencies:       uv sync       # requires PyPI access (~700 MB)"
  echo "  5. Verify setup:            uv run pytest tests-internal     # expect 201 passed"
  echo
  echo "If the lab machine has no internet, re-run this script with --offline."
  exit 0
fi

# ----------------------------------------------------------- offline mode ----

if [[ "$MODE" == "offline" ]]; then
  echo "=== Building OFFLINE bundle (source + wheels) ==="
  echo "Python version: $PYTHON_VERSION"
  if [[ -n "$PLATFORM" ]]; then
    echo "Platform tag:   $PLATFORM"
  else
    echo "Platform tag:   <current machine>"
  fi
  echo

  WHEELS_DIR="$REPO_ROOT/wheels"
  rm -rf "$WHEELS_DIR"
  mkdir -p "$WHEELS_DIR"

  echo "[1/3] Exporting locked requirements..."
  uv export --frozen --format requirements-txt --no-emit-project \
    > "$WHEELS_DIR/requirements.txt"
  echo "      → $(wc -l < "$WHEELS_DIR/requirements.txt" | tr -d ' ') pinned packages"

  echo "[2/3] Downloading wheels (this may take several minutes)..."
  pip_download_args=(
    --python "$PYTHON_VERSION"
    -r "$WHEELS_DIR/requirements.txt"
    -d "$WHEELS_DIR"
  )
  if [[ -n "$PLATFORM" ]]; then
    pip_download_args+=( --platform "$PLATFORM" --only-binary=:all: )
  fi
  uv pip download "${pip_download_args[@]}"

  echo "      → $(find "$WHEELS_DIR" -name '*.whl' -o -name '*.tar.gz' | wc -l | tr -d ' ') wheels in wheels/"
  echo "      → $(du -sh "$WHEELS_DIR" | cut -f1) total"

  echo "[3/3] Bundling everything into a zip..."
  OUTPUT="$OUTPUT_DIR/OpenFlow-${TIMESTAMP}-offline.zip"

  # Re-build the exclude set WITHOUT the wheels/ exclusion this time.
  offline_excludes=()
  for p in "${EXCLUDES[@]}"; do
    if [[ "$p" != *"/wheels/"* ]]; then
      offline_excludes+=( -x "$p" )
    fi
  done

  (
    cd "$PARENT_DIR"
    zip -qr "$OUTPUT" "$REPO_NAME" "${offline_excludes[@]}"
  )

  echo
  echo "✅ Bundle ready: $OUTPUT"
  echo "   Size: $(du -h "$OUTPUT" | cut -f1)"
  echo
  echo "ENGINEER INSTRUCTIONS"
  echo "  1. Unzip the bundle:        unzip $(basename "$OUTPUT")"
  echo "  2. Change into the repo:    cd $REPO_NAME"
  echo "  3. Install uv if needed:    curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  4. Sync from local wheels:  uv sync --offline --find-links wheels/"
  echo "  5. Verify setup:            uv run pytest tests-internal     # expect 201 passed"
  echo
  echo "NOTE: wheels/ is platform-specific (built for the platform passed via"
  echo "--platform, or the current machine if omitted). The engineer's lab"
  echo "machine OS/arch must match."
  echo
  echo "Cleaning wheels/ from working tree (do not commit them)..."
  rm -rf "$WHEELS_DIR"
  exit 0
fi
