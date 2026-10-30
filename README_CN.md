# PeerAgent 🤝（对等代理协作系统）

> **让 Claude Code 与 Codex 互相审阅代码 —— 拒绝虚假共识。**  
> *专为开发者打造的去中心化、零额外 API 账单、订阅原生的跨端多智能体协作网格。*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS | Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)]()

[English Document (README.md)](./README.md) | [安全模型声明](./SECURITY.md)

---

## 👶 10秒看懂：这到底是个什么工具？（小白必读）

如果你平时在用 **Claude Code**、**ChatGPT (Codex CLI)** 或 **Antigravity** 写代码，你一定遇到过这些场景：
* 每次让 AI 帮写了一大段代码，心里总打鼓：“这里面会不会有坑？逻辑到底对不对？”
* 想让另一个大模型帮忙挑刺把关，只能痛苦地**复制代码、切终端、粘贴、发问**，来回折腾好几轮；
* 试过网上的 Multi-Agent（多智能体）开源框架，动不动就要填 API Key，跑一次交叉审阅几十块钱就扣没了……

**装上 PeerAgent 之后，你的电脑就像有了两个随时互相挑刺的顶级 AI 程序员同事：**

* 🗣️ **一句话呼叫对方**：你在 Claude Code 终端写代码时，直接敲 `/codex 帮我检查这段代码`，Codex 就会在后台调起来帮你审查代码行号并直接把结果打在屏幕上；反过来，在 Codex 里敲 `/claude` 就能让 Claude 来审阅。
* 💰 **零额外 API 账单**：直接驱动你电脑上已有的 Claude Pro 或 ChatGPT Plus 网页会员登录态，**不需要充值任何商业 API Token，不花一分额外费用**！
* 🛡️ **安全不踩坑**：审阅模式全走**只读沙箱**，绝不乱碰你的代码；只有你明确点头同意修改时，它才会改，而且改动前会自动帮你做**快照备份**。

> 💡 **简单来说**：它是一个轻量级工具，让你的多个 AI 助手学会“串门聊天与互相找茬”，帮你把关代码质量，而你只需要像架构师一样看汇报、做决定！

---

## 💡 为什么需要 PeerAgent？

当前市面上的多智能体框架（如 CrewAI、AutoGen、LangGraph）在工程实践中常遇到三个痛点：
1. **API 账单昂贵**：跑一次复杂的多方交叉审阅动辄消耗数十万 Token 的商业 API，无法利用开发者已付费的官方会员（ChatGPT Plus/Team、Claude Pro/Team 订阅）。
2. **脱离真实开发环境**：在抽象的云端沙盒或 Python 循环里跑代码，拿不到 IDE 的上下文、官方 CLI 原生工具和本机环境。
3. **“商业互吹”（虚假共识）**：当 Agent A 提出一个存在隐患的方案，Agent B 往往习惯性附和与夸赞，缺乏去查验真实底层代码事实的机制。

**PeerAgent 彻底转变了这一逻辑。** 它是一套极简的 Unix 原生胶水层，连接三大顶级 AI 编程环境：**Google Antigravity (Gemini)**、**Anthropic Claude Code** 与 **OpenAI Codex CLI**。

```
                ┌──────────────────────────────────────┐
                │          用户（人类主持人）            │
                └──────────────────┬───────────────────┘
                                   │ 指令 & 审阅裁决
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   Antigravity    │      │   Claude Code    │      │    Codex CLI     │
│   (Gemini 驱动)  │      │   (Anthropic)    │      │     (OpenAI)     │
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                         │                         │
         │ /codex 或 /claude       │ /codex                  │ /claude
         ▼                         ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    统一调度器：peer (Python CLI)                     │
│  • 任务解包与提示词生成    • 环境变量深度标记 (PEER_DEPTH)            │
│  • 熔断停机锁检测 (STOP)   • 盲审与证据隔离                          │
│  • 只读/可写沙箱管控      • 快照 (Snapshot) 与 Git Diff 跟踪         │
└──────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ 核心设计亮点

1. **零额外 API 账单（Subscription-Native）**：  
   通过无头模式（`claude -p`、`codex exec`）直接驱动本机已登录的官方 CLI，享受您原有的订阅配额，不产生额外按 Token 计费的账单。
2. **去中心化网格（Decentralized Mesh）**：  
   没有常驻的中心主控进程。在 Antigravity 里输入 `/codex`，在 Claude 里输入 `/codex`，在 Codex 里输入 `/claude`——任何一端既是消费者也是提供者。
3. **防虚假共识的双盲审阅（Double-Blind Review）**：  
   审阅方严格隔离彼此的历史输出；任务说明将**底层客观证据（代码文件、行号、Git diff）强制前置**，审阅方必须先核验事实真实性，再看待审方案，并在回复末尾做出“独立性自述”。
4. **防套娃死循环染色（`PEER_DEPTH` Taint Tracking）**：  
   自动在子进程中注入递归深度环境变量。若检测到嵌套互调（`PEER_DEPTH >= 1`），物理阻断退出，彻底杜绝 A 调 B、B 调 A 刷爆会话的灾难。
5. **安全熔断停机锁（Emergency STOP Circuit Breaker）**：  
   精准捕捉账号风控停用、严重 401 凭证失效。一旦触发，立即写入 `STOP` 锁文件物理中断后续所有任务。**严禁任何 AI 代理自动恢复删除，必须由人类排查确认安全后手动删除**。
6. **权限沙箱与快照对比**：  
   只读模式（`review`、`plan`、`advice`）严格锁定在系统级/CLI 只读沙箱中，禁止写文件；可写执行（`exec`、`image`）必须带有用户明确授权原话，并在执行前自动进行工作区快照，做完自动生成 `changes.diff`。

---

## 🚀 快速上手

### 环境要求
* 操作系统：macOS 或 Linux（Windows 推荐使用 WSL；原生 Windows 因依赖 POSIX `fcntl` 暂不支持）。
* Python 3.10+（只使用标准库，无需 `pip install` 繁重依赖）。
* 已安装并登录以下至少一个官方 CLI：
  * **Claude Code**: `npm install -g @anthropic-ai/claude-code && claude login`
  * **Codex CLI**: 官方 CLI 登录（ChatGPT Plus/Team 会员可用）。
  * **Google Antigravity**: 官方前沿 IDE。

### 一键安装

```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent
./install.sh
```

如需开发者模式（修改本地代码立即生效）：
```bash
./install.sh --link
```

运行自检：
```bash
peer doctor
```

---

## 📖 使用示例

### 1. 在 Google Antigravity 中
在对话输入框直接使用斜杠命令：
```text
/codex 审一下当前工作区的登录鉴权代码，看看有没有时序竞争问题
/claude 针对 Redis 缓存穿透出个优化方案
/codex image 生成一张本项目的架构流程图
```

### 2. 在 Claude Code 终端中
在日常编码的 Claude 终端里，直接召唤 Codex 进行对等审阅：
```text
/codex 审阅刚才的改动，看看有没有潜在的 Regression Bug
/codex advice 为什么在高并发下连接池会超时？给个结论
```

### 3. 在 OpenAI Codex CLI 中
在 Codex 会话中直接调用 Claude：
```text
/claude 审阅刚刚重构的前端组件，检查是否存在不必要的渲染
```

---

## 🛡️ 人机治理与方案冻结（Human in the Loop）

PeerAgent 践行**“用户是主持人”**原则：AI 负责准备材料、多方交叉核实、汇报结果并**停下等待人类拍板**。

```text
出方案 (plan) ──> 多方交叉独立审阅 (review) ──> 汇总编号 (S01, S02...)
                                                     │
                                                     ▼
