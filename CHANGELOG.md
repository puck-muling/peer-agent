# Changelog

All notable changes to **PeerAgent** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.6] - 2026-11-03

### Fixed
- **`/codex` and `/claude` sent only the user's words, so short requests like "your advice" reached the other agent with nothing to work on (`skills/claude/codex`, `skills/codex/claude`)**: the called agent is a separate process and cannot see the caller's conversation. Both skills now keep the user's words verbatim under `# 任务` (still the only part `peer route` reads for type and authorization) and have the caller add `## 目标`, `## 原始需求与证据`, `## 需要阅读的文件` and `## 背景与约束` after it when the words depend on the conversation, the same sections the Antigravity skills already used. Each background item is labelled as the user's words, a verified fact with evidence, or an inference; the added text may not widen authorization; when the target cannot be identified the caller asks the user instead of calling. Tests check that all four skills carry these sections and that background mentioning edits or images does not change routing. Found when `/codex 你的建议` returned "no subject to review"; with the fix the same words produced a full review.
- **Installer messages could break on multibyte punctuation, and `--version 0.1.3` was rejected (`bootstrap.sh`, `install.sh`)**: shell variables directly followed by full-width punctuation are now braced, and versions without the `v` prefix are accepted.

## [0.1.5] - 2026-11-02

### Changed
- **README marks 0.1.5 as a public preview**: a notice at the top of all three READMEs says the project is in its trial phase and points to GitHub Issues for feedback.

### Fixed
- **Behind a proxy, the very first download did not use it (README, `bootstrap.sh`)**: in `curl … | bash -s -- --proxy URL`, `--proxy` only reaches the script on the right; the `curl` that downloads `bootstrap.sh` itself went direct and failed with `Failed to connect` in mainland China, before any of the installer's guidance could appear. The documented command and the hints in `bootstrap.sh` are now `curl -x URL -fsSL …/bootstrap.sh | bash -s -- --proxy URL`, and the plain command is followed by a pointer to it. Verified in a clean environment without proxy variables: the old line fails, the new one installs.

## [0.1.4] - 2026-11-02

### Fixed
- **New terminals could not find `peer` after a one-line install (`install.sh`)**: the installer adds `~/.local/bin` to `PATH` for its own run so freshly installed tools work at once, and then mistook that for an existing setup, skipping the line it writes to `~/.zshrc` / `~/.bashrc`. It now decides based on the `PATH` it was started with. Found by running the published one-line installer in a clean home directory.

## [0.1.3] - 2026-11-02

### Added
- **One-line install (`bootstrap.sh`)**: `curl -fsSL https://raw.githubusercontent.com/puck-muling/peer-agent/main/bootstrap.sh | bash` downloads the latest release into `~/.peer-review/src/` and runs its `install.sh`. `--version vX.Y.Z` picks a release; `--proxy URL` is also used for the download. Errors say what went wrong and what to do next.
- **Installer checks the machine and fills in what is missing (`install.sh`)**: it first checks (without changing anything) Python, Claude Code, Codex, whether each is signed in, and whether Claude / OpenAI are reachable, lists what it will do, and after a single Enter installs the missing CLIs with their official installers (`https://claude.ai/install.sh`, `https://chatgpt.com/codex/install.sh`), opens the sign-in flow (`claude auth login`, `codex login`), and asks for a proxy when the network is blocked. Anything already installed and signed in is left alone. Without a terminal (CI, unattended) nothing is installed unless `--install-deps` is passed; `--no-install-deps` only checks. On macOS without Python it triggers the system "command line developer tools" installer or uses Homebrew; on Linux it offers the distro package manager.
- **`--proxy URL`**: used during installation and saved to `child_env` in `config.json` (an existing `child_env` is left unchanged). A proxy that is already exported in the environment is saved the same way.

