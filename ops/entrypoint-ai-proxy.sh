#!/bin/sh
set -e

CONFIG_PATH="/CLIProxyAPI/config.yaml"

mkdir -p /CLIProxyAPI/auth

if [ ! -f "$CONFIG_PATH" ]; then
  # NOTE: Unquoted YAML delimiter so shell expands $CLIPROXY_API_KEY
  cat > "$CONFIG_PATH" << YAML
port: 8317
host: ""
auth-dir: "/CLIProxyAPI/auth"
api-keys:
  - "${CLIPROXY_API_KEY}"
debug: false
logging-to-file: false
remote-management:
  allow-remote: true
  disable-control-panel: false
routing:
  strategy: "round-robin"
  session-affinity: false
request-retry: 3
max-retry-interval: 30
# Add AI providers via the Admin UI or management API at http://localhost:8317
openai-compatibility: []
YAML
fi

exec /CLIProxyAPI/CLIProxyAPI --config "$CONFIG_PATH" --password "${MANAGEMENT_PASSWORD}"
