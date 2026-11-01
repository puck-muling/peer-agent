# PeerAgent 🤝

> **Get a second model to review your code — without echo chambers or extra token bills.**  
> *A lightweight, subscription-native peer review coordinator connecting developers' terminal AI agents.*

[![CI](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Dependencies: 0 (Pure Stdlib)](https://img.shields.io/badge/dependencies-0%20(pure%20stdlib)-brightgreen.svg)](./bin/peer)
[![Billing: Subscription Native](https://img.shields.io/badge/billing-subscription%20native-orange.svg)](./README_EN.md)
[![Platform: macOS | Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/puck-muling/peer-agent)

[中文文档 (README.md)](./README.md) | [Security Model (SECURITY.md)](./SECURITY.md) | [Architecture (architecture.md)](./docs/architecture.md) | [Contributing (CONTRIBUTING.md)](./CONTRIBUTING.md) | [Changelog (CHANGELOG.md)](./CHANGELOG.md)

---

If you write code with programs like **Claude**, **Codex**, and **Antigravity**, you know these familiar frustrations:
* One model writes a block of code, and you wonder: *"Did it introduce subtle edge cases or regression bugs?"*
* You want a second model to double-check it, so you manually **copy code → switch terminals → paste prompt → bring conclusions back** across tedious rounds.
* Existing multi-agent frameworks require custom commercial API keys with expensive token bills instead of reusing your active Pro/Team subscriptions.

**With PeerAgent, you get an instant AI pairing partner directly inside your current terminal:**

### Cross-Examine Code with a Single Command

Inside your active **Claude** session:
```text
❯ /codex review current git diff, focusing on concurrency and error boundaries
```

Seconds later, headless **Codex** returns an independent audit report directly in place (strictly read-only sandbox; zero workspace modifications):
```markdown
# Codex · Review (read-only)

- Status: completed
- Model: gpt-6.1-sol
- Effort: high
- Auth: subscription (Logged in using ChatGPT)
- Provider: official

## Response

[src/api.py:42] Potential Concurrency Race Condition:
Multi-threaded write to cache file occurs without an exclusive lock, risking data corruption under high load.
Recommendation: Use fcntl.flock to guard file writes or migrate to atomic file swaps.
```

Similarly, type `/claude` inside **Codex** to have Claude independently audit Codex's implementation proposals.

---

## Why PeerAgent?

| Dimension | Manual Transfer | Commercial API Frameworks (LangGraph, CrewAI) | PeerAgent |
| :--- | :--- | :--- | :--- |
| **Workflow** | Manually copy code, switch windows, paste prompt, bring findings back | Requires custom orchestration scripts or server daemons | **One slash command in current terminal; results return in place** |
| **Billing Model** | Native subscriptions (manual effort) | Pay-per-token commercial API keys required | **Drives local official CLIs; uses existing subscriptions** |
| **Dependencies** | None | Multiple heavy Python or Node packages | **Pure Python 3.10+ standard library; zero external dependencies** |
| **Recursion Prevention**| Manual intervention | Turn-counter limits only | **OS-level `PEER_DEPTH` environment taint; physical cutoff (exit code 2)** |
| **Safety Circuit Breaker** | None | Typically relies on unhandled exceptions | **Physical `STOP` lock files; blocks AI auto-recovery** |

---

## Two Verifiable Commitments

1. **Zero External Dependencies**: The core coordinator [`bin/peer`](./bin/peer) is a single Python script importing exclusively from the Python standard library. No `pip install` required.
2. **Zero Accidental Token Bills**: Before dispatching calls, PeerAgent strictly verifies that the active CLI session matches the approved authentication mode (default: `subscription`). Any unapproved shift halts immediately (exit code 3), requiring human confirmation via `peer doctor --approve`.

---

## Installation & Quickstart

> [!TIP]
> **Prerequisites**: Python 3.10+ (pure standard library; zero third-party pip dependencies). Ensure at least one of your daily tools (Claude, Codex, or Antigravity) is installed and signed in.

### 0. Prepare Official CLIs (Install as needed)
If you need to invoke a specific model, install the corresponding official CLI and log in:
```bash
# Claude official CLI
npm install -g @anthropic-ai/claude-code
claude login

# OpenAI Codex official CLI
npm install -g @openai/codex
codex login
```

### 1. Quick Install
```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent && ./install.sh
```

### 2. Verify Authentication
```bash
peer doctor
```

### 3. Immediate Experience
In your **Claude** terminal:
```text
/codex review current git diff. Focus on error boundaries. Read-only review, do not modify files.
```

---

## Common Use Cases

* **Pre-Commit Regression Audit** (in Claude):
  ```text
  /codex review current git diff, focusing on auth validation, concurrency, and edge cases
  ```
* **Post-Refactor Consumer Audit** (in Codex):
  ```text
  /claude check whether all callers have properly adapted to the updated module return type
  ```
* **Pre-Implementation Reality Check** (in Antigravity):
  ```text
  /codex verify whether line citations in the proposed plan match reality before implementation
  ```

---

## 📖 Usage Guide

PeerAgent supports two flexible modes of interaction: **Native Slash Commands (Recommended for Daily Workflows)** and **Direct Terminal CLI Commands (CI / Automation / Scripts)**.

### Mode 1: Native Slash Command Integration (Recommended)

After installation, zero persistent background services are required. Simply dispatch cross-reviews directly from your active developer interfaces:

| Client Interface | Command Example | Execution Provider | Common Scenario |
| :--- | :--- | :--- | :--- |
| **Claude Code** | `/codex review current git diff, focusing on concurrency` | Codex (headless) | Second-model code review to catch edge-case bugs |
| **OpenAI Codex** | `/claude inspect refactored module for regression risk` | Claude (headless) | Independent architectural and design validation |
| **Antigravity** | `/codex review current code` or `/claude draft proposal` | Codex / Claude | Act as coordinator orchestrating cross-agent reviews |

> [!TIP]
> **Intelligent Natural Language Intent Routing**:
> PeerAgent automatically categorizes user requests into appropriate execution sandboxes:
> - Keywords like `review`, `check`, `inspect`, `examine` → **Strictly Read-Only Sandbox (`review`)**
> - Keywords like `plan`, `how-to`, `design`, `architecture` → **Proposal Draft Mode (`plan`)**
> - Keywords like `why`, `analyze`, `advice`, `evaluate` → **Analysis & Recommendations (`advice`)**
> - Keywords like `exec`, `modify`, `fix`, `implement` (requires explicit approval) → **Safe Editable Sandbox (`exec`)** with automated pre/post snapshot diffs

---

### Mode 2: Direct Terminal CLI Commands

Ideal for shell scripting, CI/CD pipelines, or automation workflows:

```bash
# 1. Environment and authentication health check
peer doctor

# 2. Dispatch non-blocking background review
peer ask codex review --request ./task.md --cwd .

# 3. Wait for completion and print formatted review report
peer wait <run_id> --cwd .

# 4. Inspect recent execution runs in workspace
peer status --cwd .

# 5. Display today's call counts, token usage, and latency
peer stats
```

<details>
<summary><b>Click to expand: Complete CLI Command & Parameter Reference</b></summary>

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `peer doctor` | `[--approve]` | Diagnose Python, CLIs, auth status, models, and circuit breaker locks; `--approve` confirms auth changes |
| `peer ask <agent> <kind>` | `--request <file> --cwd <dir> [--model <m>] [--effort <e>]` | Launch background task (`kind`: `review` / `plan` / `advice` / `exec`) |
| `peer wait <run_id>` | `--cwd <dir> [--timeout <sec>]` | Wait for completion and render formatted markdown report |
| `peer status [run_id]` | `--cwd <dir>` | Display recent 10 runs or detailed metadata for a specific run ID |
| `peer freeze <doc>` | `--cwd <dir> [--quote <str>]` | Lock plan with SHA-256 fingerprint, archive snapshot, and produce handoff note |
| `peer verify <doc>` | None | Verify whether a frozen specification has been tampered with |
| `peer since-freeze <doc>` | None | Diff code modifications committed after the plan freeze |
| `peer stats` | None | Aggregate today's call frequency, token volume, and response durations |

</details>

---

## ⚙️ Configuration Reference

PeerAgent is designed with a **"zero-config, works out-of-the-box"** philosophy (automatically inheriting active CLI client settings). To customize model selection, reasoning intensity, or network proxies, edit the configuration file.

### Configuration File Locations
- **Default Path**: `~/.peer-review/config.json` (auto-generated by `./install.sh`)
- **Custom Path**: Override via the `PEER_CONFIG` environment variable.

### Complete Annotated Schema (`config.json`)
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

### Parameter Explanations

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `bins` | `object` | `{"claude":"claude", "codex":"codex"}` | Custom CLI binary names or absolute paths (e.g. `/usr/local/bin/claude`). |
| `models` | `object` | `{"claude":"", "codex":""}` | Pinned model names. Leave empty `""` to inherit client defaults, or specify explicitly (e.g. `"claude-3-5-sonnet-20241022"`, `"gpt-4o"`). |
| `efforts` | `object` | `{"claude":"", "codex":"high"}` | Reasoning effort level: `low`, `medium`, `high`, `xhigh`. |
| `service_tiers` | `object` | `{"codex":"default"}` | Codex client service tier (typically `"default"` or `"priority"`). |
| `follow_app_settings`| `boolean` | `true` | When `models` or `efforts` are empty, automatically inspects and inherits active client settings. |
| `approved_auth` | `object` | `{"claude":"subscription", "codex":"subscription"}` | **Zero-Bill Safety Lock**: Approved login method. Any unapproved shift immediately halts calls (exit code 3); approve via `peer doctor --approve`. |
| `max_turns` | `object` | `{"read": 20, "write": 120}` | Physical turn caps to prevent runaway execution loops. |
| `timeout_minutes` | `object` | `{"read": 30, "write": 60}` | Hard execution timeout in minutes. Terminated child processes are safely cleaned up. |
| `proxy_check` | `array\|null`| `null` | Local proxy socket health check (e.g. `["127.0.0.1", 7890]`) validated during `peer doctor`. |
| `codex_disable_apps` | `boolean` | `false` | Disable external Codex app plugins for minimal, distraction-free code auditing. |

---

### 3 Practical Configuration Recipes

#### Recipe 1: Fixed High-Reasoning Flagship Models
Lock background reviews to flagship models and high reasoning effort regardless of interactive terminal state:
```json
{
  "models": {
    "claude": "claude-3-5-sonnet-20241022",
    "codex": "gpt-6.1-sol"
  },
  "efforts": {
    "claude": "high",
    "codex": "high"
  }
}
```

#### Recipe 2: Local HTTP/SOCKS Proxy Verification
Validate that your local development proxy is healthy during `peer doctor`:
```json
{
  "proxy_check": ["127.0.0.1", 15236]
}
```

#### Recipe 3: Switch to Official API Key Mode
If utilizing standard API keys instead of interactive subscriptions, update approved auth via CLI:
```bash
# After signing in with API mode in your CLI:
peer doctor --approve
```

---

## 🌐 Environment Variables

PeerAgent adheres to POSIX conventions and supports runtime customization via environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PEER_HOME` | `~/.peer-review` | Base directory containing configurations, templates, and call audit logs. |
| `PEER_CONFIG` | `$PEER_HOME/config.json` | Explicit path to custom `config.json`. |
| `PEER_TEMPLATES_DIR` | `$PEER_HOME/templates` | Directory storing markdown prompt templates (`review.md`, `plan.md`, etc.). |
| `PEER_DEPTH` | `0` | **Anti-Recursion Taint**: Automatically injected when spawning child processes. Halts nested calls (exit code 2). |
| `HTTP_PROXY` / `HTTPS_PROXY` | System Default | Subprocesses automatically inherit active shell proxy environment variables. |

---

## Architecture & Internals

<details>
<summary><b>Click to expand: Invocation Topology, Lifecycle & Protocol Specs</b></summary>

![Topology](./docs/diagrams/topology.svg)

* **Three Consumers, Two Providers**: Antigravity, Claude, and Codex all initiate tasks. Headless Claude and Codex act as execution providers. Single-file `peer` coordinates via the workspace file protocol without persistent daemons.

![Review Lifecycle](./docs/diagrams/review_sequence.svg)

* **Review Lifecycle & Anti-Recursion**: Tasks land on disk and pass through STOP locks and PEER_DEPTH gates. Background `_run` captures Stdio and formats markdown reports. Nested child calls are halted at the process boundary (exit code 2).

![Evidence-First Protocol](./docs/diagrams/evidence_first_protocol.svg)

* **Evidence-First Protocol**: Ground-truth code lines and actual git diffs are placed before hypotheses. Reviewers independently check evidence, report facts, and provide an independence disclosure for human verification.

Read full technical details in [Architecture Guide (docs/architecture.md)](./docs/architecture.md).
</details>

---

## Community & Connect

Follow the author on X (Twitter) or join our Telegram group to discuss multi-agent workflows:

<p align="center">
  <a href="https://x.com/puck_muling"><b>Twitter (@puck_muling)</b></a> &nbsp;·&nbsp; 
  <a href="https://t.me/puckmuling"><b>Telegram (@puckmuling)</b></a>
</p>

<p align="center">
  <img src="./docs/assets/telegram_qr.png" width="140" alt="Telegram QR Code" />
</p>

---

## License & Security

Distributed under the [MIT License](./LICENSE).  
For security disclosures and sandbox policies, see [SECURITY.md](./SECURITY.md).