### Changed
- Installer messages are rewritten in plain language: what happened and what to do next. Codex install hints use the official installer instead of npm; Homebrew hints only appear on macOS.
- README: one-line install section, proxy setup via `child_env`, the verified scope (real calls on the author's Apple Silicon Mac; CI runs unit tests and clean installs on macOS and Linux without real model calls). Removed usage statistics that cannot be verified externally.

## [0.1.2] - 2026-11-02

### Security
- **Claude write calls are now sandboxed (`bin/peer`)**: in `exec` mode Claude's Bash ran unsandboxed and auto-approved, and `--allowedTools Edit,Write` (no path scope) let the Write tool create files anywhere — verified with a real call writing outside the project. Bash now runs in the Claude sandbox (writes only to the project, `--add-dir` directories and `$TMPDIR`; no network; no unsandboxed fallback), Edit / Write are left to `acceptEdits`, which only auto-approves the working directories, and the sandbox-weakening settings check now also covers write calls. The prompt tells Claude not to work around the limits. `claude_exec_sandbox: false` restores the previous behaviour; `peer doctor` reports the setting.
- **Questions were routed to writable `exec` (`peer route`)**: any edit word made a request writable, so questions and requests for explanation such as `这个函数的实现对吗`, `解释一下这段代码的实现`, `修复了什么` or `创建者是谁` started Codex / Claude in write mode (with a snapshot and the write lock). A request that is a question (question mark, sentence-final `吗` / `么` / `呢`, or words such as `什么` / `怎么` / `是否` / `哪`) or asks for an explanation (`解释` / `原理` …) now goes to `advice` instead, `思路` counts as a plan word, and the hint about starting with `exec` is shown for every read-only result that contained an edit word. Explicit `exec` and plain edit instructions are unchanged.
- **Write prompts no longer claim authorization (`bin/peer`)**: the `exec` / `image` prompt told the executor “the user has explicitly authorized this operation … treat it as approved, no need to wait for confirmation”, although peer only checks that `--quote` is non-empty and the skills fill it from the task text. The prompt now presents the quote as the caller's relay of the user's words, states that peer does not judge the scope of authorization, and tells the executor to change nothing (and explain why) when the words only ask a question, ask for an explanation, or do not clearly request a change. SECURITY.md no longer says write actions are refused “based on vague inferences”.
- **Read-only Claude web tools can now be turned off (`bin/peer`)**: `WebSearch` / `WebFetch` were always enabled for `review` / `plan` / `advice`, with no way to disable them, although prompt injection in reviewed material could use them to send out what the model had read (including files the snapshot treats as secrets). They stay on by default; `config.json` `claude_read_web: false` or `peer ask --no-web` turns them off (`--web` turns them back on for one call), and `peer doctor` now states the setting with this warning. Without them the prompt asks Claude to list facts that need outside sources as evidence gaps.
- **Codex `/claude` skill no longer embeds user text in Python source (`skills/codex/claude/SKILL.md`)**: the model used to paste the user's request into a `task_prompt = "..."` literal, so quotes, triple quotes, backslashes or newlines could break the script or run as code. The request is now written with the file-edit tool to `.peer-review/requests/<timestamp>-<random>-codex-claude.md` (the random part avoids same-second overwrites), and the script only receives that validated path.
- **Claude `/codex` skill injection (`skills/claude/codex/SKILL.md`)**: Claude Code substitutes every `$ARGUMENTS` occurrence in the skill text, so a multi-line argument escaped the old comment line into bare Bash (and inputs such as `锁(竞争)` broke the script with a syntax error), while a line equal to the fixed heredoc delimiter `PEER_ARGUMENTS_EOF_7f3a9c` closed the heredoc early. The user's arguments now only appear in a Markdown data block; the request file is written with the `Write` tool (added to `allowed-tools`), and the Bash steps only receive a generated file path, which is validated before use. No skill keeps `$ARGUMENTS` or a fixed heredoc inside a code block.

- **Codex `/claude` skill routing (`skills/codex/claude/SKILL.md`)**: negated requests such as `不修改文件，只汇报结果` or `不要修复，给我列出问题` were routed to writable `exec` (and the negated sentence was passed on as the authorization quote). The skill now uses the same rules as the Claude `/codex` skill: explicit first-word subcommands (`exec` / `review` / `plan` / `advice`, with `exec` + negation downgraded to `review`), negation words including single `不` / `别` / `勿` with a same-sentence gap, English negations, and review verbs taking priority over edit words.
- **Claude read-only sandbox inheritance (`bin/peer`)**: `--settings` is merged with the user's and project's Claude settings, so an existing `sandbox.excludedCommands` (commands run outside the sandbox) or `sandbox.filesystem.disabled` could weaken read-only calls. `peer ask claude` in read mode now refuses to start (exit code 3, no request sent) when any of `$CLAUDE_CONFIG_DIR/settings.json`, `.claude/settings.json` or `.claude/settings.local.json` sets them.

### Fixed
- **Leftover `ANTHROPIC_API_KEY` blocked subscription users (`bin/peer`)**: `auth_state` returned `api` as soon as the variable was set, although the child process never receives it, so subscription users were stopped and nudged into `peer doctor --approve` recording a baseline that did not match the real login. Claude now follows what `claude auth status` reports in the same key-free child environment, with the variable only mentioned as a hint, matching the Codex side.
- **Snapshot cost on large / media projects (`bin/peer`)**: comparing a snapshot re-hashed every file up to 64 MiB. Files whose size and modification time are unchanged now reuse the snapshot fingerprint (the check git uses), and only files up to 8 MiB are hashed at all; larger files are compared by size and modification time.
- **`.peer-review/` could be committed into user projects (`bin/peer`)**: the first time peer creates `.peer-review/` it now writes a `.gitignore` containing `*` (an existing one is left alone).

- **Circuit breaker missed `errors[]` (`bin/peer`)**: `parse_claude` now extracts the structured `errors[]` of a Claude error result into the displayed error (truncated) and a full `error_detail` that is scanned for fatal ban / re-login patterns, so a ban reason that only appears in stdout is no longer missed. Rate-limit text inside `errors[]` is also recognized.
- **Write lock leaked on STOP (`bin/peer`)**: the dispatcher's first STOP-lock check returned without releasing the run's write lock, blocking the project until the grace-period reclaim.
- **`since-freeze` re-anchoring (`bin/peer`)**: freeze records now store the frozen file's and snapshot's paths relative to the project root. When the frozen file is no longer at its recorded location, the project root is derived from that relative path (also for older records), instead of treating the plan's subdirectory (e.g. `docs/`) as the root or comparing against the original project when it was copied. If the root cannot be derived, the command asks for `--cwd`, which is now normalized.
- **Freeze snapshot collisions (`bin/peer`)**: snapshot directories are created exclusively; two plans with the same 24-character prefix frozen in the same second no longer share and overwrite one snapshot.
- **Symlinked install and relative env paths (`bin/peer`)**: `REPO_DIR` uses `realpath`, so a symlinked `peer` finds the repo's `templates/`; `PEER_HOME`, `PEER_CONFIG` and `PEER_TEMPLATES_DIR` are made absolute at startup so the background dispatcher (which runs in the project directory) checks the same STOP, config and locks.
- **Write lock initialization race (`bin/peer`)**: `acquire_write_lock` writes the complete JSON (`run_id`, `pid`, `created_ts`) to a unique temp file in the same directory and publishes it with `os.link`, so a visible lock file is never empty. Where hard links are unavailable it falls back to exclusive create + read-back check. Empty or unparsable locks get a strict 30-second grace period based on `st_mtime`. Stale locks are reclaimed by renaming to a unique path and verifying `run_id` and inode before deleting (a mismatching lock is put back). Acquisition and reclaim are serialized with `flock` on POSIX, or with an exclusive reclaim mutex file where `fcntl` is unavailable. Release goes through `release_write_lock`, which only removes the caller's own lock.
- **Orphaned grandchildren after normal exit (`bin/peer`)**: the dispatcher now calls `terminate_child` in a `finally` block on every path (normal exit, non-zero exit, timeout, stall, spawn error). Teardown order is fixed: kill the process group, join the pipe threads, compare the snapshot / write the unified diff, then release the write lock (also released on signal exit).
- **Installer overwrote third-party `peer` (`install.sh`)**: in both `--copy` and `--link` modes, `$PEER_HOME/bin/peer` and `$LOCAL_BIN/peer` are checked with `is_peer_owned`; foreign files are moved to `.bak_<timestamp>` instead of being removed, and restored on `--uninstall`. Copy mode writes a temp file in the same directory and replaces the target with `mv -f`.
- **Installer upgrade / uninstall hardening (`install.sh`)**: symlink targets are canonicalized with `canon_path` before ownership checks, so `repo/../elsewhere` no longer passes the prefix test. Pre-flight now also checks `$PEER_HOME/bin`, `templates`, `logs` and that no final target file is occupied by a directory. Skills that already carry the `managed-by: peer-agent` marker are replaced in place without creating stacked `.bak_` files, and `--uninstall` only restores the newest original (unmanaged) backup.

### Changed
- **One routing rule for all skills (`peer route`)**: the Claude `/codex`, Codex `/claude` and Antigravity skills each carried their own keyword rules and disagreed (e.g. “看看这个 bug 并修掉” was `exec` in Antigravity but `review` in Claude Code). Routing now lives in `peer route --request <file>`, which prints `{"kind", "quote"}`; all skills call it. The vocabulary is the union of the previous two code routers (adds `删除` as an edit word and `挑刺` / `验收` as review verbs to the Claude side). When the file has a `# 任务` section only that section is considered, so Antigravity's background and constraints do not sway the result. Behaviour for every previously tested input is unchanged.
- **New `child_env` setting**: extra environment variables (e.g. `HTTPS_PROXY`) for the Claude / Codex child processes. peer runs the CLI binaries directly, bypassing shell functions or aliases that inject a proxy, and apps launched from the desktop may not inherit terminal proxies. Billing-related and internal variables are refused; `peer doctor` lists only the variable names.
- **Public skills no longer carry the author's private workflow**: the Antigravity skills referred to a private review skill by name, a dated personal rule, a “12-item checklist” and a specific subscription tier. The review-sheet steps are now an optional add-on with a conversational fallback (record the user's replies in the plan and freeze in standalone mode); the `boss-review-commit-v2` receipt format id is kept for compatibility.

