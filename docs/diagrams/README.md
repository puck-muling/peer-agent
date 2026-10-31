# PeerAgent 架构图与嵌入说明

本目录提供三组语义对应的 Mermaid 源码与独立 SVG。SVG 使用固定的 1600 × 900（16:9）深色构图，可直接用于 README、网页或视频剪辑；所有图形与文字均为标准 SVG，无脚本、外部图片、外部样式或字体下载。文字使用系统 `sans-serif`，显示中文需要系统自带中文字体。

SVG 为人工排版的矢量构图，不是 Mermaid 的逐像素导出。修改 `.mmd` 后需同步维护对应 `.svg`；SVG 的 metadata 保存配套源码的 SHA-256，用于识别版本是否同步。

| 图解 | Mermaid 源码 | SVG 成图 | 用途 |
| --- | --- | --- | --- |
| 调用拓扑 | [topology.mmd](./topology.mmd) | [topology.svg](./topology.svg) | 区分三个发起端与两个执行端，以及只读 / 可写权限 |
| 单次审阅时序 | [review_sequence.mmd](./review_sequence.mmd) | [review_sequence.svg](./review_sequence.svg) | 展示请求落盘、门禁、后台运行、Stdio 回收、报告与递归阻断 |
| 证据优先协议 | [evidence_first_protocol.mmd](./evidence_first_protocol.mmd) | [evidence_first_protocol.svg](./evidence_first_protocol.svg) | 展示任务书分层、独立核验与人类最终决策 |

## 已嵌入中文 README 的对应内容

以下内容已整合至仓库根目录的 `README.md`（中文主页）“系统架构与工作原理”：

```markdown
![PeerAgent 调用拓扑：三个发起端通过 peer 调用 Claude 或 Codex 两种执行端](./docs/diagrams/topology.svg)

Antigravity、Claude 和 Codex 都可发起任务；实际无头执行端只有 Claude 与 Codex。单文件 `peer` 使用 Python 标准库与工作区文件协议调度，没有常驻后台守护进程。审阅使用只读模式，明确授权的可写任务附调用前快照与调用后 Diff。

![PeerAgent 单次审阅时序与 PEER_DEPTH 递归阻断](./docs/diagrams/review_sequence.svg)

任务先落盘并经过 STOP 与 PEER_DEPTH 门禁；元数据写入后，临时后台 `_run` 启动无头 CLI、捕获 Stdio 并生成报告。`peer wait` 轮询状态并读取结果。子进程再次调用 `peer ask` 时，继承的深度标记触发退出码 2；普通只读审阅不生成快照 Diff。

![PeerAgent 证据优先独立审阅协议与人类核验](./docs/diagrams/evidence_first_protocol.svg)

任务书先列用户原话、代码行号与真实 Diff，再列待审假设。审阅者先独立核验，再给出事实、结论与独立性自述，最终由人类主持人核验并决定后续行动。该协议依靠任务材料和提示词约束，不是操作系统文件读取白名单。
```

## 已嵌入英文 README 的对应内容

以下内容已整合至仓库根目录的 `README.md`“Architecture & Invocation Topology”：

```markdown
![PeerAgent topology: three consumers invoke two headless CLI providers through peer](./docs/diagrams/topology.svg)

Antigravity, Claude, and Codex can initiate tasks. Only Claude and Codex are execution providers. The single-file `peer` CLI uses the Python standard library and workspace files, with no persistent orchestration daemon. Reviews run in read-only mode; explicitly authorized write tasks include pre-run snapshots and post-run diffs.

![PeerAgent review lifecycle and PEER_DEPTH recursion guard](./docs/diagrams/review_sequence.svg)

A request is saved and checked against STOP locks and PEER_DEPTH. Metadata is written before a temporary background `_run` process launches the headless CLI, captures Stdio, and produces the report. `peer wait` polls status and reads the result. A nested `peer ask` inheriting a depth of at least 1 is rejected with exit code 2. Ordinary read-only reviews do not produce snapshot diffs.

![Evidence-first review: primary evidence, independent checks, disclosure, and human verification](./docs/diagrams/evidence_first_protocol.svg)

Task files place user quotes, source line references, and actual diffs before hypotheses. Reviewers verify primary evidence, report facts and conclusions, and provide an independence disclosure. A human host verifies the findings and decides what happens next. This is a task-and-prompt protocol, not an operating-system file-read allowlist.
```

## 已嵌入 architecture.md 的对应内容

