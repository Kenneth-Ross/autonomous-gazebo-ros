#!/usr/bin/env bash

# Fail before colcon reaches the opaque setuptools errors caused by Conda or
# another non-system Python environment shadowing the ROS 2 Jazzy toolchain.
set -euo pipefail

if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
    echo "ERROR: ROS 2 Jazzy is not installed at /opt/ros/jazzy." >&2
    exit 1
fi

# ROS setup scripts may reference unset variables, so temporarily relax nounset.
set +u
source /opt/ros/jazzy/setup.bash
set -u

PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: python3 is not available on PATH." >&2
    exit 1
fi

PYTHON_PREFIX="$(python3 -c 'import sys; print(sys.prefix)')"
SETUPTOOLS_PATH="$(python3 -c 'import setuptools; print(setuptools.__file__)')"
SETUPTOOLS_MAJOR="$(python3 -c 'import setuptools; print(setuptools.__version__.split(".")[0])')"

if [[ -n "${CONDA_PREFIX:-}" && "${ALLOW_NON_SYSTEM_PYTHON:-0}" != "1" ]]; then
    cat >&2 <<EOF
ERROR: Conda is active at: $CONDA_PREFIX
ROS 2 Jazzy builds in this repository require the system Python toolchain.
Run 'conda deactivate' until CONDA_PREFIX is unset, open a clean shell, source
/opt/ros/jazzy/setup.bash, and rerun this check.
EOF
    exit 1
fi

if [[ "$PYTHON_BIN" != /usr/bin/python3 && "${ALLOW_NON_SYSTEM_PYTHON:-0}" != "1" ]]; then
    cat >&2 <<EOF
ERROR: python3 resolves to a non-system interpreter: $PYTHON_BIN
Python prefix: $PYTHON_PREFIX
setuptools: $SETUPTOOLS_PATH
Use a clean shell with /usr/bin ahead of virtual-environment paths. Set
ALLOW_NON_SYSTEM_PYTHON=1 only when intentionally testing another toolchain.
EOF
    exit 1
fi

if (( SETUPTOOLS_MAJOR >= 80 )); then
    cat >&2 <<EOF
ERROR: setuptools $SETUPTOOLS_MAJOR at $SETUPTOOLS_PATH is incompatible with the
installed colcon editable-install command. Prepend Ubuntu system packages before
building:
  export PYTHONPATH=/usr/lib/python3/dist-packages:${PYTHONPATH:-}
Then rerun this check.
EOF
    exit 1
fi

echo "ROS build environment OK"
echo "  python3:    $PYTHON_BIN"
echo "  prefix:     $PYTHON_PREFIX"
echo "  setuptools: $SETUPTOOLS_PATH"