- **README auth wording**: describes the actual per-agent handling of environment keys — `ANTHROPIC_API_KEY` makes Claude count as `api` and blocks the call; `OPENAI_API_KEY` / `CODEX_API_KEY` are only stripped from the child environment with a hint.
- **README wording**: replaced "millisecond detection" and "physical isolation" claims with the actual mechanisms (process-group signal handling + STOP circuit breaker after the child exits; tool allow-list limits + prompt rules, not OS-level isolation).
- **CI package validation**: builds a real wheel with `pip wheel --no-deps -w dist .`, installs it into a fresh virtual environment and runs `peer --help`.
- **Tests**: Codex `/claude` skill routing executed from the real skill text (negations, subcommands, agreement with the Claude skill); Claude read-only deny-rule form and sandbox-weakening settings; `errors[]` circuit-breaker detection; STOP-path write-lock release; `since-freeze` with a plan in a subdirectory, a copied project, legacy records and an undeterminable root; freeze snapshot uniqueness; symlinked install and relative env paths.
- **Tests (previous round)**: full-text `$ARGUMENTS` substitution test over the whole `SKILL.md` (multi-line, parentheses, delimiter collision, command substitution) with `bash -n` and end-to-end routing; write-lock tests for empty/corrupt locks, grace period, reclaim verification, no-hardlink fallback and thread/process concurrency; dispatcher tests for normal-exit process-group cleanup and teardown order; installer tests for foreign `peer` backup/restore, link→copy upgrade, managed-skill upgrade without backups, canonicalized symlink ownership and extended pre-flight.

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
