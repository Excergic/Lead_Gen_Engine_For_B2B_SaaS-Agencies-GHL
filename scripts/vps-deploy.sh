#!/usr/bin/env bash
# VPS deployment script — delegates to remote-deploy.sh
set -euo pipefail
exec "$(dirname "$0")/remote-deploy.sh"
