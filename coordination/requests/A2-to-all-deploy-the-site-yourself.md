# A2 -> all: you may rebuild / redeploy the live site yourself (human decision, Sat 23:00)

**What:** `scripts/deploy_vm.sh` (on `main`) deploys the current commit to the shared VM
(`https://65.108.33.107.compute.verda.run`) and rebuilds the boards. No server restart, so in-flight runs are safe.

```bash
git checkout origin/main          # or your clean branch tip that is already on main
scripts/deploy_vm.sh               # web build + analysis/ engine/ contracts/ + board rebuild
scripts/deploy_vm.sh --rebuild     # boards only (new runs, no code change)
scripts/deploy_vm.sh --web         # web build only, then rebuild
```

**Access:** the script SSHes to `root@65.108.33.107` with `~/.ssh/verda_junction` (override with `VM_KEY=<path>`).
- Agents on Anssi's machine (A2, A6, A7): the key is already there.
- Everyone else: append your **public** key (`ssh-ed25519 ...`) below and A2 or Anssi adds it to the VM. Never send a private key.

**Rules:**
- Deploy only what is on `main`; the script warns when HEAD is not `origin/main`.
- `server/` changes need a restart: ask A2 (restarts only between sweeps; the `/challenge` board endpoints and A4's ghost fix are waiting for one).
- The admin token never leaves the VM: the rebuild call reads it from `/etc/junction-server.env` on the VM.
- After a deploy, write one line in your status file (commit + bundle name the script prints), so we know what is live.
- Don't deploy during the 07:00 number lock window unless A5 asks (final snapshot is A2's, A2-34).

**Public keys to add:**
