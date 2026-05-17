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

# Background keepalive ping loop to prevent CLIProxyAPI from shutting down due to inactivity.
# Sends a lightweight management check every 5 seconds to keep the keepalive endpoint fresh.
(
  sleep 3
  while true; do
    if which curl >/dev/null 2>&1; then
      curl -s -H "Authorization: Bearer ${CLIPROXY_API_KEY}" http://localhost:8317/v0/management/openai-compatibility >/dev/null 2>&1 || true
    elif which wget >/dev/null 2>&1; then
      wget -q --header="Authorization: Bearer ${CLIPROXY_API_KEY}" --spider http://localhost:8317/v0/management/openai-compatibility >/dev/null 2>&1 || true
    else
      (echo > /dev/tcp/127.0.0.1/8317) >/dev/null 2>&1 || true
    fi
    sleep 5
  done
) &

exec /CLIProxyAPI/CLIProxyAPI --config "$CONFIG_PATH" --password "${MANAGEMENT_PASSWORD}"

