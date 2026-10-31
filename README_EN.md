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

<details>
<summary><b>Direct CLI Reference</b></summary>

```bash
# 1. Health check
peer doctor

# 2. Async read-only review
peer ask codex review --request ./task.md --cwd .

# 3. Poll and print report
peer wait <run_id> --cwd .

# 4. View token usage
peer stats
```
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
