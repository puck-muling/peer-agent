---
name: codex
description: 用户输入 /codex <任务> 时，通过 peer 调度 Codex 执行该任务并汇报结果。Codex 可读取并写入当前工作目录。
argument-hint: "<任务描述>"
disable-model-invocation: true
allowed-tools: Bash(*)
---

# /codex：调用 Codex

用户参数：`$ARGUMENTS`

## 执行步骤

1. 参数为空时，不调用 Codex，直接请用户补充任务描述。
2. 防递归死循环检查：检查环境变量 `PEER_DEPTH`，若已存在且大于等于 1（或为 true/yes），严禁调用 Codex，直接向用户报错：`【防死循环拦截】检测到嵌套调用（PEER_DEPTH=$PEER_DEPTH）：禁止在 Claude 任务进程中再次调用 Codex，防止递归死循环。`
3. 安全停机锁检查：检查 `$PEER_HOME/STOP` 与 `$PEER_HOME/STOP-codex`（默认 `$HOME/.peer-review/`），存在时立即阻断退出，提示人工排查。**严禁 Agent 自行删除任何 STOP 锁文件或尝试绕过**；STOP 锁只能由用户本人人工排查确认安全后手动删除。
4. 全局统一入口：所有 Codex 调用一律经由 `peer` 调度工具发起，严禁裸跑 `codex exec`，确保享有工作区隔离、全局排他锁、拟人化冷却与致命鉴权熔断保护。
5. 在当前工作目录运行：

   ```bash
   PEER_HOME="${PEER_HOME:-$HOME/.peer-review}"

   # 1. 安全停机熔断检查
   if [ -f "$PEER_HOME/STOP" ] || [ -f "$PEER_HOME/STOP-codex" ]; then
     echo "【peer 熔断保护生效中】检测到此前已触发安全停机锁，暂停所有自动调用！请人工排查确认安全后由用户本人删除停机锁（严禁 Agent 自动删除恢复）。" >&2
     exit 3
   fi

   # 2. 防死循环拦截
   case "${PEER_DEPTH:-0}" in
     0|false|no|off) ;;
     *)
       echo "【防死循环拦截】检测到嵌套调用（PEER_DEPTH=$PEER_DEPTH）：禁止在 Claude 任务进程中再次调用 Codex，防止递归死循环。" >&2
       exit 2
       ;;
   esac

   # 3. 动态定位 peer 可执行文件
   if command -v peer >/dev/null 2>&1; then
     PEER_BIN=$(command -v peer)
   elif [ -x "$PEER_HOME/bin/peer" ]; then
     PEER_BIN="$PEER_HOME/bin/peer"
   elif [ -x "$HOME/.local/bin/peer" ]; then
     PEER_BIN="$HOME/.local/bin/peer"
   else
     echo "【错误】peer 调度工具未找到或不可执行，请检查 PATH 或 ~/.peer-review/bin/peer！" >&2
     exit 4
   fi

   # 4. 安全落盘请求说明（$ARGUMENTS 由 Claude Code 在执行前做文本替换；这里用带引号的 heredoc 原样落盘，
   #    不经 shell 求值，反引号、$(...)、$变量 都不会被展开）
   REQ_DIR="$PWD/.peer-review/requests"
   mkdir -p "$REQ_DIR"
   REQ_FILE="$REQ_DIR/$(date +%Y%m%d-%H%M%S)-claude-codex.md"
   printf '# 任务\n' > "$REQ_FILE"
   cat >> "$REQ_FILE" <<'PEER_ARGUMENTS_EOF_7f3a9c'
$ARGUMENTS
PEER_ARGUMENTS_EOF_7f3a9c

   # 5. 安全提取意图与任务原文（通过 Python 安全读取文件，完全免疫 shell 命令注入）
   PARSED_JSON=$(python3 -c '
import sys, json, re

req_file = sys.argv[1]
with open(req_file, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
raw = " ".join(lines)
raw_l = raw.lower()
first_word = raw.split()[0].lower() if raw.split() else ""

# 优先级 1: 否定/严格只读词，允许否定词与修改词间隔对象和修饰语。
# 邻近检测不跨句读；采用保守只读路由，避免否定句被误升级为可写。
edit_words = ["修改", "实现", "编辑", "写入", "创建", "新建", "修复", "重构", "编写", "修掉", "改一下"]
has_edit_word = any(w in raw_l for w in edit_words)
is_negated_readonly = any(w in raw_l for w in [
    "只读", "仅审阅", "仅查看", "仅分析", "仅排查", "不要改", "不要修改",
    "无需修改", "不用修改", "不得修改", "严禁修改", "禁止修改", "请勿修改",
    "不修改", "只查", "只看", "评估", "是否需要", "是否应当"
]) or bool(re.search(
    r"(?:不要|不许|请勿|严禁|禁止|不得|无需|不用|不能|不可|不准|不|别|勿)"
    r"[^，。；！？,;.!?\n]{0,16}(?:修改|改动|编辑|写入|创建|新建|修复|重构|编写|改)", raw_l
)) or bool(re.search(
    r"\b(?:do\s+not|don\x27t|never|without)\b[^,;.!?\n]{0,40}"
    r"\b(?:modify|modifying|edit|editing|change|changing|write|writing|fix|fixing)\b", raw_l
))

# 优先级 2: 强只读动词，高于任何修改词（“审阅当前修改”、“检查修复结果”必须是 review，不得升级为 exec）
has_review_verb = any(w in raw_l for w in [
    "审阅", "排查", "检查", "查看", "看看", "核查", "核实", "复核", "审查", "审计"
]) or bool(re.search(r"\b(?:review|inspect|audit|diff|check)\b", raw_l))

if first_word in ("exec", "review", "plan", "advice", "image"):
    # 显式子命令除 exec 外直接匹配；若写了 exec 但紧接着有否定词，安全降级为 review
    kind = "review" if (first_word == "exec" and is_negated_readonly) else first_word
elif is_negated_readonly or has_review_verb:
    kind = "review"
elif any(w in raw_l for w in ["出方案", "出计划", "设计方案", "怎么做", "出个计划", "重构方案", "方案", "计划"]):
    kind = "plan"
elif any(w in raw_l for w in ["生图", "生成图片", "出图", "画一张", "做一张", "出海报", "做立绘"]):
    kind = "image"
elif has_edit_word:
    kind = "exec"
elif any(w in raw_l for w in ["为什么", "怎么看", "分析一下", "给个建议", "给个结论", "结论", "建议"]):
    kind = "advice"
else:
    kind = "review"

if kind == "review" and (first_word == "exec" or has_edit_word):
    print("【提示】已按只读处理；要修改请以 exec 开头，并去掉相冲突的只读或禁止修改要求。", file=sys.stderr)

print(json.dumps({"kind": kind, "quote": raw[:300]}, ensure_ascii=False))
' "$REQ_FILE")

   KIND=$(python3 -c "import json, sys; print(json.loads(sys.argv[1])['kind'])" "$PARSED_JSON")
   QUOTE=$(python3 -c "import json, sys; print(json.loads(sys.argv[1])['quote'])" "$PARSED_JSON")

   # 6. 后台发起调用（绝不导出 PEER_DEPTH=1，由 peer child_env 自动安全注入）
   if [ "$KIND" = "review" ] || [ "$KIND" = "plan" ] || [ "$KIND" = "advice" ]; then
     RUN_OUT=$("$PEER_BIN" ask codex "$KIND" --request "$REQ_FILE" --cwd "$PWD" --caller "Claude")
   else
     RUN_OUT=$("$PEER_BIN" ask codex "$KIND" --request "$REQ_FILE" --cwd "$PWD" --quote "$QUOTE" --caller "Claude")
   fi
   ASK_STATUS=$?
   echo "$RUN_OUT"
   if [ $ASK_STATUS -ne 0 ]; then
     exit $ASK_STATUS
   fi

   # 7. 等待并展示结果（自动续等至 540 秒；退出码 10 只重跑 wait，绝对禁止重新 ask）
   RUN_ID=$(echo "$RUN_OUT" | grep "运行编号：" | head -n 1 | sed 's/.*运行编号：//' | tr -d ' ')
   if [ -n "$RUN_ID" ]; then
     "$PEER_BIN" wait "$RUN_ID" --cwd "$PWD" --timeout 540
     WAIT_STATUS=$?
     if [ $WAIT_STATUS -eq 10 ]; then
       echo "【提示】任务仍在后台执行中（退出码 10）。请等待片刻后再次运行：$PEER_BIN wait $RUN_ID --cwd \"$PWD\"；绝对禁止重新发起 ask！" >&2
     fi
     exit $WAIT_STATUS
   fi
   ```

6. 汇报：
   - 结果由 `peer wait` 自动格式化输出（包含状态、模型、用量、耗时及改动 diff）。
   - 若遇到退出码 10（还在运行），只再次调用 `peer wait <run_id> --cwd "$PWD"` 查询，**绝对禁止重新执行 ask**。
   - 遇到退出码 3 或熔断提示时只向用户如实汇报，**严禁 Agent 自动删除恢复**。

## 约束

- 失败、超时或结果不明时不自动重试、不换账号或模型重发，先向用户报告。
- 不把密钥、Cookie、令牌等敏感信息写入任务描述或日志。
- 严禁 Agent 自行删除任何 STOP 停机锁。
