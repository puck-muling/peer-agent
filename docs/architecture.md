# PeerAgent 架构设计与实现原理

PeerAgent 是一套去中心化的对等多智能体（Decentralized Peer-to-Peer Multi-Agent）代码审阅与协作系统。本文档详细剖析其设计思想、调度原理、通信机制与安全防线。

---

## 1. 核心架构拓扑

不同于以中央 Python 进程为核心的编排系统，PeerAgent 采用对等网格拓扑（Peer-to-Peer Mesh）：

```
    ┌──────────────────────┐          ┌──────────────────────┐
    │  Antigravity (Gemini)│          │   Claude Code CLI    │
    └──────────┬───────────┘          └──────────┬───────────┘
               │                                 │
               │ /codex, /claude                 │ /codex
               ▼                                 ▼
         ┌─────────────────────────────────────────────┐
         │             peer 统一调度核心               │
         │      (单文件 Python CLI，仅依赖标准库)      │
         └─────────────────────┬───────────────────────┘
                               ▲
                               │ /claude
                               │
                    ┌──────────┴──────────┐
                    │      Codex CLI      │
                    └─────────────────────┘
```

* **发起端（Consumer）**：Antigravity IDE、Claude Code CLI、Codex CLI 均可作为发起源。
* **执行端（Provider）**：由本机安装的官方 `codex` CLI 和 `claude` CLI 在后台无头拉起，负责具体的代码审查与分析。

---

## 2. 调度与文件协议（File-Based Protocol）

AI 代理之间不依赖复杂的 RPC 守护进程或常驻 WebSocket，而是基于标准 Unix 文件协议和标准输入输出（Stdio）完成解耦：

1. **请求落盘（Request Phase）**：
   * 发起端将任务描述与底层证据路径写入工作区的 `.peer-review/requests/<timestamp>-<agent>-<kind>.md`。
2. **异步拉起（Spawn Phase）**：
   * `peer ask <agent> <kind>` 读取请求，识别只读或可写意图；
   * 后台拉起无头 CLI 进程（Codex 注入 `--sandbox read-only`，Claude 注入 `--permission-overrides` 剥离写工具）；
   * 为当前任务分配唯一的 `run_id`，并记录元数据到 `.peer-review/runs/<run_id>/meta.json`。
3. **轮询等待与回收（Wait Phase）**：
   * `peer wait <run_id>` 监听进程状态并捕获 Stdio 输出流；
   * 输出格式化 Markdown 报告至 `.peer-review/runs/<run_id>/response.md`，包含用量统计、实际模型、执行耗时与改动记录。

---

## 3. 防套娃死循环机制（Anti-Recursion Taint Tracking）

多智能体相互调用时，最危险的场景是 **A 调 B，B 以为还要做某事又调了 A**，陷入递归死循环，导致账户 Token 耗尽。

PeerAgent 采用类似**污点跟踪（Taint Tracking）**的环境变量染色原理：
```python
# 进程环境组装
curr_depth = int(src.get("PEER_DEPTH", "0"))
env["PEER_DEPTH"] = str(curr_depth + 1)
```
在每次进入调用门禁时，严格校验深度标记：
```python
if is_nested_depth(os.environ.get("PEER_DEPTH")):
    raise PeerError("检测到嵌套调用：禁止在任务进程中再次调用 peer ask，防止递归死循环。")
```
任何第二层代理如果尝试再次调起对等模型，会被操作系统级环境变量检查物理阻断，退出码为 `2`。

---

## 4. 证据优先的独立审阅协议（Evidence-First Review Protocol）

在多模型讨论中，后发言的模型往往倾向于附和先发言模型的观点（回音室与附和效应）。

PeerAgent 通过任务协议与提示词规范降低附和倾向：
1. **任务书隔离历史推论**：下发给审阅端的文件严格排除其他模型的历史中间 runs 结论，仅提供当前任务目标与代码背景。
2. **证据前置（Evidence-First）**：任务书排版必须将用户原话、代码文件、Git diff 列在首部，待审推断列在后部。系统提示词要求审阅模型必须先通过只读工具核查代码第几行是否确实存在缺陷，再给审阅结论。
3. **独立性自述（Independence Disclosure）**：审阅回复末尾必须包含独立性自述，说明是否受到先入为主假设的影响。

> [!NOTE]
> 独立审阅规范依赖任务协议和提示词约束，而非操作系统级的文件读取白名单；在提示词遵循度不同的模型上，仍需人类最终核验。

---

## 5. 权限沙箱与快照比对

* **只读沙箱（Read-Only）**：
  * Codex 强制注入 `--sandbox read-only`；
  * Claude Code 配置拒绝规则 `deny: ["Edit(~/**)", "Edit(./**)"]`，且沙箱内 Bash 禁网。
* **可写快照（Snapshot Diff）**：
  * 可写调用前遍历工作区执行快照，排除 `.git`、`node_modules` 等缓存；
  * 执行完成后对比生成精确的 Unified Diff，由人类审查确认。
