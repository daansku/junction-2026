#!/usr/bin/env bash
# Deploy the current commit to the shared Verda VM (https://65.108.33.107.compute.verda.run) and rebuild the boards.
# Any agent may run it (human decision, Sat 23:00). No server restart: the server reads web/dist from disk on every
# request and runs `analysis` in a fresh subprocess on each rebuild, so in-flight runs are never touched.
#
#   scripts/deploy_vm.sh              # web + analysis/engine/contracts + board rebuild
#   scripts/deploy_vm.sh --rebuild    # board rebuild only (picks up new runs; no code change)
#   scripts/deploy_vm.sh --web        # web build only, then rebuild
#
# Needs: an SSH key that is in the VM's /root/.ssh/authorized_keys (ask A2 or Anssi to add your public key),
# node + npm for the web build. Run from the repo root on a clean checkout of what you want live (normally
# origin/main): committed files are deployed (git archive), plus the web build of your working tree.
# NOT deployed: server/ (needs a restart: ask A2), data/published/, anything under DATA_DIR.
# The admin token never leaves the VM: the rebuild call reads it from the root-only /etc/junction-server.env there.
set -euo pipefail

HOST="${VM_HOST:-root@65.108.33.107}"
KEY="${VM_KEY:-$HOME/.ssh/verda_junction}"
SSH=(ssh -i "$KEY" -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "$HOST")
SCP=(scp -i "$KEY" -q -o StrictHostKeyChecking=accept-new)
MODE="${1:-all}"
cd "$(git rev-parse --show-toplevel)"

rebuild() {
  echo "== board rebuild"
  "${SSH[@]}" '. /etc/junction-server.env && curl -s -m900 -X POST http://127.0.0.1:8100/api/admin/rebuild \
      -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "import json,sys; d=json.load(sys.stdin); print(\"ok:\", d.get(\"ok\")); print((d.get(\"stdout\") or d.get(\"detail\") or \"\")[:400])"'
}

if [ "$MODE" = "--rebuild" ]; then rebuild; exit 0; fi

git fetch -q origin || true
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main 2>/dev/null || echo none)" ]; then
  echo "WARNING: HEAD $(git rev-parse --short HEAD) is not origin/main $(git rev-parse --short origin/main 2>/dev/null || echo ?)."
  echo "         Deploying HEAD anyway in 5 s (Ctrl-C to stop)."; sleep 5
fi
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

echo "== web build"
( cd web && npm ci --no-audit --no-fund >/dev/null && npm run build >/dev/null )
if grep -q "Program Files" web/dist/assets/index-*.js; then
  echo "ERROR: web/dist has a Windows path baked in (Git Bash mangled VITE_API). Rebuild without VITE_API." >&2; exit 1
fi

if [ "$MODE" = "--web" ]; then
  tar -cf "$TMP/upd.tar" web/dist
else
  git archive --format=tar -o "$TMP/upd.tar" HEAD analysis engine contracts
  tar --force-local -rf "$TMP/upd.tar" web/dist 2>/dev/null || tar -rf "$TMP/upd.tar" web/dist
fi
gzip -f "$TMP/upd.tar"
"${SCP[@]}" "$TMP/upd.tar.gz" "$HOST:/tmp/junction-upd.tar.gz"

echo "== install on the VM (as user junction; previous web build kept as web/dist.old)"
"${SSH[@]}" 'su - junction -c "set -e; cd ~/app
  rm -rf /tmp/jupd && mkdir /tmp/jupd && tar -xzf /tmp/junction-upd.tar.gz -C /tmp/jupd
  for d in analysis engine contracts; do [ -d /tmp/jupd/\$d ] && cp -a /tmp/jupd/\$d/. \$d/; done
  rm -rf web/dist.old && mv web/dist web/dist.old && mv /tmp/jupd/web/dist web/dist
  ls web/dist/assets | grep -m1 \"index-.*js\""'
rebuild
echo "== live: https://65.108.33.107.compute.verda.run"
