# Changelog

All notable changes to **PeerAgent** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-10-30

### Added
- **Unified Core Router (`peer`)**:
  - Single-file Python CLI powered purely by Python 3.10+ standard library without external dependencies.
  - Subcommands: `doctor`, `ask`, `wait`, `status`, `freeze`, `verify`, `since-freeze`, `stats`.
- **Subscription-Native Cross-Model Review**:
  - Direct P2P inter-agent review between Claude Code, OpenAI Codex CLI, and Google Antigravity.
  - Reuses existing active subscriptions (ChatGPT Plus/Team, Claude Pro/Team) through local official CLIs.
- **Defensive Safety Engine**:
  - Strict read-only sandbox mode enforcement (`review`, `plan`, `advice`).
  - Emergency STOP circuit breaker locking (`~/.peer-review/STOP`) upon account deactivation or ban errors.
  - Anti-recursion taint tracking (`PEER_DEPTH`) to prevent cross-agent infinite looping.
  - Pre/post workspace file snapshots and automated unified diff generation for authorized write tasks (`exec`).
  - Sensitive file scrubbing and credential masking.
- **Agent Integration Skills**:
  - Antigravity slash commands: `/codex`, `/claude`.
  - Claude Code slash command: `/codex`.
  - Codex CLI slash command: `/claude`.
- **Structured Review Templates**:
  - Markdown templates for `review.md`, `plan.md`, `advice.md`, `exec.md`, and `image.md`.
- **One-Line Installer (`install.sh`)**:
  - Automated setup script for macOS and Linux supporting both symlink and copy modes, with self-check verification and safe uninstallation.
- **Packaging and CI/CD**:
  - Standard `pyproject.toml` specification.
  - GitHub Actions CI workflow running multi-OS (Ubuntu, macOS) and multi-version (Python 3.10, 3.11, 3.12) matrices.
  - GitHub issue forms and pull request templates.
