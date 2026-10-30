# Security Model and Guidelines for PeerAgent

Security and production safety are core design goals of PeerAgent. Because PeerAgent bridges multiple frontier agent CLIs running with terminal and file system access, it enforces strict boundaries.

---

## 1. Sandbox and Execution Modes

PeerAgent strictly categorizes tasks into two permission tiers:

### Read-Only Modes (`review`, `plan`, `advice`)
* **Codex**: Executed with `--sandbox read-only`. Filesystem writes are physically prevented by the sandbox.
* **Claude Code**: Executed with write tools disabled (`Edit`, `Write` disallowed). File modification permissions are denied (`Edit(~/**)`, `Edit(./**)`). Bash commands are executed in a sandboxed, network-isolated shell where only `$TMPDIR` is writable.
* **Guarantee**: A read-only review task operates under strict read-only constraints to inspect and report findings without mutating project files.

### Write Modes (`exec`, `image`)
* **Explicit Human Quoting**: Write calls require `--quote "<Human Exact Command>"`. PeerAgent refuses to launch write actions based on vague inferences.
* **Pre-Execution Snapshot**: Before any write task begins, PeerAgent records an in-memory/filesystem snapshot of text files (up to 2MB each, up to 300MB total) in the target workspace, intentionally excluding `.git`, `node_modules`, `venv`, binary files, and sensitive credentials (`.env`, `*.key`, etc.). This acts as a targeted change-tracking baseline rather than a complete disk backup.
* **Automated Diff Tracking**: When the write task finishes, PeerAgent diffs the workspace against the snapshot and generates `changes.diff` and `changes.md` for human review.
* **Caution**: In `exec` mode, agents (specifically Claude Code) may execute shell commands permitted within its normal operating profile. Never launch untrusted code generation on sensitive production servers without human inspection.

---

## 2. Emergency STOP Circuit Breaker & Auth Guard

To protect your accounts against automated lockouts, IP bans, or runaway tasks, PeerAgent enforces two layers of defense:
* **Account Suspension Defense (`banned`)**:
  - Scans error outputs for patterns indicating account deactivation, suspension, or organization bans (`FATAL_BANNED_PATTERNS`).
  - Immediately writes a physical lock file (`$PEER_HOME/STOP` or `STOP-<agent>`).
  - **Zero AI Bypass Rule**: **No AI agent is ever allowed to delete or circumvent a STOP lock.** If triggered, human operator intervention is strictly required to verify the account status and remove the lock manually.
* **Authentication Expiration (`relogin`)**:
  - Detects 401 Unauthorized, token revocation, or refresh token invalidation (`AUTH_RELOGIN_PATTERNS`).
  - Halts the task immediately without dropping a permanent lock, and prompts the user to re-authenticate manually in the respective CLI (`claude auth login` or `codex`).
* **Pre-Flight Lock Check**:
  - Before spawning any agent process or executing queued jobs, PeerAgent checks for the presence of active STOP locks and refuses execution if found.

---

## 3. Anti-Recursion Loop Prevention

To eliminate infinite invocation loops (Agent A calling Agent B, which calls Agent A again):
* Every spawned child process inherits `PEER_DEPTH`.
* If a process attempts to invoke `peer ask` while `PEER_DEPTH >= 1`, the invocation is immediately aborted with exit code `2`.

---

## 4. Sensitive Data and Secret Scrubbing

* PeerAgent excludes sensitive files (`.env`, `*.pem`, `*.key`, `id_rsa`, `*token*.json`) from snapshot contents. Only SHA-256 fingerprints of these files are tracked to detect modifications.
* Basic email scrubbing is performed on terminal output.
* **Best Practice**: Never paste raw API keys or database passwords into task request prompts. Use environment variables or official CLI auth flows.

---

## 5. Reporting a Security Vulnerability

If you discover a security issue or vulnerability in PeerAgent, please do NOT open a public GitHub issue. Instead, report it confidentially via GitHub Security Advisories at [puck-muling/peer-agent/security/advisories](https://github.com/puck-muling/peer-agent/security/advisories).