按冻结版安全实施 <── 方案 SHA-256 加密冻结 <── 老大审阅单勾选采纳与终审
```

1. **出方案**：一方提出方案（v001）；
2. **交叉审阅**：另一方独立查验底层代码与行号，出具评审意见；
3. **人类勾选**：用户逐条勾选“采纳 / PASS / 修改”；
4. **加密冻结**：计算方案全文 SHA-256 哈希，运行 `peer freeze <方案.md>` 固定版本，任何未获批准的操作一律不执行。

---

## ⚙️ 配置文件与终端命令行直接调用

PeerAgent 的全局配置位于 `~/.peer-review/config.json`，安装时会自动生成默认模板。

除在对话框使用斜杠命令外，你也可以在任何终端中直接使用 `peer` CLI：
```bash
# 运行环境与账号登录自检
peer doctor

# 发起一次只读审阅
peer ask codex review --request ./task.md --cwd .

# 等待审阅结束并查看结果与 Diff
peer wait <运行编号> --cwd .

# 查看今日调用次数与 Token 消耗统计
peer stats
```

---

## ❓ 常见问题排查（FAQ）

<details>
<summary><b>1. PeerAgent 会扣我的商业 API 费用吗？</b></summary>
不会。PeerAgent 默认直接驱动本机官方已安装登录的 CLI（`claude`、`codex`），使用您的 ChatGPT Plus/Team 或 Claude Pro/Team 订阅配额。只要您在官方 CLI 里使用的是网页/订阅登录，就不会产生额外 API 扣费。
</details>

<details>
<summary><b>2. 提示“熔断停机锁生效中（STOP）”怎么办？</b></summary>
如果检测到严重鉴权失效或疑似封控风控风险，PeerAgent 会在 <code>~/.peer-review/STOP</code> 放置物理熔断锁。这是为了保护您的账号不被高频重试牵连。此时 AI 代理被硬性禁止自动恢复该文件。请您人工核实该工具的登录状态正常后，在终端手动删除该锁文件即可恢复：<code>rm ~/.peer-review/STOP*</code>。
</details>

<details>
<summary><b>3. 为什么不支持原生 Windows？</b></summary>
PeerAgent 的并发进程控制与安全文件排他锁使用了 POSIX 的 <code>fcntl</code> 与进程组信号。Windows 用户请在 <b>WSL2</b>（Windows Subsystem for Linux）环境下运行。
</details>

---

## ⚖️ 架构横向对比

| 特性 | PeerAgent | LangGraph / CrewAI | 单模型原生 CLI | 社区 MCP 单向桥接 |
| :--- | :---: | :---: | :---: | :---: |
| **计费方式** | **官方订阅原生（零额外 API 账单）** | 按 Token 商业 API | 官方订阅 | 官方订阅 |
| **多模型交叉审阅** | **支持（对等网格 Mesh）** | 支持（中央编排器） | 不支持（单一视角） | 易脆弱断连 |
| **防虚假共识协议** | **支持（双盲隔离+证据前置）** | 无 | 无 | 无 |
| **防死循环套娃** | **支持（`PEER_DEPTH` 进程染色）** | 仅依赖轮次上限 | 无 | 无 |
| **致命风控熔断锁** | **支持（`STOP` 停机锁）** | 无 | 无 | 无 |
| **工作区快照与 Diff** | **支持（自动快照对比）** | 无 | 仅依赖 Git | 无 |
| **外部重型依赖** | **零依赖（纯 Python 标准库）** | 极度重型 | 无 | Node/Docker |

---

## 📄 开源许可证

本项目基于 [MIT License](./LICENSE) 开源发布。
