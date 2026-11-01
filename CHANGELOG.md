# Changelog

All notable changes to **PeerAgent** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] - 2026-11-01

### Added
- **Ecosystem Positioning & Comparative Analysis**:
  - Added comprehensive horizontal evaluation matrix in `README` comparing PeerAgent against official plugins (`openai/codex-plugin-cc`), MCP wrappers (`consult`), and HTTP companion servers (`hirak99/peer-agent`).
  - Added explicit disambiguation notice for the similarly named `hirak99/peer-agent` repository.
  - Incorporated real-world production metrics (372+ code reviews, 235+ architectural consultations, 283+ image runs, 0 accidental billings, 0 account bans).
- **Cross-Platform Compatibility**:
  - Implemented graceful file-lock degradation for non-POSIX / Windows native environments without `fcntl`, preventing import crashes in `bin/peer`.
  - Added comprehensive unit test `test_cross_platform_fcntl_fallback` covering no-fcntl fallback paths.
  - Added `terminate_child()` in `bin/peer`: timeout / signal cleanup kills the child process group via `os.killpg` on POSIX, and falls back to `Popen.terminate()` / `Popen.kill()` where `os.killpg` / `os.getpgid` are missing (native Windows), instead of raising `AttributeError`. Signal handlers are registered by name, so a missing `SIGHUP` no longer crashes the worker.
- **Installer (`install.sh`)**:
  - Codex `/claude` skill is now installed to both `~/.codex/skills/claude/SKILL.md` (legacy path) and `~/.agents/skills/claude/SKILL.md` (current OpenAI path); `--uninstall` removes both.
  - Pre-flight path checks refuse to run (exit 1, nothing deleted) when `PEER_HOME` is the repository itself, a symlink to it, or when any install source and target resolve to the same file.
  - Foreign skill symlinks are backed up (link itself, not its target) and restored on `--uninstall`; re-running `--link` no longer backs up its own links.
  - The real `peer doctor` exit code (0 / 2 / 3) is propagated as the installer exit code, with a dedicated message for an active STOP circuit-breaker lock (code 3).
  - Claude install hints now list the official native installer first, then Homebrew and npm as alternatives.
  - Usage hints only list commands that the detected CLIs can actually run.
- **Hardening Tests**: new `TestHardeningFixes` suite covering billing-key isolation, auth probing, lock directory creation, installer path safety, exit-code propagation, skill backup/restore, `killpg` fallback and dual Codex skill paths. All tests run with a temporary lock directory / HOME, so a pre-existing `~/.peer-review` on the developer machine can no longer mask failures.
- **CI**: Python 3.9 added to the test matrix; new "Installer smoke test (clean HOME)" step runs `install.sh --copy` and `--uninstall` against an empty temporary HOME and checks every installed file.

### Changed
- **Minimum Python lowered to 3.9** (`requires-python = ">=3.9"`), with matching installer checks, README badge and `CONTRIBUTING.md`.
- **Billing protection**: `OPENAI_API_KEY` and `CODEX_API_KEY` are stripped from child-process environments (`CHILD_ENV_BLOCKED_KEYS`) so a leftover key in the parent shell is not passed to the underlying CLI. Separately, when the detected login state does not match the approved mode (`approved_auth`), the call is blocked before invocation and `peer` exits with code 3.
- **Stricter auth detection**:
  - Claude: requires exit code 0, a JSON object, and `loggedIn` exactly `true`.
  - Codex: requires exit code 0 and a full affirmative status line (`Logged in using ChatGPT` / `Logged in using an API key`); negative or partial phrases are reported as `unknown`.
- **Documentation Refinement**:
  - Elevated the core narrative from a simple CLI invocation bridge to a robust **Multi-Agent Safety & Cost Governance Middleware**.
  - Unified bilingual (CN/EN) community contact cards (QQ & Telegram) with responsive layout tables.
  - README: native Windows is not a supported install target; use WSL2. Clarified that `pip install` only installs the `peer` CLI and `./install.sh` must still be run to register the host skills.

