<div align="center">

**简体中文** | [English](README_EN.md)

# PeerAgent 🤝

**让 Claude Code 和 Codex 互相审代码，少一次复制粘贴，多一份独立意见。**

在当前会话里请另一个模型检查代码，审阅意见直接带回来，省去切窗口和搬运结果。

使用本机官方 CLI · 支持已有订阅登录 · 审阅任务只读 · 防静默扣费锁 · 封号熔断保护 · 核心无需 Python 第三方包

> 🧪 **0.1.4 公开试用版**：目前处于试用阶段，欢迎反馈。遇到问题或有建议，请到 [GitHub Issues](https://github.com/puck-muling/peer-agent/issues) 留言。

[安装与初次体验](#安装与初次体验) · [生态定位与同类对比](#生态定位与同类对比) · [使用示例](#使用示例) · [费用与权限边界](#费用与权限边界) · [常见问题与网络排障](#常见问题与网络排障)

[![CI](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/puck-muling/peer-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

</div>

## 演示视频

https://github.com/user-attachments/assets/6e51e140-c110-4447-9d02-287796e750cd

▶ [备用观看直链 / 下载 MP4](https://cdn.jsdelivr.net/gh/puck-muling/peer-agent@main/docs/assets/demo.mp4)（2 分 21 秒，中文旁白与字幕）

> [!NOTE]
> **同名项目说明**：本项目（`puck-muling/peer-agent`）是面向代码工程实战的**多智能体安全治理与对等审查中间件**（基于本地官方 CLI、零第三方 pip 依赖、内置计费门禁与封号熔断）；不同于 `hirak99/peer-agent`（基于 HTTP/FastAPI 的伴生 Agent 框架），二者架构与应用场景完全不同。

适合已经使用 Claude Code 或 Codex、想让另一个模型多检查一遍的开发者。需要 **Python 3.9+ 和被调用模型对应的官方 CLI**（缺的话一键安装会自动帮你装）；订阅登录仍会消耗对应额度，实际计费取决于登录方式和所用工具。安装面向 macOS / Linux；Windows 用户请在 WSL2 中安装和使用（原生 Windows 仅做了文件锁与进程终止的降级兼容，`install.sh` 不支持原生 Windows）。

## 生态定位与同类对比：不仅是调用通道，更是安全治理层

随着官方生态演进，社区常有疑问：“现在已经有了官方插件（如 `openai/codex-plugin-cc`）和 MCP 工具（如 `consult`），PeerAgent 是否会被取代？”

**答案是：纯调用转发很容易做，但多 Agent 协同落地的核心矛盾是安全失控与成本治理。**

普通的转发通道（Plugin 或 MCP）只做“把 Prompt 转发给另一模型”，面对真实工程研发时有四大痛点：
1. **静默切到按量扣费**：终端意外残留 API Key 或登录态失效掉入 API 计费，导致数百美元的天价账单；
2. **并发死循环连带封号**：遇到地区 IP 或鉴权异常时，自动化脚本死循环重试，导致整个主账号被直接封禁；
3. **附和谄媚效应（回音室）**：后发言模型倾向于附和先发言模型的推论，丧失真正独立的审查价值；
4. **长上下文遗忘与方案推翻**：多轮对话后模型自我遗忘，偏离或推翻已定架构，引入范围蠕变。

PeerAgent 的核心护城河是**将调用能力深嵌在一套坚固的防御体系中**：

| 评估维度 | PeerAgent (本项目) | 官方插件 (openai/codex-plugin-cc) | MCP 模式 (neelsatyavolu/consult 等) | 伴生服务端 (hirak99/peer-agent) |
| :--- | :--- | :--- | :--- | :--- |
| **定位与形态** | **安全治理与对等互审中间件** | 单向转发插件 | 基于 MCP 协议的模型咨询 | HTTP/FastAPI 伴生代理服务 |
| **协作拓扑** | **Claude ↔ Codex ↔ Antigravity 双向闭环** | Codex → Claude 单向 | 主持端 → 其它模型星型转发 | 客户端 ↔ 伴生服务端 |
| **计费防偷切锁 (`approved_auth`)** | ✅ **发请求前拦截校验，防静默 API 扣费** | ❌ 无校验，易受环境变量偷切 | ❌ 依赖底层环境与自律 | ❌ 依赖自行鉴权配置 |
| **封号连带熔断锁 (`STOP`)** | ✅ **进程组信号拦截与停机熔断：子进程结束后扫描致命风控特征，写入 STOP 锁阻断后续调用** | ❌ 进程直接报错退出，无停机保护 | ❌ 无风控熔断保护 | ❌ 无 |
| **落地改前快照与 Unified Diff** | ✅ **自动执行前物理快照 + 落地比对 Diff** | ❌ 无改前快照，需依赖 git 手动比对 | ❌ 依赖客户端自身实现 | ❌ 无 |
| **架构决策指纹固化 (`peer freeze`)** | ✅ **SHA-256 方案指纹 + 独立交接语** | ❌ 无 | ❌ 无 | ❌ 无 |
| **防共谋盲审协议** | ✅ **工具名单限制与提示规范：只读工具名单 + 要求不采信历史回复、证据前置（非操作系统级隔离）** | ❌ 上下文直接串联，易谄媚附和 | ❌ 由具体 Prompt 决定 | ❌ 无规范 |
| **运行依赖与环境** | **Python 标准库单文件 CLI，零 pip 依赖** | 依赖特定宿主插件生态 | 依赖 Node / MCP 运行时 | 依赖 FastAPI / pip 依赖生态 |

## 安装与初次体验

### 先确认你要从哪里调用

| 使用方式 | 需要准备什么 |
| :--- | :--- |
| 在 Claude Code 会话中输入 `/codex` | 可用的 Claude Code 会话，以及本机已安装、已登录的 Codex CLI |
| 在 Codex 会话中调用 `/claude` 技能 | 可用的 Codex 会话，以及本机已安装、已登录的 Claude Code CLI |
| 在 Antigravity 中调用任一模型 | Antigravity 主持环境，以及被调用模型对应的官方 CLI 和登录状态 |
| 直接用 `peer ask` 调用 | Python 3.9+，以及被调用模型对应的官方 CLI 和登录状态 |

上面这些不用自己一项项准备：下面的一键安装会自动检查，缺什么装什么。

### 一键安装（推荐，macOS / Linux）

打开“终端”，复制下面这一行，粘贴后按回车：

```bash
curl -fsSL https://raw.githubusercontent.com/puck-muling/peer-agent/main/bootstrap.sh | bash
```

> 在国内、需要代理才能上 GitHub？请直接用下面“国内网络”那一行，否则第一步下载就会失败。

它会：

1. 下载最新发布版本，装好 `peer` 命令和各端技能；
2. 检查这台电脑缺什么：Python、Claude Code、Codex、有没有登录、能不能连上 Claude / OpenAI；
3. 把要做的事列出来，**你只需要按一次回车**，它就会自动用官方命令安装缺的工具、打开浏览器让你登录、网络不通时问你代理地址；
4. 最后再检查一遍，告诉你现在能怎么用。

已经装好、登录好的不会重复处理；任何一步失败，都会直接告诉你原因和下一步怎么做。

- **国内网络**：连 GitHub、Claude、OpenAI 一般都需要代理。先打开代理软件，再用下面这一行（**两处 7890 都换成你代理软件里显示的端口**，Clash 默认一般是 7890）：

  ```bash
  curl -x http://127.0.0.1:7890 -fsSL https://raw.githubusercontent.com/puck-muling/peer-agent/main/bootstrap.sh | bash -s -- --proxy http://127.0.0.1:7890
  ```

  开头的 `-x` 让“下载安装脚本”这一步走代理；末尾的 `--proxy` 让后面的下载、安装 Claude Code / Codex 也走代理，并保存给 peer（写进配置的 `child_env`），之后调用 Claude / Codex 同样会用它。两处缺一不可。

- **想先看看脚本再运行**：

  ```bash
  curl -fsSL https://raw.githubusercontent.com/puck-muling/peer-agent/main/bootstrap.sh -o peer-bootstrap.sh
  less peer-bootstrap.sh
  bash peer-bootstrap.sh
  ```

  需要代理时，第一行的 `curl` 后面加 `-x http://127.0.0.1:7890`，最后一行改成 `bash peer-bootstrap.sh --proxy http://127.0.0.1:7890`。

- **Mac 第一次用 Python**：如果系统弹窗要求安装“命令行开发者工具”，点【安装】，装完再运行一次上面的命令即可。
- **Windows**：目前请先安装 WSL2，在 WSL2 的终端里运行上面的命令。
- 安装脚本只运行官方安装命令，执行前会显示出来：Claude Code 用 `curl -fsSL https://claude.ai/install.sh | bash`，Codex 用 `curl -fsSL https://chatgpt.com/codex/install.sh | sh`。不想自动安装可以加 `--no-install-deps`，只检查不安装。

### 从源码安装（开发者）

在源码目录运行 `./install.sh`，效果和一键安装相同，也会检查并补齐缺的环境：

```bash
git clone https://github.com/puck-muling/peer-agent.git
cd peer-agent
./install.sh
peer doctor
```

安装默认采用**文件复制**：将 `peer` 复制到 `~/.local/bin/peer` 和 `$PEER_HOME/bin/peer`（`PEER_HOME` 默认是 `~/.peer-review`），并复制模板与各端技能；配置不存在时生成默认配置，还会按 Shell 情况补充 PATH。开发时可显式选择 `./install.sh --link` 使用软链接。复制安装后，修改仓库不会自动更新已安装副本。

> [!IMPORTANT]
> 若通过 `pip install` 安装，只会装上 `peer` 命令本身，**不会注册各端 Agent 技能**（`/codex`、`/claude`）。请在仓库目录中再运行一次 `./install.sh`，把技能安装到 Claude、Codex（`~/.codex/skills` 与 `~/.agents/skills`）和 Antigravity 的技能目录。

如果当前终端还找不到 `peer`，可先用固定路径检查：

```bash
"$HOME/.local/bin/peer" doctor
```

`peer doctor` 是核心环境诊断与安全锁自检工具，用于查看 CLI 状态、登录类别一致性与 STOP 熔断锁。**不要把 `peer doctor --approve` 当作通用修复命令**：它是防静默扣费锁（`approved_auth`）的核准工具，会把当前可识别的登录类别写入批准配置；请先核实输出与计费方式，确认安全后再由本人决定是否执行。

### 发起第一次审阅

安装技能后，重新打开或刷新主持端客户端，确认技能已加载。进入你要审阅的项目，在 **Claude Code** 中输入：

```text
/codex review 审阅当前 git diff，重点检查异常边界。只读，不要修改文件。
```

在 **Codex** 中可调用 `/claude` 技能（具体入口以客户端技能菜单为准）：

```text
/claude review 审阅当前 git diff，检查旧功能是否受影响。只读，不要修改文件。
```

下面仅展示可能返回的内容格式，**不是历史任务的原始报告**；路径和行号为示意，实际发现与耗时取决于任务：

```markdown
## 审阅意见（示意）

- 位置：src/handler.py:42（示意）
- 问题：失败分支没有关闭资源，可能导致重复请求后连接耗尽。
- 待验证：检查调用方是否负责释放，并运行覆盖失败分支的测试。
```

报告回来后先核查问题位置和触发条件，再决定是否修改。另一个模型也可能漏查或判断错误。

## 使用示例

| 你想做什么 | 可以怎么说或怎么调用 |
| :--- | :--- |
| 请 Codex 检查改动 | `/codex review 审阅当前 git diff，检查并发和异常边界。只读。` |
| 请 Claude 看重构方案 | `/claude plan 根据当前模块提出重构方案，不要修改文件。` |
| 批准一个具体修复 | `/codex exec 授权修改：修复刚才确认的资源释放问题，仅改对应函数。` |
| 生成图片（仅 Codex） | `/codex image 授权生成：画一张调用流程图，保存到项目指定素材目录。` |
| 保存方案版本和内容指纹 | `peer freeze ./方案-v2.md --cwd .` |
| 检查环境与安全锁状态 | `peer doctor` |
| 批准/更新登录计费模式 | `peer doctor --approve`（核实后由本人执行，防止静默扣费） |
| 手动急停全局自动调用 | `touch ~/.peer-review/STOP`（解除须人工排查后删除，严禁 Agent 自动恢复） |

### 审阅、方案和执行怎么区分

斜杠技能按关键词判断意图，属于启发式路由，并不能理解所有自然语言表达。三端技能（Claude Code 的 `/codex`、Codex 的 `/claude`、Antigravity 的 `/codex` 与 `/claude`）都调用同一个 `peer route --request <任务说明>` 判定，规则一致；任务说明有“# 任务”小节时只看该小节。匹配顺序：

1. 开头明确写 `exec` / `review` / `plan` / `advice` / `image` 时按该类型处理；显式 `exec` 遇到只读或禁止修改要求会降级为 `review`。
2. 未显式指定时，否定词和审阅词优先于修改词。例如“审阅当前修改”“检查修复结果”按 `review` 处理。
3. 随后依次匹配方案词、出图词、修改词和建议词；未命中时默认 `review`。
4. 提问或要讲解的句子（带问号、句末“吗 / 呢”，或含“什么 / 怎么 / 是否 / 解释 / 原理”等）即使出现“实现”“修复”“创建”等词，也不会进入可写的 `exec`，按 `advice` 处理。“能帮我修复这个 bug 吗”这类请求同样只读，要修改请以 `exec` 开头或直接写成指令。

需要确定类型时，可直接用 `peer ask` 传入，不经过斜杠技能的意图判断；也可以先用 `peer route` 查看某份任务说明会被判成什么类型。

`review`、`plan`、`advice` 采用只读执行配置；`exec`、`image` 可写，需要用户授权原话。请写清允许修改哪些文件，并核对发起的任务类型。

### 在终端直接调用

先在项目中准备任务说明文件 `review-task.md`，写清要检查的文件、原始需求和回复要求，例如：

```markdown
# 任务

只读审阅当前 git diff，重点检查异常处理。不要修改文件。

## 回复格式

列出问题位置、触发条件、依据和仍需验证的事项；没有发现也请明确说明。
```

然后调用对应 CLI：

```bash
peer ask codex review --request ./review-task.md --cwd .
```

命令默认后台运行，返回运行编号。将下面的 `RUN_ID` 替换成该编号：

```bash
peer wait RUN_ID --cwd .
peer status RUN_ID --cwd .
peer stats
```

`peer wait` 等待超时只表示还没有等到结果，应查询或继续等待原编号；不要重新 `ask`。

可写任务使用单独的任务说明，并传入用户已经确认的授权原话：

```bash
peer ask codex exec --request ./fix-task.md --cwd . \
  --quote '仅修复已确认的资源释放问题'
```

程序只检查 `--quote` 是否非空，不会判断这段话是否充分授权了每项操作。修改前快照位于 `.peer-review/runs/<运行编号>/snapshot/`，完成后生成 `changes.md` 和 `changes.diff`；快照限制见下文。

### Antigravity 主持双方审阅

可以分别请 Claude 和 Codex 核查相同的源码和需求，再由主持端汇总问题位置、证据和分歧。任务说明要求先查原始证据，避免直接采信已有结论；**这不是操作系统级的盲审隔离**。请求正文会直接传给被调用方，主持端应避免把另一方结论混入独立审阅请求。

方案经人确认后，可保存冻结副本：

```bash
peer freeze ./方案-v2.md --cwd .
peer verify ./方案-v2_冻结v001.md
peer since-freeze ./方案-v2_冻结v001.md
```

示例假定这是该文档的第一次冻结，实际文件名以输出为准。`freeze` 创建 `*_冻结vNNN.md`、内容指纹、项目快照与交接语；默认是独立模式。可选的 `--review-receipt <目录>` 会校验外部终审回执；未提供回执时，冻结本身不代表已获批准。SHA-256 用于检查内容是否变化，不会阻止文件被编辑，也不是实施授权。

<details>
<summary>完整命令索引</summary>

| 命令 | 参数与说明 |
| :--- | :--- |
| `peer doctor` | `[--approve]`：环境诊断与安全锁自检（巡检 CLI、登录一致性与 STOP 熔断锁）；显式 `--approve` 时记录当前可识别的登录类别为新基线 |
| `peer ask <codex\|claude> <kind>` | `--request <文件> --cwd <目录>`；`kind` 为 `review` / `plan` / `advice` / `exec` / `image`，其中 `image` 仅 Codex 支持 |
| 调用可选参数 | `--quote <原话>`、`--model <模型>`、`--effort <强度>`、`--service-tier <层级>`、`--add-dir <目录>`、`--caller <名称>`、`--foreground`、`--web` / `--no-web`（只读调用 Claude 时本次开放 / 关闭 WebSearch / WebFetch，默认开放）；可写类型必须有 `--quote` |
| `peer wait <运行编号>` | `--cwd <目录> [--timeout <秒>]`：等待原任务并显示报告 |
| `peer status [运行编号]` | `--cwd <目录>`：查看某次任务或最近 10 次任务 |
| `peer freeze <方案文档>` | `--cwd <目录> [--quote <原话>] [--review-receipt <目录>]`：保存冻结副本与指纹 |
| `peer verify <冻结版文件>` | 比较冻结副本与记录的 SHA-256 |
| `peer since-freeze <冻结版文件>` | 比较项目与冻结时快照，并生成改动记录 |
| `peer stats` | 显示当日调用与可取得的用量统计；不等同于官方账单 |
| `peer route` | `--request <文件>`：按任务说明判断类型，输出 `{"kind", "quote"}`；三端技能共用 |

</details>

## 费用与权限边界

| 机制 | 实际做什么 | 需要知道的限制 |
| :--- | :--- | :--- |
| 登录类别检查 (`approved_auth`) | 调用前比较当前类别与 `approved_auth`，不一致时停止，退出码 3；配套工具为 `peer doctor [--approve]` | 不能验证授权范围、可用余额或最终账单。支持已有 CLI 订阅登录，仍消耗额度；API 登录按相应规则计费 |
| 只读任务 | 给 Codex 设置 `read-only` 沙箱；给 Claude 限制工具和 Bash 沙箱权限，默认开放 WebSearch / WebFetch 便于查资料（可用 `claude_read_web: false` 或 `--no-web` 关闭），并在任务说明中要求只读 | 依赖目标 CLI 与系统沙箱实现；PeerAgent 仍会写入任务、日志等过程文件，不代表整台机器不写文件 |
| 可写授权 | `exec` / `image` 要求非空授权引文，使用可写配置 | 引文存在不等于程序理解了授权；实施范围仍需人和执行方核对 |
| 可写沙箱 | Codex 用 `workspace-write` 沙箱；Claude 的 Bash 默认进沙箱（只能写项目、`--add-dir` 目录和 `$TMPDIR`，不能联网），Edit / Write 只自动放行项目和 `--add-dir` 目录内的改动 | 需要联网（如安装依赖）或写项目外的任务会失败；确认风险后可设 `claude_exec_sandbox: false` 恢复不加沙箱 |
| 改前快照 | 保存可复制的文本内容并记录文件信息，改后对比 | 跳过部分目录和疑似敏感内容；大文件、二进制与总量等有限制，不是完整备份或自动回滚 |
| 防递归标记 | 子进程继承 `PEER_DEPTH` 后，嵌套 `peer ask` 被拒绝，退出码 2 | 只覆盖经过该入口且保留标记的调用，不能阻止所有可能的模型循环 |
| STOP 熔断锁 (`STOP`) | 检测到特定封禁或地区错误后，写入停机锁文件阻止该渠道后续调用；配套工具为 `peer doctor` 诊断与手动急停/复位 | 依赖错误匹配，不能保证避免封号；需人工排查，严禁 Agent 自动删除 STOP 文件 |
| 独立审阅要求 | 提示审阅者先查源码、需求和 diff，再判断主张 | 不保证模型意见正确、互不影响或必然达成共识 |

快照默认跳过 `.git`、`node_modules`、`.peer-review` 等目录。单个文本文件超过 2 MiB 不复制，超过 8 MiB 的文件只记录大小和修改时间；对比时大小和修改时间都没变的文件沿用快照指纹，不再重新计算（与 git 的判断方式相同）；复制总量上限 300 MiB，文件数上限 40,000。具体规则见 [`bin/peer`](./bin/peer)，完整权限说明见 [SECURITY.md](./SECURITY.md)。

### 核心安全锁与管理工具：防静默扣费 & 致命封号熔断

在多 Agent 协同与自动审阅中，开发者最担心的两大风险是：**“原本走会员订阅，结果被环境变量或凭据失效偷切到按量 API 导致天价扣费”**，以及**“遇到网络风控或账号异常时，自动化脚本疯狂死循环重试导致连带封号”**。PeerAgent 在底层内置了两道硬核安全门禁与配套管理工具：

#### 1. `approved_auth` 认证防静默扣费锁

* **拦截原理**：PeerAgent 在发起任何调用（`peer ask`）前，会强制调用官方 CLI 的真实鉴权检查并扫描环境变量，把当前登录方式（`subscription` / `api` / `unknown`）与配置文件中的 `approved_auth`（默认均为 `subscription`）逐一比对。
* **为什么防扣费**：如果你平常使用 Claude Pro 或 ChatGPT Plus 订阅，但 CLI 登录态失效或被切换成 API 计费模式，PeerAgent 检测到当前登录状态与已核准模式（`approved_auth`）不一致时，会**在发起调用前主动阻断并退出**（退出码 3），明确输出差异并拒绝调用。环境变量里的 Key 两端处理一致：`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`CODEX_API_KEY` 都只会在子进程环境中被移除并给出提示，登录类别按官方 CLI 在同样（已去掉 Key）的环境里回报的实际登录方式判定，不会因为环境里残留 Key 就误判或阻断。它只比对登录类别，不能验证授权范围、可用余额或最终账单。
* **配套管理工具**：
  * **诊断工具 `peer doctor`**：一键打印各渠道登录状态及与 `approved_auth` 的比对结果（显示 `✅ 与已确认一致` 或 `⚠️ 与已确认不一致`）。
  * **授权工具 `peer doctor --approve`**：若你确认有意使用官方 API 计费，可在人工核验终端输出与资费预期后，显式运行该命令将当前模式固化为新基线。此操作严禁由 AI Agent 自动调用。

#### 2. `STOP` 致命封号熔断锁

* **拦截原理**：子进程结束、输出收齐后，PeerAgent 对错误输出做致命鉴权错误特征扫描（包括 `account deactivated/suspended/banned`、`organization_disabled`、`unsupported_country` 等致命风控特征）。一旦命中，调度器立即在 `$PEER_HOME` 写入停机锁文件（如 `STOP-codex`、`STOP-claude` 或全局 `STOP`），并记录触发时间、原因和关联任务编号。
* **为什么防封号**：多 Agent 异步调用时，若一个任务因地区 IP 或鉴权异常失败，排队的后续任务如果继续并发重试，极易被平台判定为恶意撞库或攻击从而封锁整个账号。写入 STOP 锁后，后续所有任务在拉起前都会被强行拦截，彻底斩断重试连击链条。普通 401 提示重登或网络波动则绝不触发停机锁。
* **急停拉手与人工复位原则（红线）**：
  * **手动急停**：用户可在任何紧急时刻执行 `touch ~/.peer-review/STOP` 手动拉下总闸，阻断所有自动调用。
  * **严禁 Agent 自动复位**：当 STOP 熔断锁生效时，`peer` 会严格拒绝执行任务。**AI Agent 绝对禁止自动删除 STOP 文件**，必须由人类用户亲自排查原因、确认网络与账号安全后，手动在终端删除锁文件（如 `rm ~/.peer-review/STOP*`）方可恢复。
  * **诊断工具 `peer doctor`**：若处于熔断状态，`peer doctor` 会以红色警报高亮展示熔断锁路径与具体触发原因，并以退出码 3 退出，阻断自动化流程。

## 常见问题与网络排障

### 找不到 `peer` 或目标 CLI

重开终端使 PATH 生效，或使用前面的 `~/.local/bin/peer` 固定路径。目标模型仍提示找不到命令时，确认对应 CLI 已安装，且启动主持端的环境能找到它；必要时将配置的 `bins.claude` / `bins.codex` 改为实际可执行文件的绝对路径。PATH 或配置改完后，重启主持端再检查。

### 未登录，或提示登录类别不一致

先在原渠道的官方 CLI 中核实登录状态；未登录时按该 CLI 的流程登录，再运行 `peer doctor`。若你有意改变了登录方式，先确认订阅/API 与计费预期，再由本人决定是否执行 `peer doctor --approve`。它记录可识别的当前类别，不修复网络、额度或账号权限。

### 安装了，但 `/codex` 或 `/claude` 没出现

刷新或重开主持端，检查技能是否加载到了该客户端实际使用的配置目录。安装器复制到默认的 Claude、Codex 和 Antigravity 技能目录；使用自定义配置目录时，需要按客户端设置核对。斜杠菜单的显示方式以客户端版本为准，也可先用 `peer ask` 排查调度链路。

### 国内网络下，代理端口能连但请求仍失败

**最简单的办法**：重新运行安装命令并加上 `--proxy http://127.0.0.1:你的端口`，或者直接在 `~/.peer-review/config.json` 里写：

```json
{
  "child_env": {"HTTPS_PROXY": "http://127.0.0.1:7890", "HTTP_PROXY": "http://127.0.0.1:7890"}
}
```

peer 是直接运行 Claude / Codex 程序的，不经过你在 shell 里给 `claude`、`codex` 设置的函数或别名，所以写在那里的代理 peer 用不上；从桌面 App 里调用时，也拿不到终端里的代理环境变量。`child_env` 就是为这种情况准备的，`peer doctor` 会列出已生效的变量名。

下面的 `proxy_check` 只是检查端口用的：

`proxy_check` **只用 TCP 连接探测指定的主机和端口**，不自动设置代理，也不检查 HTTP/SOCKS 协议、认证、DNS、TLS 或官方模型服务是否可达。可以按本机实际端口配置：

```json
{
  "proxy_check": ["127.0.0.1", 7890]
}
```

这仅让 `peer doctor` 检查端口。代理地址、协议和环境变量要在运行官方 CLI 的环境中另行配置；子进程会继承环境，但目标 CLI 是否采用这些设置取决于它自身的实现。先在同一终端验证官方 CLI 的网络状态，再检查主持端是否继承相同环境。代理软件启用了，不代表从桌面打开的客户端也拿到了终端环境变量。

CLI 安装包下载与模型服务访问是两条链路。安装成功不代表模型服务可达；遇到代理超时，先检查端口、协议和目标服务。这里不提供未经验证的镜像或绕过服务限制的方案。

### 任务超时，或状态是 `unknown`

先用原运行编号执行 `peer status`，检查该任务目录中的状态、报告和错误文件；等待超时可继续 `peer wait`。`unknown` 表示进程已结束但结果没有回收，不代表请求未提交。结果不明时不要重发或切账号；先核查原任务和原账号，确认未受理并获得重试授权后再发新请求。PeerAgent 不自动重试。

### 模型或强度不受支持

默认模型留空并跟随客户端设置；配置中 Codex 强度默认固定为 `high`。指定模型、强度前先确认目标 CLI 支持。优先级为：本次参数 > 配置固定值 > 客户端设置 > CLI 默认值。PeerAgent 接受参数不代表目标服务一定支持。

## 配置参考

默认配置位于 `~/.peer-review/config.json`，也可用 `PEER_CONFIG` 指向其他文件。完整默认值如下，字段与 [`config.example.json`](./config.example.json) 一致：

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
  "codex_disable_apps": false,
  "claude_read_web": true,
  "child_env": {},
  "claude_exec_sandbox": true
}
```

| 配置项 | 说明 |
| :--- | :--- |
| `bins` | 目标 CLI 命令名或绝对路径 |
| `models` | 固定模型；空字符串表示尝试跟随客户端，不写死模型名称 |
| `efforts` | 固定推理强度；空字符串表示尝试跟随客户端，具体取值由目标 CLI 支持情况决定 |
| `service_tiers.codex` | 当前调度器只接受 `default` 或 `flex`；默认 `default` |
| `follow_app_settings` | 允许在对应配置留空时读取客户端设置 |
| `approved_auth` | 已批准的登录类别，默认均为 `subscription`；不一致时阻止调用 |
| `max_turns` | 当前用于 Claude CLI 的最大轮次参数，不是两端通用的循环保证 |
| `timeout_minutes` | 读/写任务最长运行时间（分钟），到期终止子进程；不证明远端未处理请求 |
| `proxy_check` | 可选 `[主机, 端口]` TCP 检测，不配置代理 |
| `codex_disable_apps` | 传参禁用 Codex Apps；默认 `false`，生图任务会单独禁用 |
| `claude_read_web` | 只读调用是否给 Claude 开放 WebSearch / WebFetch；默认 `true`。⚠️ 审阅外部或不可信代码、项目里有密钥时，被审内容里的提示注入可能诱导模型借联网工具外传读到的内容；不需要联网时建议设为 `false`，或按次加 `peer ask --no-web`。`peer doctor` 会显示当前状态 |
| `child_env` | 附加给 Claude / Codex 子进程的环境变量，如 `{"HTTPS_PROXY": "http://127.0.0.1:7890"}`。peer 直接调用 CLI 程序，不经过 shell 里的同名函数或别名，从桌面 App 发起时也未必继承终端代理；计费相关变量（`ANTHROPIC_*`、`OPENAI_API_KEY` 等）不接受。`peer doctor` 只显示变量名 |
| `claude_exec_sandbox` | 可写调用时 Claude 的 Bash 是否进沙箱；默认 `true`（只能写项目、`--add-dir` 目录和 `$TMPDIR`，不能联网，与 Codex 一致）。设为 `false` 恢复不加沙箱，`peer doctor` 会给出提醒 |

如果只想固定高强度、继续跟随模型设置，可合并下面的配置片段：

```json
{
  "efforts": {"claude": "high", "codex": "high"}
}
```

若主动改用官方 API 登录，先在对应 CLI 完成并确认，再核对 `peer doctor` 输出后决定是否批准新类别；不要仅为了消除报错而批准。

### 环境变量

| 环境变量 | 默认值与用途 |
| :--- | :--- |
| `PEER_HOME` | 默认 `~/.peer-review`，存放配置、模板和全局调用日志 |
| `PEER_CONFIG` | 默认 `$PEER_HOME/config.json`，指定配置文件 |
| `PEER_TEMPLATES_DIR` | 覆盖模板目录；默认优先程序所在仓库的 `templates/`，否则用 `$PEER_HOME/templates` |
| `PEER_DEPTH` | 默认 0，由调度器为子进程增加深度标记，用于拒绝嵌套调用 |
| `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` | 继承启动环境中的值；是否生效由目标 CLI 决定，PeerAgent 不自动设置 |

## 里面有什么与工作原理

| 组成 | 路径与说明 |
| :--- | :--- |
| 核心调度器 | [`bin/peer`](./bin/peer)，当前版本 2,541 行，仅用 Python 标准库，无常驻守护进程 |
| CLI 适配技能 | [`skills/`](./skills/)，适配 Claude Code、Codex 与 Antigravity，非这些厂商官方出品 |
| 任务模板 | [`templates/`](./templates/)，共 5 份：`review.md`、`plan.md`、`advice.md`、`exec.md`、`image.md` |
| 安装器 | [`install.sh`](./install.sh)，默认文件复制，可显式选择软链接 |
| 测试 | [`tests/`](./tests/)，核心行为的测试用例 |
| 架构说明 | [`docs/architecture.md`](./docs/architecture.md)，设计细节和图解 |

调用流程是：保存任务说明 → 检查登录类别、STOP 和调用深度 → 启动本机 CLI → 保存结果并返回报告。Claude Code、Codex 和 Antigravity 都能发起请求，实际执行端是本机 Claude / Codex CLI。

<details>
<summary>架构图与现有演示素材</summary>

![调用拓扑](./docs/diagrams/topology.svg)

![审阅时序](./docs/diagrams/review_sequence.svg)

![证据核查流程](./docs/diagrams/evidence_first_protocol.svg)

以下是现有演示封面，画面包含机器人出图及重绘界面，**不是代码审阅实录**。图中历史宣传文字不作为能力承诺；当前行为与边界以本页及源码为准。

<img src="./docs/assets/hero.jpg" alt="现有演示封面，含重绘界面和生图场景" width="100%" />

</details>

## 为什么写这个工具

写完代码后，我们经常想请另一个模型再看一遍，但复制代码、切窗口、搬回意见很麻烦。PeerAgent 把这一步接到现有会话里，使用本机已登录的 CLI，减少重复操作。

它来自作者日常的多 Agent 编程实践。真实调用（审阅、修改执行、沙箱拦截）在作者的 Mac（Apple Silicon）上实测过；CI 在 macOS 和 Linux 上运行单元测试和从零安装测试，但 CI 里没有账号，不做真实的模型调用。在其他机型或系统上遇到问题，欢迎提 issue。

如果只是想在现有 CLI 之间安全、省心地让另一个模型多做一次代码检查，PeerAgent 就是为你打造的。

## 社区与交流

欢迎通过以下渠道反馈问题、交流使用经验与探讨多 Agent 落地实战：

- 🐛 **问题反馈**：[GitHub Issues](https://github.com/puck-muling/peer-agent/issues)
- 𝕏 **X（Twitter）**：[@puck_muling](https://x.com/puck_muling)

### 💬 QQ 交流

添加作者 QQ：**2607430010**（Puck-Muling），探讨技术或反馈问题：

<p align="center">
  <img src="./docs/assets/qq_qr.jpg" width="220" alt="QQ 联系二维码" />
</p>

### ✈️ Telegram 交流

加入 Telegram 交流群探讨多 Agent 协作实战：[@puckmuling](https://t.me/puckmuling)：

<p align="center">
  <img src="./docs/assets/telegram_qr.png" width="220" alt="Telegram 二维码" />
</p>

---

感谢 Claude Code、Codex、Antigravity 团队与分享 Agent 审阅实践的开源贡献者。

## 许可证与安全

本项目采用 [MIT 许可证](./LICENSE)。安全说明与问题报告方式见 [SECURITY.md](./SECURITY.md)。
