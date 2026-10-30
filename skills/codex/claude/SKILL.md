---
name: claude
description: 在 Codex 聊天中通过 /claude、$claude 或明确调用 Claude 的请求，使用本机 Claude Code 读取、创建、编辑任务指定的文件，并返回真实执行结果。提到 Claude 但未要求调用时不执行。
---

# 调用本机 Claude Code

用户在当前 Codex 聊天选择 `/claude` 或 `$claude`，附上任务，由 Codex 调用本机 Claude Code，结果返回当前聊天。不要让用户另开终端，也不要以 Codex 自己的意见或改动冒充 Claude 的执行。

## 解析任务与范围

- 以命令后的文字、附件及当前任务确定工作目录、目标文件、动作与验收标准；可以从当前上下文明确推定的内容不重复询问。只有缺少具体任务或文件目标时才补问。
- 将用户请求与必要规则组成一份任务提示传给 Claude；不转发整段聊天历史、凭证或无关私人文件。
- 强度：默认高（`--effort high`）。用户写了“超高”或“超高强度”作为强度要求时，本次用 `--effort xhigh`。
- 默认以当前项目或 worktree 为工作目录；用户指定其他目录时使用该目录。额外 `--add-dir` 仅限用户明确授权的目录。

## 运行环境与权限

- **提升权限（Escalated）**：Codex 默认沙箱无网络、不能写工作区外，而 Claude 需要访问 API、写会话记录并读取登录凭证。因此调用 Claude 的命令必须申请提升权限运行（`sandbox_permissions: "require_escalated"`），justification 写“调用本机 Claude Code，需要网络权限”。
- **统一入口优先**：优先使用 `peer` 统一调度器（`peer ask claude`），确保享有工作区快照（Snapshot）、改动对比（Diff）、防死循环深度标记（`PEER_DEPTH`）与安全熔断停机锁（`STOP`）保护。
- **环境隔离**：脚本启动前移除所有第三方 API 环境变量污染（如 `ANTHROPIC_BASE_URL` 等），确保走本机官方登录通道。

## 调用方式

以提升权限通过终端工具运行下述 Python 结构：

```python
import json, os, re, shutil, subprocess, sys
from pathlib import Path

workdir = Path(os.getcwd()).resolve()
task_prompt = "用户原始任务及目标路径"
effort = "high"  # 默认高；用户写“超高”时改为 "xhigh"
timeout_seconds = 1800

peer_bin = shutil.which("peer")
if not peer_bin:
    peer_home = os.environ.get("PEER_HOME") or os.path.expanduser("~/.peer-review")
    candidate = os.path.join(peer_home, "bin", "peer")
    if os.path.exists(candidate) and os.access(candidate, os.X_OK):
        peer_bin = candidate

# 1. 优先通过 peer 调度（享有快照、diff 与统一熔断保护）
if peer_bin:
    # 意图识别分发
    has_readonly = any(w in task_prompt for w in [
        "只读", "仅查看", "仅分析", "仅排查", "仅审阅", "只审阅",
        "无需修改", "不要修改", "不得修改", "严禁修改", "禁止修改", "请勿修改"
    ])
    clean_prompt = re.sub(r"(不得|严禁|不要|禁止|不可|避免|不需要|请勿|勿|别)[\u4e00-\u9fa5]{0,10}(修改|编辑|写入|改动|变更|创建|新建|重构|编写|删除)", "", task_prompt)
    has_write = any(w in clean_prompt for w in ["修改", "实现", "编辑", "写入", "创建", "新建", "修复", "重构", "编写", "删除"])
    is_write = has_write and not has_readonly

    kind = "exec" if is_write else "review"
    if not is_write:
        if any(w in task_prompt for w in ["方案", "计划", "怎么做"]):
            kind = "plan"
        elif any(w in task_prompt for w in ["建议", "结论", "为什么"]):
            kind = "advice"

    # 落盘请求文件
    req_dir = workdir / ".peer-review" / "requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    req_file = req_dir / f"{ts}-codex-claude.md"
    req_file.write_text(f"# 任务\n{task_prompt}\n", encoding="utf-8")

    ask_cmd = [peer_bin, "ask", "claude", kind, "--request", str(req_file), "--cwd", str(workdir), "--caller", "Codex"]
    if is_write:
        ask_cmd += ["--quote", task_prompt]
    if effort:
        ask_cmd += ["--effort", effort]

    proc = subprocess.run(ask_cmd, capture_output=True, text=True)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)

    # 提取运行编号并等待
    match = re.search(r"运行编号：([0-9a-zA-Z_-]+)", proc.stdout)
    if match:
        run_id = match.group(1).strip()
        wait_cmd = [peer_bin, "wait", run_id, "--cwd", str(workdir), "--timeout", str(timeout_seconds)]
        wait_proc = subprocess.run(wait_cmd)
        sys.exit(wait_proc.returncode)

# 2. 备选：直接调用本机 claude CLI
claude = shutil.which("claude")
if not claude:
    raise SystemExit("本机未找到 peer 或 claude CLI 工具；未执行请求")

env = {k: v for k, v in os.environ.items() if not k.startswith(("ANTHROPIC_", "CLAUDE_CODE_USE_"))}
env["PEER_DEPTH"] = "1"

argv = [
    claude, "-p", "--output-format", "json",
    "--restricted", "--tools", "Read,Glob,Grep,Edit,Write",
    "--permission-mode", "acceptEdits", "--permission-prompts", "none",
    "--settings", '{"disableAllHooks":true}', "--effort", effort,
]
p = subprocess.Popen(argv, cwd=workdir, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, err = p.communicate(task_prompt, timeout=timeout_seconds)
if p.returncode == 0:
    res = json.loads(out)
    print(res.get("result", out))
else:
    print(err, file=sys.stderr)
```

## 等待与汇报

- 汇报由 `peer wait` 自动格式化输出（包含状态、模型、用量、耗时及改动 diff）。
- 执行完成后由 Codex 核对改动与生成结果，并向用户呈现。