### Fixed
- `ImageGlobalLock` now creates the lock directory before opening the lock file, fixing `FileNotFoundError` on machines without `~/.peer-review` (the CI failure in `test_cross_platform_fcntl_fallback`).
- `install.sh`: `PEER_HOME` containing `.` or `..` segments is refused (exit 1); `canon_path` now fails instead of re-joining a missing directory followed by `..` (e.g. `repo/nope/..`) into a path that bypassed the same-directory check.
- `terminate_child()` signals the process group `child.pid` directly (children are started with `start_new_session=True`) instead of calling `os.getpgid`, which raised `ESRCH` once the direct child had been reaped and left grandchildren running.
- `install.sh --uninstall` ownership checks are exact: symlinks must point to the install source or inside the repository / `PEER_HOME`; regular files must match the source or carry the `managed-by: peer-agent` marker (now in all four `SKILL.md` files and `bin/peer`). Foreign files, including `~/.local/bin/peer`, are skipped with a warning instead of deleted.
- `install.sh` pre-checks every target directory (not a regular file, writable) before writing anything, and restores the backed-up skill if copying / linking a skill fails.
- Docs: replaced absolute "no surprise bill" wording with what `approved_auth` actually does (mismatch → blocked before invocation, exit code 3).

## [0.1.0] - 2026-10-30

### Added
- **Unified Core Router (`peer`)**:
  - Single-file Python CLI powered purely by Python 3.10+ standard library without external dependencies.
  - Subcommands: `doctor`, `ask`, `wait`, `status`, `freeze`, `verify`, `since-freeze`, `stats`.
- **Subscription-Native Cross-Model Review**:
  - Direct P2P inter-agent review between Claude, Codex, and Antigravity.
  - Reuses existing active subscriptions (ChatGPT Plus/Team, Claude Pro/Team) through local official CLIs.
- **Defensive Safety Engine**:
  - Strict read-only sandbox mode enforcement (`review`, `plan`, `advice`).
  - Emergency STOP circuit breaker locking (`~/.peer-review/STOP`) upon account deactivation or ban errors.
  - Anti-recursion taint tracking (`PEER_DEPTH`) to prevent cross-agent infinite looping.
  - Pre/post workspace file snapshots and automated unified diff generation for authorized write tasks (`exec`).
  - Sensitive file scrubbing and credential masking.
- **Agent Integration Skills**:
  - Antigravity slash commands: `/codex`, `/claude`.
  - Claude slash command: `/codex`.
  - Codex slash command: `/claude`.
- **Structured Review Templates**:
  - Markdown templates for `review.md`, `plan.md`, `advice.md`, `exec.md`, and `image.md`.
- **One-Line Installer (`install.sh`)**:
  - Automated setup script for macOS and Linux supporting both symlink and copy modes, with self-check verification and safe uninstallation.
- **Packaging and CI/CD**:
  - Standard `pyproject.toml` specification.
  - GitHub Actions CI workflow running multi-OS (Ubuntu, macOS) and multi-version (Python 3.10, 3.11, 3.12) matrices.
  - GitHub issue forms and pull request templates.

### Fixed
- **Installation & Setup**:
  - Fixed Bash syntax error in `install.sh` under strict mode (`set -u`) when evaluating `${PY_VER}` next to multibyte punctuation.
  - Added PATH environment check and export guidance in `install.sh` for standard macOS setups.
  - Corrected `peer doctor` exit code so missing CLI dependencies or auth errors reliably report exit code 2.
- **Claude Integration**:
  - Added support for Claude Code `oauth_token` authentication method, resolving auth approval lock-out.
  - Removed unsupported `--permission-prompts none` CLI flag to ensure backward compatibility across Claude CLI versions.
- **Skill Task Passing**:
  - Replaced single-quoted Heredoc with `printf` in `skills/claude/codex/SKILL.md` to ensure `$ARGUMENTS` is correctly interpolated into review requests.
- **Packaging**:
  - Configured `data-files` in `pyproject.toml` to package `templates/` and `skills/` for pip distribution.