以下内容已整合至 `docs/architecture.md` 第 1、2、4 节：

```markdown
![三端发起、两端执行的调用拓扑](./diagrams/topology.svg)

三个交互发起端共享同一个文件协议入口，执行端仅为本机 Claude 与 Codex。`peer` 是按调用启动的单文件 Python CLI；后台 `_run` 仅管理当前任务，不是常驻守护进程。Antigravity 不承担无头执行端角色。

![请求落盘、门禁、异步执行与结果回收时序](./diagrams/review_sequence.svg)

`cmd_ask` 先校验 STOP 与调用深度，再校验请求及登录方式，保存任务副本；可写模式取得写锁并记录调用前快照。它先写入 `meta.json` 与排队状态，再启动临时后台 `_run`。`cmd_run` 复查 STOP、拉起执行端并以线程捕获 stdout/stderr；执行后解析结果，可写模式进行快照比对，最后生成 `response.md` 与终态。`cmd_wait` 负责轮询与读取报告，不捕获执行端的 Stdio。继承 PEER_DEPTH ≥ 1 的嵌套 `peer ask` 在入口退出，退出码为 2；STOP 优先命中时退出码为 3。

![证据前置、假设后置与人类终审](./diagrams/evidence_first_protocol.svg)

证据优先协议要求先核验原始需求、代码及 Diff，再阅读待审方案与主代理推断；输出事实与证据缺口，并按审阅模板提供独立性自述。对历史 runs 回复的读取限制是提示词规范，不是 OS 文件白名单；最终仍需人类核验。任务材料的分层与审阅质量依赖调用方和审阅端遵循协议，CLI 不自动验证其真实性或独立性。
```

## 实现依据与边界

本次核对基于当前工作树中的实现，不依赖历史审阅结论。

| 事实 | 实现依据 |
| --- | --- |
| 执行端仅为 codex / claude；review / plan / advice 只读，exec / image 可写 | [bin/peer](../../bin/peer) 的 `AGENT_NAMES`（93 行）、`KINDS`（94–100 行） |
| 子进程继承深度标记；入口先查 STOP，再查递归 | [bin/peer](../../bin/peer) 的 `child_env`（200–217 行）、`is_nested_depth` / `cmd_ask`（1010–1027 行）；`die` 默认退出码 2（159 行） |
| Claude 只读移除 Edit / Write，Bash 禁网；WebSearch / WebFetch 仍可用 | [bin/peer](../../bin/peer) 的 `build_args`（681–731 行）；不能将其描述为执行端全部联网能力被禁用 |
| 元数据先写入，后台 _run 后启动 | [bin/peer](../../bin/peer) 的 `cmd_ask`（1105–1147 行） |
| runner 捕获 Stdio，wait 轮询状态并读报告 | [bin/peer](../../bin/peer) 的 `pump`（1358 行）、`cmd_run`（1456–1467 行）、`cmd_wait`（1657–1683 行） |
| 快照和改动清单仅属于可写模式；Diff 有排除项和容量限制，不保证覆盖所有内容 | [bin/peer](../../bin/peer) 的 `snapshot` / `compare`（365–448 行）、可写比对（1526–1544 行） |
| 原始证据先查、假设后读、历史 runs 限制属于提示词；独立性自述来自回复模板 | [bin/peer](../../bin/peer) 的 `build_prompt`（643–665 行）、[review 模板](../../templates/review.md)、[architecture.md 第 4 节](../architecture.md#4-证据优先的独立审阅协议evidence-first-review-protocol) |

时序图以普通后台审阅的正常主线为骨架，展示 STOP、递归阻断以及可写快照分支；Mermaid 版包含更多条件说明，SVG 为适合 16:9 阅读的压缩排版，不穷举所有启动失败、超时和信号处理路径。`wait` 超时或状态未知不授权自动重发请求。图中“可写 exec”仅说明已授权的执行模式，不代表审阅报告本身授予写权限。

## 嵌入与对齐状态

以上三张图解与对应说明已全量嵌入至仓库核心文档：
- [README.md](../../README.md)（中文主页架构与原理说明）
- [README_EN.md](../../README_EN.md)（英文主页架构与原理说明）
- [architecture.md](../architecture.md)（系统架构设计与实现原理）

SVG 与 Mermaid 源码保持双向同步，修改 `.mmd` 源码后请通过元数据 SHA-256 校验保持 `.svg` 同步更新。
