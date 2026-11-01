# PeerAgent 🤝

> **让 Claude 与 Codex 帮彼此审代码 —— 查验真实事实，拒绝盲目附和。**  
> *专为开发者打造的轻量级、订阅原生、跨模型对等交叉审阅 CLI。*

[![CI](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Dependencies: 0 (Pure Stdlib)](https://img.shields.io/badge/dependencies-0%20(pure%20stdlib)-brightgreen.svg)](./bin/peer)
[![Billing: Subscription Native](https://img.shields.io/badge/billing-subscription%20native-orange.svg)](./README_CN.md)
[![Platform: macOS | Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/puck-muling/peer-agent)

[English Document (README_EN.md)](./README_EN.md) | [安全模型 (SECURITY.md)](./SECURITY.md) | [架构设计详解 (architecture.md)](./docs/architecture.md) | [贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md) | [版本历史 (CHANGELOG.md)](./CHANGELOG.md)

---

如果你平时在用 **Claude**，**Codex**，**Antigravity** 这几个程序写代码，你一定经历过这些痛点：
* 每次让 AI 写完一大段代码，心里总打鼓：“这里面会不会漏了边界条件，或者有隐蔽的 Regression Bug？”
* 想让另一个大模型帮忙挑刺把关，只能痛苦地**复制代码 → 切换窗口 → 粘贴发问 → 再把结论搬回来**，来回折腾好几轮；
* 现有的多智能体框架通常需要配置商业 API Key，跑一次交叉审阅产生昂贵的按 Token 计费账单，无法复用已有会员订阅。

**装上 PeerAgent 之后，就像把另一个顶级 AI 程序员请到了你的当前终端里：**

### 在当前终端一句话唤起交叉审阅

在 **Claude** 会话中：
```text
❯ /codex 审阅当前 git diff，重点排查并发竞争与边界条件
```

几秒后，后台无头运行的 **Codex** 原地返回独立审阅报告（只读沙箱，物理禁止修改任何文件）：
```markdown
# Codex · 审阅（只读）

- 状态：完成
- 模型：gpt-6.1-sol
- 强度：high
- 登录方式：subscription（Logged in using ChatGPT）
- 服务提供方：官方

## 回复

[src/api.py:42] 发现潜在并发竞争：
多线程写入 cache 文件时未获取排他锁，高并发下可能导致写入冲突。
建议：使用 fcntl.flock 保护文件写入或改用原子写入。
```

同理，在 **Codex** 终端中输入 `/claude`，即可呼叫 Claude 进行代码与方案复核。

---

## 为什么使用 PeerAgent？

| 考量维度 | 传统手动转交 | 商业 API 框架 (LangGraph / CrewAI) | PeerAgent |
| :--- | :--- | :--- | :--- |
| **交互流程** | 复制代码、切换标签页、粘贴发问、整理结论 | 需配置复杂编排脚本或常驻服务 | **当前终端一条斜杠命令，结果原地返回** |
| **计费方式** | 官方订阅（人工繁琐操作） | 需配置 API Key，按 Token 商业计费 | **本机官方 CLI 原生直驱，复用已有会员额度** |
| **环境依赖** | 无 | 依赖多个重量级第三方包 | **单文件 Python CLI，仅依赖纯标准库** |
| **防死循环机制** | 人工干预 | 仅依靠轮次上限限制 | **`PEER_DEPTH` 进程染色，子进程嵌套调用物理退出（退出码 2）** |
| **安全风控机制** | 无 | 通常依赖代码异常抛出 | **物理 `STOP` 停机锁，禁止 AI 自动恢复，保护账号安全** |

---

## 两项可核验的安全承诺

1. **纯标准库零外部依赖**：核心调度器 [`bin/peer`](./bin/peer) 为单文件实现，仅 import Python 官方标准库，无需 `pip install` 任何第三方包。
2. **绝不意外产生 API 账单**：每次调用前强制核对登录状态与已确认方式（默认 `subscription` 会员订阅）。一旦检测到未确认的变动，直接终止调用并提示退出（退出码 3），必须由人类执行 `peer doctor --approve` 确认后方可继续。

---

## 安装与上手

> [!TIP]
> **前置要求**：Python 3.10+（纯标准库，无需 pip 安装三方包）。并确保你常用的工具（Claude、Codex 或 Antigravity）中至少已安装并登录一个即可。

### 0. 准备官方 CLI（按需安装）
若需要调用对应模型，请确保本机已全局安装官方 CLI 并登录：
```bash
# Claude 官方 CLI
npm install -g @anthropic-ai/claude-code
claude login

# OpenAI Codex 官方 CLI
npm install -g @openai/codex
codex login
```

### 1. 一键安装
```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent && ./install.sh
```

### 2. 环境与认证自检
```bash
peer doctor
```

### 3. 马上体验
在你的 **Claude** 终端中输入：
```text
/codex 审阅当前 git diff，重点排查异常边界。只读审阅，不要修改任何文件。
```

---

## 典型使用场景

* **代码提交前查回归**（在 Claude 中）：
  ```text
  /codex 审阅当前 git diff，重点排查权限校验、并发与异常边界
  ```
* **重构后查调用方遗漏**（在 Codex 中）：
  ```text
  /claude 检查所有调用方是否已正确适配新模块的返回值
  ```
* **方案实施前核真伪**（在 Antigravity 中）：
  ```text
  /codex 先独立核实方案中引用的代码文件与行号是否属实，再评估可行性
  ```

---

## 📖 使用指南 (Usage Guide)

PeerAgent 支持两种交互方式：**三端无缝斜杠命令（日常最推荐）** 与 **终端 CLI 命令行直接调度（自动化/脚本）**。

### 方式一：斜杠命令原生交互（推荐）

安装完成后，无须启动任何常驻后台服务。在你的日常交互界面直接输入斜杠指令即可发起调度：

| 发起端 | 常用指令示例 | 底层执行端 | 典型场景 |
| :--- | :--- | :--- | :--- |
| **Claude Code** | `/codex 审阅当前 git diff，排查并发与边界条件` | Codex (无头) | 让 Codex 交叉挑刺，防止代码逻辑盲区 |
| **OpenAI Codex** | `/claude 复核重构模块的命名规范与类型设计` | Claude (无头) | 让 Claude 独立核实结构合理性与回归风险 |
| **Antigravity** | `/codex 审阅当前代码` 或 `/claude 给出优化方案` | Codex / Claude | 作为主持人统一调度对等交叉审阅与方案制定 |

> [!TIP]
> **自然语言智能意图路由**：
> 调度器会自动识别任务意图并切换只读/可写安全沙箱：
> - 包含“审阅 / 看看 / 检查 / review” → **严格只读沙箱 (`review`)**
> - 包含“方案 / 怎么做 / 计划 / plan” → **方案构思模式 (`plan`)**
> - 包含“分析 / 为什么 / 建议 / advice” → **结论与建议模式 (`advice`)**
> - 包含“修改 / 实现 / 修复 / exec”（需明确授权） → **安全可写沙箱 (`exec`)**，自动备份并对比快照

---

### 方式二：终端 CLI 命令行直接调度

适合在系统终端、CI/CD 自动化流水线或脚本中直接唤起：

```bash
# 1. 运行系统环境与认证自检
peer doctor

# 2. 发起只读代码审阅（非阻塞后台运行）
peer ask codex review --request ./task.md --cwd .

# 3. 等待审阅任务完成并原地输出格式化报告
peer wait <run_id> --cwd .

# 4. 查看当前项目或全局调用历史状态
peer status --cwd .

# 5. 查看当日调用次数与 Token 用量统计
peer stats
```

<details>
<summary><b>点击查看：全量 CLI 命令与参数速查表</b></summary>

| 命令 | 参数 | 说明 |
| :--- | :--- | :--- |
| `peer doctor` | `[--approve]` | 检查 Python、CLI、登录状态、模型与熔断锁；`--approve` 用于批准并记住新的登录方式 |
| `peer ask <agent> <kind>` | `--request <file> --cwd <dir> [--model <m>] [--effort <e>]` | 在后台拉起指定 Agent 执行任务（`kind` 可选：`review` / `plan` / `advice` / `exec`） |
| `peer wait <run_id>` | `--cwd <dir> [--timeout <sec>]` | 等待后台任务并实时打印结构化审阅报告（只读模式） |
| `peer status [run_id]` | `--cwd <dir>` | 查看当前工作区最近 10 次调用的运行状态或指定运行编号的详细日志 |
| `peer freeze <doc>` | `--cwd <dir> [--quote <原话>]` | 对方案文档进行 SHA-256 指纹固化与快照归档，生成交接语 |
| `peer verify <doc>` | 无 | 校验冻结版方案文档是否遭到篡改 |
| `peer since-freeze <doc>` | 无 | 对比自方案冻结以来的项目代码改动 diff |
| `peer stats` | 无 | 汇总显示当天各模型的调用频次、Token 用量与响应耗时 |

</details>

---

## ⚙️ 进阶配置指南 (Configuration)

PeerAgent 的设计哲学是**“开箱即用，零配可用”**（默认自动跟随客户端已有设置）。如果你需要指定特定的模型代系、调整思考深度或配置本地代理，可以通过配置文件进行深度定制。

### 配置文件位置
- **默认路径**：`~/.peer-review/config.json`（安装脚本会自动生成默认配置）
- **自定义路径**：可通过环境变量 `PEER_CONFIG` 指定自定义配置文件路径。

### 完整配置范例 (`config.json`)
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

### 配置项详细说明

| 配置键名 | 类型 | 默认值 | 作用说明 |
| :--- | :--- | :--- | :--- |
| `bins` | `object` | `{"claude":"claude", "codex":"codex"}` | 指定底层的可执行命令名或绝对路径。如果安装在非标准目录可填绝对路径（如 `/usr/local/bin/claude`）。 |
| `models` | `object` | `{"claude":"", "codex":""}` | 固定指定模型代系。留空 `""` 表示自动跟随客户端当前设置；亦可显式指定（如 `"claude": "claude-3-5-sonnet-20241022"`、`"codex": "gpt-4o"`）。 |
| `efforts` | `object` | `{"claude":"", "codex":"high"}` | 深度思考/推理强度。可选值：`low`（低）、`medium`（中）、`high`（高）、`xhigh`（超高）。 |
| `service_tiers` | `object` | `{"codex":"default"}` | Codex 客户端服务层级，通常保留 `"default"`。 |
| `follow_app_settings`| `boolean` | `true` | 当 `models` 或 `efforts` 为空时，是否自动读取并继承客户端原生的当前激活设置。 |
| `approved_auth` | `object` | `{"claude":"subscription", "codex":"subscription"}` | **防盗刷/防账单核心锁**：已批准的登录方式。若实际登录方式与之不符，调度器物理阻断（退出码 3），须人工运行 `peer doctor --approve` 确认后方可调用。 |
| `max_turns` | `object` | `{"read": 20, "write": 120}` | 单次任务最大对话轮次物理上限，杜绝死循环消耗额度。 |
| `timeout_minutes` | `object` | `{"read": 30, "write": 60}` | 任务最长执行超时时间（分钟），超时后自动安全终止子进程并回收资源。 |
| `proxy_check` | `array\|null`| `null` | 本地代理连通性检查。可配置如 `["127.0.0.1", 7890]`，在 `peer doctor` 时校验代理存活状态。 |
| `codex_disable_apps` | `boolean` | `false` | 是否禁用 Codex 扩展插件/Apps。设为 `true` 可确保审阅处于最精简纯粹的代码分析环境。 |

---

### 3 种高频实用配置配方 (Recipes)

#### 配方 1：固定高强度深度审阅模型
如果你希望无论交互终端当前设置是什么，后台交叉审阅时都固定使用顶级模型与高强度思考：
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

#### 配方 2：配置本地代理网络检查
在需要通过本地 HTTP/SOCKS 代理访问官方服务的网络环境下，让 `peer doctor` 自动检查代理端口：
```json
{
  "proxy_check": ["127.0.0.1", 15236]
}
```

#### 配方 3：切换为官方 API Key 模式
如果你选择使用官方 API Key 而非会员订阅，在完成 CLI 的 API 登录后，更新批准模式并保存：
```bash
# 确认当前登录变更为 API 模式后，直接批准更新配置：
peer doctor --approve
```
对应 `config.json` 将自动记录：
```json
{
  "approved_auth": {
    "claude": "api",
    "codex": "api"
  }
}
```

---

## 🌐 环境变量参考 (Environment Variables)

PeerAgent 遵循 POSIX 标准，支持通过环境变量灵活定制运行时行为：

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `PEER_HOME` | `~/.peer-review` | PeerAgent 数据主目录，包含配置文件、模板库与全局调用审计日志。 |
| `PEER_CONFIG` | `$PEER_HOME/config.json` | 显式指定 `config.json` 的绝对路径。 |
| `PEER_TEMPLATES_DIR` | `$PEER_HOME/templates` | 任务 Prompt 模板目录（内置 `review.md`, `plan.md`, `advice.md`, `exec.md`）。 |
| `PEER_DEPTH` | `0` | **防递归调用环境变量**：由调度器在派生子进程时自动注入。若大于等于 1，子进程再次调用 peer 时将被物理拦截（退出码 2）。 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 系统默认 | 调度器拉起子进程时自动继承当前 Shell 的标准网络代理配置。 |

---

## 系统架构与工作原理

<details>
<summary><b>点击展开：调用拓扑、审阅时序与证据优先协议</b></summary>

![调用拓扑](./docs/diagrams/topology.svg)

* **三端发起，两端执行**：Antigravity、Claude 和 Codex 均可作为交互发起端；实际无头执行端为本机安装的 Claude 与 Codex。单文件 `peer` 使用 Python 标准库与工作区文件协议调度，无常驻后台守护进程。

![单次审阅时序](./docs/diagrams/review_sequence.svg)

* **时序与防递归机制**：任务先落盘并经过 STOP 停机锁与 PEER_DEPTH 门禁；元数据写入后，临时后台 `_run` 启动无头 CLI、捕获 Stdio 并生成报告。子进程尝试二次调用时，继承的深度标记触发退出码 2 立即拦截。

![证据优先协议](./docs/diagrams/evidence_first_protocol.svg)

* **证据优先独立审阅**：任务书排版先列用户原话、代码行号与真实 Git Diff，再列待审假设。审阅者先独立核验客观证据，再给出事实、结论与独立性自述，最终由人类主持人核验决策。

详细系统设计请阅读 [架构设计文档 (docs/architecture.md)](./docs/architecture.md)。
</details>

---

## 社区与交流 (Community)

关注作者 X (Twitter) 或加入 Telegram 交流群探讨多 Agent 落地实战：

<p align="center">
  <a href="https://x.com/puck_muling"><b>Twitter (@puck_muling)</b></a> &nbsp;·&nbsp; 
  <a href="https://t.me/puckmuling"><b>Telegram (@puckmuling)</b></a>
</p>

<p align="center">
  <img src="./docs/assets/telegram_qr.png" width="140" alt="Telegram QR Code" />
</p>

---

## 许可证与安全

本项目采用 [MIT 许可证](./LICENSE) 开源。  
安全模型声明与漏洞报告指引详见 [SECURITY.md](./SECURITY.md)。
