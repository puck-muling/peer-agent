# PeerAgent 🤝

> **让 Claude Code 与 Codex 帮彼此审代码 —— 拒绝附和，查验真实事实。**  
> *专为开发者打造的轻量级、订阅原生、跨端多智能体对等协作网格。*

[![CI](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform: macOS | Linux](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/puck-muling/peer-agent)

[English Document (README.md)](./README.md) | [安全模型声明 (SECURITY.md)](./SECURITY.md) | [架构设计详解 (architecture.md)](./docs/architecture.md) | [贡献指南 (CONTRIBUTING.md)](./CONTRIBUTING.md) | [版本历史 (CHANGELOG.md)](./CHANGELOG.md)

---

## 👶 10秒看懂：它能帮你做什么？

如果你平时在用 **Claude Code**、**Codex CLI** 或 **Google Antigravity** 写代码，你一定经历过这些痛点：
* 每次让 AI 写完一大段代码，心里总打鼓：“这里面会不会漏了边界条件，或者有隐蔽的 Regression Bug？”
* 想让另一个大模型帮忙挑刺把关，只能痛苦地**复制代码 → 切换窗口 → 粘贴提问 → 再把结论搬回来**，来回折腾好几轮；
* 现有的多智能体框架（如 CrewAI、LangGraph）通常需要配置商业 API Key，跑一次交叉审阅产生昂贵的按 Token 计费账单，无法复用你已经开通的会员订阅。

**装上 PeerAgent 之后，就像把另一个顶级 AI 程序员请到了你的当前终端里：**

* 🗣️ **在原终端一句话呼叫对方**：在 Claude Code 编写代码时，输入 `/codex 审阅刚才的改动`，Codex 就会在后台无头运行，把带代码行号的审阅结果直接打印在当前屏幕上；反过来，在 Codex 中输入 `/claude` 就能让 Claude 来审阅。
* 💰 **直接复用现有订阅额度**：通过本机已登录的官方 CLI 驱动，直接消耗你现有的 ChatGPT Plus/Team 或 Claude Pro/Team 订阅配额，无需配置第三方 API Key。
* 🛡️ **严格安全，绝不擅自改动**：审阅模式全走**只读沙箱**，物理禁止修改任何文件；只有在明确授权的可写模式下才会编辑，且执行前后自动生成**快照与 Diff 对比**。

### 以前 vs. 装上 PeerAgent 之后

| 对比维度 | 传统的折腾方式 | 装上 PeerAgent 之后 |
| :--- | :--- | :--- |
| **跨模型交叉审阅** | 手动复制代码 → 切换标签页 → 粘贴发问 → 复制结论返回 | **当前会话直接发起**：输入 `/codex` 或 `/claude`，结果原地返回 |
| **计费与成本** | 商业 API 框架按 Token 计费，跑几次多轮交互成本不菲 | **本机登录态直接驱动**：复用已有官方订阅额度，无需额外充值 |
| **多模型合作态度** | 放在同一个会话容易“商业互吹”，缺乏深入查验 | **独立审阅协议**：强制隔离前序推论，必须先核查代码客观事实 |
| **代码安全边界** | 担心执行权限过大导致误删或篡改文件 | **只读沙箱 + 进程防递归 + 快照 Diff**，未获许可绝不写入 |

---

## 🚀 30秒极简上手

### 1. 前置环境准备
* **操作系统**：macOS 或 Linux（Windows 用户推荐在 WSL2 下使用）。
* **Python**：Python 3.10+（纯标准库实现，无需 `pip install` 繁重依赖）。
* **官方 CLI 工具（按需安装并登录）**：
  * **Claude Code**：`npm install -g @anthropic-ai/claude-code && claude auth login`
  * **Codex CLI**：已安装并完成登录（ChatGPT Plus/Team 会员可用）
  * **Google Antigravity**：已安装（用于 IDE 对话框发起）
  > [!TIP]
  > 您不需要同时装齐所有工具。例如：若只需在 Claude Code 中调 Codex，只需确保本机安装并登录了 `claude` 和 `codex` 即可。

### 2. 一键安装

```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent
./install.sh
```

> [!NOTE]
> **推荐使用 `./install.sh` 进行一键安装**：脚本会自动将核心二进制安装到 `~/.local/bin/peer`，分发审阅模板到 `~/.peer-review/templates`，并将对应斜杠命令注册到 `~/.claude`、`~/.codex` 和 `~/.gemini`。  
> 请确保 `~/.local/bin` 已加入系统的 `PATH` 环境变量中。

### 3. 环境与登录自检

```bash
peer doctor
```
如果输出均显示通过，说明系统已就绪！

### 4. 马上体验第一次跨模型审阅

在你的 **Claude Code** 终端中，输入：
```text
/codex 审阅当前工作区的改动，检查是否有逻辑漏洞。只做审阅，不要修改任何文件。
```
Codex 将在后台自动启动只读沙箱进行审查，几秒后，包含问题行号、影响与修改建议的独立审阅报告就会直接呈现在你的当前会话中！

---

## 🎯 三大高频使用场景

```
  ┌─────────────────────────────────────────────────────────────┐
  │                      典型开发工作流                          │
  │                                                             │
  │   1. 准备提交           2. 重构完毕           3. 方案设计    │
  │   [提交前查回归]       [重构后查遗漏]        [实施前审方案]  │
  │        │                     │                     │        │
  │        ▼                     ▼                     ▼        │
  │  /codex 查 git diff   /claude 查新返回值   /codex 查证据真伪 │
  └─────────────────────────────────────────────────────────────┘
```

### 场景一：代码提交前查回归（Pre-Commit Check）
在 Claude Code 编写完一段功能后，调用 Codex 作为独立的测试把关者：
```text
/codex 审阅当前 git diff，重点排查权限校验、并发竞争与异常边界处理。只做审阅，不修改文件。
```

### 场景二：重构后查调用方遗漏（Post-Refactor Audit）
在 Codex 中完成模块重构后，让 Claude 交叉排查受影响的上下游：
```text
/claude 审阅刚才重构的 auth 模块，检查项目中所有调用方是否已适配新的返回值结构。
```

### 场景三：实施前核实技术方案（Pre-Implementation Review）
在 Antigravity 或终端中提出复杂重构或性能优化方案时：
```text
/codex 针对当前优化方案进行独立审查，先核实所列代码文件与行号是否属实，再指出潜在隐患。
```

---

## 🛡️ 为什么你可以放心让它跑？四大安全防线

PeerAgent 在设计之初就将安全与稳定性放在首位，通过四重安全护栏保护开发者的代码与账号：

1. **严格只读沙箱（Read-Only Enforcement）**：  
   审阅任务（`review`、`plan`、`advice`）启动时强制锁定只读模式（Codex 注入 `--sandbox read-only`，Claude 禁用文件修改工具并切入沙箱环境）。物理杜绝审阅过程中误改任何工程文件。
2. **防套娃死循环染色（`PEER_DEPTH` Anti-Loop）**：  
   子进程自动注入调用深度环境变量。若检测到嵌套互调（例如 Agent A 调起 Agent B，Agent B 试图再次调起 Agent A），环境变量深度门禁立即阻断退出，彻底杜绝无限循环消耗。
3. **安全熔断停机锁（STOP Circuit Breaker）**：  
   精准识别封禁等致命特征。一旦捕获致命异常，立即写入停机锁文件（`~/.peer-review/STOP`），物理阻断后续一切自动调用。**严禁任何 AI 代理自动恢复删除**，必须由人类排查确认后手动解除。（注：普通 401 凭证失效仅提示重新登录，不写停机锁）。
4. **工作区快照与改动比对（Snapshot Diff）**：  
   对于明确授权的可写任务（`exec`），执行前会自动记录工作区文件快照，执行完成后输出 Unified Diff 清单，修改点一目了然。

---

## 📦 进阶功能与系统设计

<details>
<summary><b>1. 查看调用拓扑与工作原理（Architecture Topology）</b></summary>

PeerAgent 采用对等网格拓扑（P2P Mesh），没有常驻的中心后台守护进程：

```
                ┌──────────────────────────────────────┐
                │          用户（人类主持人）            │
                └──────────────────┬───────────────────┘
                                   │ 指令 / 审阅裁决
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
│  • 熔断停机锁检测 (STOP)   • 证据优先独立审阅协议                    │
│  • 只读/可写沙箱管控      • 快照 (Snapshot) 与 Git Diff 跟踪         │
└──────────────────────────────────────────────────────────────────────┘
```

各端既是调用的发起者，也是专业的执行与审阅者。详细说明请参考 [架构设计文档 (docs/architecture.md)](./docs/architecture.md)。
</details>

<details>
<summary><b>2. 在终端直接使用 peer 命令行</b></summary>

除了在交互界面使用斜杠命令外，你也可以在任何终端脚本中直接调用 `peer`：

```bash
# 1. 运行自检与认证状态检查
peer doctor

# 2. 发起一次异步只读审阅任务
peer ask codex review --request ./task.md --cwd .

# 3. 查看进行中的任务状态
peer status <运行编号> --cwd .

# 4. 等待审阅完成并输出报告与 Diff
peer wait <运行编号> --cwd .

# 5. 查看近期调用统计与 Token 用量
peer stats
```
</details>

<details>
<summary><b>3. 方案指纹固化与终审流程（Human-in-the-Loop）</b></summary>

在复杂工程重构中，PeerAgent 贯彻**“人类是主持人”**原则：
* AI 负责出具初版方案 (`plan`)；
* 另一方模型核查代码真实性并提出独立审阅建议 (`review`)；
* 用户审阅汇总意见并拍板最终方案；
* 执行 `peer freeze <方案.md> --cwd .` 计算并固化全文 SHA-256 内容指纹并生成交接语，确保后续执行严格限定在已冻结的范围之内（支持独立指纹固化模式；若在企业内配合私有审阅插件，还可通过 `--review-receipt <目录>` 校验终审签名回执）。
</details>

<details>
<summary><b>4. 配置文件参考 (~/.peer-review/config.json)</b></summary>

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
  "timeout_minutes": {
    "read": 30,
    "write": 60
  }
}
```
</details>

---

## ❓ 常见问题排查（FAQ）

<details>
<summary><b>1. PeerAgent 会扣除我的商业 API 费用吗？</b></summary>

默认不会。PeerAgent 会调用本机已通过官方命令登录的 CLI（`claude`、`codex`）。如果您在这些官方 CLI 中使用的是网页会员/订阅登录（如 ChatGPT Plus/Team 或 Claude Pro/Team），则消耗对应账号的原生配额。具体使用限制和配额政策以官方服务条款为准。
</details>

<details>
<summary><b>2. 终端提示“熔断停机锁生效中（STOP）”该如何处理？</b></summary>

当检测到账号异常封禁等致命特征时，PeerAgent 会在 `~/.peer-review/` 目录下生成 `STOP` 或 `STOP-<agent>` 文件。  
**处理步骤**：
1. 查看提示中指明的具体锁文件路径；
2. 确认触发的原因，并在终端排查该官方 CLI 的可用性与账号状态；
3. 确认一切正常后，手动删除指定的锁文件（例如 `rm ~/.peer-review/STOP-codex`），切勿使用通配符盲目删除所有锁。
</details>

<details>
<summary><b>3. 为什么原生 Windows 暂不支持？</b></summary>

PeerAgent 依赖 POSIX 标准的文件排他锁（`fcntl.flock`）与进程组信号机制（`os.killpg`）来确保多进程并发调度与取消的安全性。Windows 用户建议在 **WSL2**（Windows Subsystem for Linux）环境中运行。
</details>

---

## ⚖️ 方案客观对比

| 考量维度 | 手动转交模式 | 商业 API 编排框架 (LangGraph / CrewAI 等) | PeerAgent |
| :--- | :--- | :--- | :--- |
| **调用流程** | 手动复制材料、切换终端、粘贴发问、整理结论 | 需编写编排脚本或运行独立服务 | **当前终端一条命令发起，后台自动执行并在原处汇报** |
| **计费方式** | 官方订阅（人工手动操作） | 需配置商业 API Key，按 Token 计费 | **官方 CLI 原生驱动，复用现有订阅额度** |
| **环境依赖** | 无 | 通常需要安装多个重型 Python/Node 依赖包 | **纯 Python 3.10+ 标准库，零第三方外部依赖** |
| **审阅隔离** | 依靠人工控制材料 | 依赖开发者自定义构建隔离管道 | **任务协议强制隔离历史推论，证据优先** |
| **防死循环机制** | 人工停止 | 仅依靠轮次计数器限制 | **`PEER_DEPTH` 操作系统环境变量染色，物理阻断** |
| **安全风控熔断** | 无 | 通常依赖异常抛出 | **物理 `STOP` 停机锁，禁止 AI 自恢复，保护账号安全** |

---

## 📄 开源许可证与安全

本项目采用 [MIT License](./LICENSE) 协议开源。  
关于沙箱权限、凭证安全与漏洞反馈渠道，请完整阅读 [安全模型声明 (SECURITY.md)](./SECURITY.md)。
