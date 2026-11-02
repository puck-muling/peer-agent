# Security Model and Guidelines for PeerAgent

Security and production safety are core design goals of PeerAgent. Because PeerAgent bridges multiple frontier agent CLIs running with terminal and file system access, it enforces strict boundaries.

---

## 1. Sandbox and Execution Modes

PeerAgent strictly categorizes tasks into two permission tiers:

### Read-Only Modes (`review`, `plan`, `advice`)
* **Codex**: Executed with `--sandbox read-only`. Filesystem writes are physically prevented by the sandbox.
* **Claude**: Executed with write tools disabled (`Edit`, `Write` disallowed). File modification permissions are denied (`Edit(~/**)`, `Edit(./**)`). Bash commands are executed in a sandboxed, network-isolated shell where only `$TMPDIR` is writable. Web tools (`WebSearch`, `WebFetch`) are allowed by default so Claude can check facts online. **Caution**: prompt injection in reviewed material could use them to send out what the model has read (including secrets in the project). When reviewing external or untrusted code, or when you do not need web access, set `claude_read_web: false` in `config.json` or pass `peer ask --no-web`; `peer doctor` reports the current setting.
* **Guarantee**: A read-only review task operates under strict read-only constraints to inspect and report findings without mutating project files.

### Write Modes (`exec`, `image`)
* **Quoted Request**: Write calls require a non-empty `--quote` with the user's words. PeerAgent only checks that it is present; it does not judge the scope of authorization. The slash skills use writable mode only for an explicit leading `exec` or a clear edit instruction (questions and requests for explanation stay read-only), and the prompt passes the quote on as the caller's relay of the user's words — it does not claim the user has approved anything. The executor is told to change nothing when the quote does not clearly ask for a change.
* **Pre-Execution Snapshot**: Before any write task begins, PeerAgent records an in-memory/filesystem snapshot of text files (up to 2MB each, up to 300MB total) in the target workspace, intentionally excluding `.git`, `node_modules`, `venv`, binary files, and sensitive credentials (`.env`, `*.key`, etc.). This acts as a targeted change-tracking baseline rather than a complete disk backup.
* **Automated Diff Tracking**: When the write task finishes, PeerAgent diffs the workspace against the snapshot and generates `changes.diff` and `changes.md` for human review.
* **Caution**: In `exec` mode, agents (specifically Claude) may execute shell commands permitted within its normal operating profile. Never launch untrusted code generation on sensitive production servers without human inspection.

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
