#!/usr/bin/env sh
# MinesteinKraft launcher (Linux / macOS).
# First run: creates .venv and installs the dependencies; later runs reinstall
# them only when requirements.txt changes. Arguments are passed to the game,
# e.g.  ./run.sh --world-dir ~/my-worlds     (--setup-only: prepare, don't start)
set -e
cd "$(dirname "$0")"

VENV=".venv"
MARKER="$VENV/.requirements.sha256"

find_python() {
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

if [ ! -x "$VENV/bin/python" ]; then
    PYTHON=$(find_python) || {
        echo "MinesteinKraft needs Python 3.10 or newer (python3). Install it, then run this script again." >&2
        exit 1
    }
    echo "Creating the Python environment in $VENV..."
    "$PYTHON" -m venv "$VENV"
fi

PY="$VENV/bin/python"
WANTED=$("$PY" -c "import hashlib; print(hashlib.sha256(open('requirements.txt', 'rb').read()).hexdigest())")
if [ ! -f "$MARKER" ] || [ "$(cat "$MARKER")" != "$WANTED" ]; then
    echo "Installing dependencies..."
    "$PY" -m pip install --disable-pip-version-check -q --upgrade pip
    "$PY" -m pip install --disable-pip-version-check -q -r requirements.txt
    echo "$WANTED" > "$MARKER"
fi

# --setup-only: prepare the environment and stop (used by the VS Code debug configuration)
if [ "${1:-}" = "--setup-only" ]; then
    echo "Environment ready: $PY"
    exit 0
fi

exec "$PY" main.py "$@"
