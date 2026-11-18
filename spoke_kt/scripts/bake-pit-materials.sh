#!/usr/bin/env bash
# Bake the pit's prebuilt .filamat binaries from the .mat sources in
# spoke_kt/app/src/main/assets/pit/ (see that directory's README.md).
#
# Usage:
#   ./spoke_kt/scripts/bake-pit-materials.sh [path-to-matc]
#
# With no argument, expects matc on PATH (e.g. from the Filament 1.76.0
# Linux release: filament-1.76.0-linux.tgz, bin/matc). The baked binaries
# must come from Filament 1.76.0 — the exact version the app links.
# Windows: the same three commands with matc.exe from
# filament-1.76.0-windows.tgz.
set -euo pipefail

MATC="${1:-matc}"
PIT_DIR="$(cd "$(dirname "$0")/../app/src/main/assets/pit" && pwd)"

"$MATC" -p mobile -a opengl -a vulkan -o "$PIT_DIR/die-1.76.0-r3.filamat" "$PIT_DIR/die.mat"
"$MATC" -p mobile -a opengl -a vulkan -o "$PIT_DIR/felt-1.76.0-r3.filamat" "$PIT_DIR/felt.mat"
"$MATC" -p mobile -a opengl -a vulkan -o "$PIT_DIR/shadow-1.76.0-r3.filamat" "$PIT_DIR/shadow.mat"

ls -la "$PIT_DIR"/*.filamat
echo "Baked. Verify with matinfo (same Filament release):"
echo "  matinfo $PIT_DIR/die-1.76.0-r3.filamat  # Version 76, DieFace, lit"
