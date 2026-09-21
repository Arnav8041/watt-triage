#!/usr/bin/env bash
# Prints the NAMES of the variables defined in .env, one per line. Never their values.
# This is the one sanctioned way to look inside .env (see CLAUDE.md).
grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$(dirname "$0")/../.env" | tr -d '='
