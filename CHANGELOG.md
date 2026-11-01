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

### Changed
- **Documentation Refinement**:
  - Elevated the core narrative from a simple CLI invocation bridge to a robust **Multi-Agent Safety & Cost Governance Middleware**.
  - Unified bilingual (CN/EN) community contact cards (QQ & Telegram) with responsive layout tables.

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
