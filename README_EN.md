<div align="center">

[简体中文](README_CN.md) | **English**

# PeerAgent 🤝

**Let Claude Code and Codex review each other's code. Less copy-pasting, another independent opinion.**

Ask another model to check your code from your current session and bring the findings back, without switching windows.

Local official CLIs · Existing subscription logins supported · Read-only review tasks · No third-party Python packages for the core

[Install and try it](#install-and-try-it) · [Usage examples](#usage-examples) · [Costs and permission boundaries](#costs-and-permission-boundaries) · [Troubleshooting and network FAQ](#troubleshooting-and-network-faq)

[![CI](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

</div>

## Demo video

<a href="https://cdn.jsdelivr.net/gh/puck-muling/peer-agent@main/docs/assets/demo.mp4"><img src="./docs/assets/demo_cover.jpg" alt="PeerAgent demo video cover, click to watch" width="100%" /></a>

▶ [Watch the demo video](https://cdn.jsdelivr.net/gh/puck-muling/peer-agent@main/docs/assets/demo.mp4) (2 min 21 s, Chinese narration and subtitles)

For developers already using Claude Code or Codex who want a second review. You need **Python 3.10+ and the official CLI for the model you want to call**. Subscription runs still consume quota; actual billing depends on the login mode and tools used. Installation targets macOS / Linux. Native Windows and WSL do not yet have complete project validation records.

## Install and try it

### Choose your calling path

| Calling path | What you need |
| :--- | :--- |
| `/codex` from Claude Code | A working Claude Code session and a locally installed, signed-in Codex CLI |
| The `/claude` skill from Codex | A working Codex session and a locally installed, signed-in Claude Code CLI |
| Either model from Antigravity | The Antigravity host and the signed-in official CLI for the target model |
| Direct `peer ask` | Python 3.10+ and the signed-in official CLI for the target model |

PeerAgent does not install these CLIs or log in for you. Prepare the target CLI and confirm it works on its own before installing PeerAgent. A one-way workflow does not require activating an unused calling channel.

### 30-second quickstart commands

With prerequisites ready, this is the installation entry point. Downloads and the first run depend on your network and task size:

```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent
./install.sh
peer doctor
```

The installer defaults to **file copies**. It copies `peer` to `~/.local/bin/peer` and `$PEER_HOME/bin/peer` (`PEER_HOME` defaults to `~/.peer-review`), copies templates and host skills, creates a default config if absent, and adds PATH configuration where supported by the shell. Developers can explicitly select symlinks with `./install.sh --link`. With copy installation, repository edits do not update installed copies automatically.

If the current terminal cannot find `peer` yet, use the installed path:

```bash
"$HOME/.local/bin/peer" doctor
```

`peer doctor` reports CLI locations, login categories, and configuration. **Do not use `peer doctor --approve` as a generic repair command**: it writes currently recognized login categories into the approved config and may affect both channels. Check its output and billing mode first.

### Run your first review

Reopen or refresh the host client after installation and confirm the skill has loaded. In the project you want reviewed, enter this in **Claude Code**:

```text
/codex review the current git diff, focusing on error boundaries. Do not modify files.
```

In **Codex**, invoke the `/claude` skill (the exact entry point depends on the client's skill menu):

```text
/claude review the current git diff for regressions. Do not modify files.
```

This only illustrates a possible result format. **It is not an original report from a historical run**; the location is illustrative, and findings and latency depend on the task:

```markdown
## Review findings (illustration)

- Location: src/handler.py:42 (illustrative)
- Issue: The failure branch does not close a resource, which may exhaust connections after repeated requests.
- To verify: Check whether the caller owns cleanup and run tests covering the failure branch.
```

Check the reported location and trigger before deciding to edit. A second model can miss issues or make incorrect judgments too.

## Usage examples

| Goal | Example |
| :--- | :--- |
| Ask Codex to check changes | `/codex review the current git diff for races and error boundaries. Do not modify files.` |
| Ask Claude for a refactoring plan | `peer ask claude plan --request ./plan-task.md --cwd .` (prepare the task file first) |
| Authorize a specific fix | `/codex exec Authorized: fix the confirmed resource cleanup issue, changing only that function.` |
| Generate an image (Codex only) | `/codex image Authorized: draw a call flow diagram in the specified project asset directory.` |
| Save a plan version and fingerprint | `peer freeze ./plan-v2.md --cwd .` |
| Inspect the environment | `peer doctor` |

### Review, planning, and execution

Slash skills use keyword-based intent routing. It is a heuristic, not a complete understanding of natural language. The following order applies to **the `/codex` skill in Claude Code**:

1. An explicit leading `exec` / `review` / `plan` / `advice` / `image` selects that type; `exec` is downgraded to `review` when a read-only or no-edit requirement is detected.
2. Without an explicit type, recognized negative phrases and review verbs take precedence over edit verbs. For example, reviewing changes or checking a fix stays a review.
3. The remaining checks match plan, image, edit, and advice phrases in that order, with `review` as the fallback. Phrase coverage varies by language; use an explicit type when possible.

The `/claude` skill in Codex and the Antigravity skills use different classification rules; do not assume identical precedence across hosts. Check the corresponding skill and actual call type. To select a type deterministically, use direct `peer ask`, which bypasses slash-skill intent routing.

`review`, `plan`, and `advice` use read-only execution settings. `exec` and `image` can write and require a user authorization quote. Specify allowed files clearly and check the submitted task type.

### Call directly from a terminal

Create `review-task.md` in the project with the files, original requirements, and response format. For example:

```markdown
# Task

Review the current git diff, focusing on error handling. Do not modify files.

## Response format

List locations, triggers, evidence, and remaining checks. Say explicitly if no issues were found.
```

Then invoke the target CLI:

```bash
peer ask codex review --request ./review-task.md --cwd .
```

This starts a background run and returns a run ID. Replace `RUN_ID` below with that ID:

```bash
peer wait RUN_ID --cwd .
peer status RUN_ID --cwd .
peer stats
```

A `peer wait` timeout means the result has not arrived during that wait. Inspect or wait for the original run; do not submit another `ask`.

For a write task, prepare a separate task file and pass the user's actual approval:

```bash
peer ask codex exec --request ./fix-task.md --cwd . \
  --quote 'Fix only the confirmed resource cleanup issue'
```

The program only checks that `--quote` is nonempty. It does not establish whether the quote authorizes every action. Pre-run snapshots live in `.peer-review/runs/<run_id>/snapshot/`; completion generates `changes.md` and `changes.diff`. Snapshot limits are described below.

### Host two reviews in Antigravity

Ask Claude and Codex to inspect the same source and requirements separately, then have the host summarize locations, evidence, and disagreements. Task instructions ask reviewers to check original evidence before accepting existing conclusions. **This is not OS-level blind-review isolation.** Request text is passed directly to the called model, so the host should keep the other reviewer's conclusions out of an independent review request.

After a person confirms the plan, save a frozen copy:

```bash
peer freeze ./plan-v2.md --cwd .
peer verify ./plan-v2_冻结v001.md
peer since-freeze ./plan-v2_冻结v001.md
```

This assumes the first freeze of that document; use the filename printed by the command. `freeze` creates `*_冻结vNNN.md`, a content fingerprint, project snapshot, and handoff text. It runs in standalone mode by default. Optional `--review-receipt <dir>` validates an external final-review receipt; without one, freezing does not establish approval. SHA-256 detects content changes; it does not prevent edits or authorize implementation.

<details>
<summary>Complete command index</summary>

| Command | Arguments and behavior |
| :--- | :--- |
| `peer doctor` | `[--approve]`: inspect the environment; explicitly approving records currently recognized login categories |
| `peer ask <codex\|claude> <kind>` | `--request <file> --cwd <dir>`; `kind`: `review` / `plan` / `advice` / `exec` / `image`; `image` is Codex-only |
| Optional call arguments | `--quote <text>`, `--model <model>`, `--effort <effort>`, `--service-tier <tier>`, `--add-dir <dir>`, `--caller <name>`, `--foreground`; write types require `--quote` |
| `peer wait <run_id>` | `--cwd <dir> [--timeout <seconds>]`: wait for the original run and show the report |
| `peer status [run_id]` | `--cwd <dir>`: inspect a run or the latest 10 runs |
| `peer freeze <plan>` | `--cwd <dir> [--quote <text>] [--review-receipt <dir>]`: save a frozen copy and fingerprint |
| `peer verify <frozen>` | Compare the frozen copy with its recorded SHA-256 |
| `peer since-freeze <frozen>` | Compare the project with its freeze snapshot and generate change records |
| `peer stats` | Show daily calls and available usage data, not an official billing statement |

</details>

## Costs and permission boundaries

| Mechanism | What it does | Limits |
| :--- | :--- | :--- |
| Login-category check | Compares the current category with `approved_auth`; mismatch stops the call with exit code 3 | Does not verify authorization scope, remaining credit, or final charges. Subscription calls consume quota; API logins follow their billing rules |
| Read-only tasks | Sets Codex's `read-only` sandbox; restricts Claude tools and Bash sandbox permissions; requests read-only behavior in the prompt | Depends on the target CLI and system sandbox. PeerAgent still writes task files and logs; the machine is not entirely write-free |
| Write authorization | Requires a nonempty quote for `exec` / `image` and uses write settings | A quote does not mean the program understands its scope; people and the executor must check it |
| Pre-run snapshot | Copies eligible text content, records file information, and compares afterward | Skips some directories and suspected secrets; size, binary, and total-copy limits apply. Not a full backup or automatic rollback |
| Recursion marker | Inherited `PEER_DEPTH` causes nested `peer ask` calls to exit with code 2 | Covers this entry point with its marker intact, not every possible agent loop |
| STOP files | Blocks later calls on a channel after detecting certain ban or region errors | Depends on error matching and cannot guarantee account protection. Investigate manually; agents should not remove STOP files automatically |
| Independent-review instructions | Ask reviewers to inspect source, requirements, and diffs before judging claims | Do not guarantee correctness, independence, or consensus |

Snapshots skip directories such as `.git`, `node_modules`, and `.peer-review`. Text files over 2 MiB are not copied; files over 64 MiB only have size and modification time recorded. Total copied content is capped at 300 MiB and file count at 40,000. See [`bin/peer`](./bin/peer) for details and [SECURITY.md](./SECURITY.md) for the security model.

## Troubleshooting and network FAQ

### `peer` or a target CLI cannot be found

Reopen the terminal to load PATH changes or use the fixed `~/.local/bin/peer` path above. If a target command is missing, confirm its CLI is installed and visible in the environment that starts the host. Set `bins.claude` / `bins.codex` to its actual absolute executable path if needed. Restart the host after changing PATH or configuration.

### Not signed in, or login category mismatch

Check the original channel's official CLI login status. If needed, log in using that CLI's flow, then run `peer doctor`. If you intentionally changed login mode, confirm subscription/API billing expectations before personally deciding to run `peer doctor --approve`. It records recognized categories; it does not repair networking, quota, or account permissions.

### `/codex` or `/claude` is missing after installation

Refresh or reopen the host and check that the skill is in the configuration directory that client actually uses. The installer copies skills to the default Claude, Codex, and Antigravity directories; custom config directories need to be checked against client settings. Menu behavior depends on client version. Direct `peer ask` can help isolate the calling path.

### In mainland China or another restricted network, the proxy port connects but requests fail

`proxy_check` **only attempts a TCP connection to the configured host and port**. It does not configure a proxy or validate HTTP/SOCKS behavior, authentication, DNS, TLS, or model-service reachability. Set your actual local port if you want this check:

```json
{
  "proxy_check": ["127.0.0.1", 7890]
}
```

This only makes `peer doctor` probe the port. Configure proxy addresses, protocols, and environment variables separately in the environment running the official CLI. Child processes inherit that environment, but support depends on the target CLI. Check the official CLI's network state in the same terminal, then verify the host inherits the same environment. A desktop-launched client may not inherit terminal proxy variables.

Package downloads and model-service requests are separate paths. Successful installation does not prove model-service access. For proxy timeouts, check the port, protocol, and target service first. No unverified mirrors or service-restriction workarounds are provided here.

### A task timed out or has `unknown` status

Use the original run ID with `peer status`, then inspect that run's status, report, and error files. A wait timeout can be followed by another `peer wait`. `unknown` means the process ended without a collected result, not that the request was never submitted. Do not resubmit or switch accounts while the outcome is unclear. Check the original task and account; only send a new request after confirming non-acceptance and obtaining retry authorization. PeerAgent does not retry automatically.

### A model or effort setting is unsupported

Models are blank by default and follow client settings; the config fixes Codex effort to `high` by default. Confirm target CLI support before specifying a model or effort. Precedence: call arguments > fixed config > client settings > CLI defaults. A parameter accepted by PeerAgent is not necessarily supported by the target service.

## Configuration reference

Default config: `~/.peer-review/config.json`. Use `PEER_CONFIG` for another path. These defaults match [`config.example.json`](./config.example.json):

```json
{
  "bins": {
    "claude": "claude",
    "codex": "codex"
  },
  "models": {
    "claude": "",
    "codex": ""
  },
  "efforts": {
    "claude": "",
    "codex": "high"
  },
  "service_tiers": {
    "codex": "default"
  },
  "follow_app_settings": true,
  "approved_auth": {
    "claude": "subscription",
    "codex": "subscription"
  },
  "max_turns": {
    "read": 20,
    "write": 120
  },
  "timeout_minutes": {
    "read": 30,
    "write": 60
  },
  "proxy_check": null,
  "codex_disable_apps": false
}
```

| Setting | Meaning |
| :--- | :--- |
| `bins` | Target CLI command name or absolute executable path |
| `models` | Fixed model; empty means try to follow client settings rather than hard-coding a model name |
| `efforts` | Fixed reasoning effort; empty means try to follow the client. Supported values depend on the target CLI |
| `service_tiers.codex` | This coordinator currently accepts only `default` or `flex`; default is `default` |
| `follow_app_settings` | Read client settings when the corresponding fixed value is empty |
| `approved_auth` | Approved login categories, both `subscription` by default; mismatches block calls |
| `max_turns` | Currently passed to the Claude CLI, not a universal loop limit for both agents |
| `timeout_minutes` | Maximum read/write task duration in minutes before terminating the child; does not establish that a remote request was not processed |
| `proxy_check` | Optional `[host, port]` TCP check; does not configure a proxy |
| `codex_disable_apps` | Pass a setting to disable Codex Apps; default `false`, separately disabled for image tasks |

To fix effort at high while retaining model inheritance, merge this fragment:

```json
{
  "efforts": {"claude": "high", "codex": "high"}
}
```

If intentionally switching to an official API login, complete and confirm it in that CLI, inspect `peer doctor`, and then decide whether to approve the new category. Do not approve merely to dismiss an error.

### Environment variables

| Variable | Default and purpose |
| :--- | :--- |
| `PEER_HOME` | `~/.peer-review`; configuration, templates, and global call logs |
| `PEER_CONFIG` | `$PEER_HOME/config.json`; explicit config path |
| `PEER_TEMPLATES_DIR` | Override templates; otherwise prefer `templates/` beside the program's repository, then `$PEER_HOME/templates` |
| `PEER_DEPTH` | Defaults to 0; the coordinator marks child depth to reject nested calls |
| `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` | Inherited from the launch environment; target CLI support determines behavior. PeerAgent does not set them automatically |

## What's inside and how it works

| Component | Path and description |
| :--- | :--- |
| Core coordinator | [`bin/peer`](./bin/peer), currently 2,028 lines, Python standard library only, no persistent daemon |
| CLI adaptation skills | [`skills/`](./skills/), for Claude Code, Codex, and Antigravity; not official vendor products |
| Task templates | [`templates/`](./templates/), 5 files: `review.md`, `plan.md`, `advice.md`, `exec.md`, `image.md` |
| Installer | [`install.sh`](./install.sh), file copies by default; symlinks are opt-in |
| Tests | [`tests/`](./tests/), test cases for core behavior |
| Architecture | [`docs/architecture.md`](./docs/architecture.md), design details and diagrams |

Flow: save the task → check login category, STOP files, and call depth → launch the local CLI → collect results and return a report. Claude Code, Codex, and Antigravity can initiate calls; local Claude / Codex CLIs execute them.

<details>
<summary>Architecture diagrams and existing demo assets</summary>

![Topology](./docs/diagrams/topology.svg)

![Review sequence](./docs/diagrams/review_sequence.svg)

![Evidence checking](./docs/diagrams/evidence_first_protocol.svg)

This existing demo cover contains robot image generation and a redrawn interface; **it is not a recording of code review**. Historical promotional wording in the image is not a capability guarantee. Refer to this page and the source for current behavior and limits.

<img src="./docs/assets/hero.jpg" alt="Existing demo cover with a redrawn interface and image generation" width="100%" />

</details>

## Why we built it

After writing code, we often want another model to check it. Copying code, switching windows, and moving feedback back is tedious. PeerAgent connects that step to the existing session using local signed-in CLIs.

Try it if you want an extra code check between existing CLIs. For complex orchestration, choose tools based on your specific needs. Another model does not make a finding correct; you still decide what to accept.

## Community

Report issues on [GitHub Issues](https://github.com/puck-muling/peer-agent/issues), or add QQ: 2607430010 (Puck-Muling). Also find us on [X (@puck_muling)](https://x.com/puck_muling) and [Telegram (@puckmuling)](https://t.me/puckmuling).

<p align="center">
  <img src="./docs/assets/qq_qr.jpg" height="220" alt="QQ contact QR code" />
  <img src="./docs/assets/telegram_qr.png" height="220" alt="Telegram QR code" />
</p>

Thanks to the Claude Code, Codex, and Antigravity teams and open-source contributors sharing agent-review practices.

## License and security

Released under the [MIT License](./LICENSE). See [SECURITY.md](./SECURITY.md) for security details and reporting guidelines.
