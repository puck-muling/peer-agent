#!/usr/bin/env bash
# PeerAgent 一键安装脚本
# 支持 macOS 与 Linux (Ubuntu/Debian/Fedora/Arch)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PEER_HOME="${PEER_HOME:-$HOME/.peer-review}"
LOCAL_BIN="$HOME/.local/bin"
# Codex 技能目录：旧版扫描 ~/.codex/skills，OpenAI 现行文档为 ~/.agents/skills，两处都装
CODEX_SKILL_DIRS=("$HOME/.codex/skills" "$HOME/.agents/skills")
MODE="copy"

print_banner() {
  cat << 'EOF'
  ____                  _                    _   
 |  _ \ ___  ___ _ __  / \   __ _  ___ _ __ | |_ 
 | |_) / _ \/ _ \ '__|/ _ \ / _` |/ _ \ '_ \| __|
 |  __/  __/  __/ |  / ___ \ (_| |  __/ | | | |_ 
 |_|   \___|\___|_| /_/   \_\__, |\___|_| |_|\__|
                            |___/                 
  Decentralized Multi-Agent Code Review Mesh
EOF
}

usage() {
  local code="${1:-0}"
  echo "用法: $0 [选项]"
  echo "选项:"
  echo "  --link       使用软链接安装（适合开发者，修改代码立即生效）"
  echo "  --copy       使用文件复制安装（默认方式）"
  echo "  --uninstall  卸载 PeerAgent 及相关技能配置（若有安装前备份将自动还原）"
  echo "  -h, --help   显示本帮助信息"
  exit "$code"
}

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --copy) MODE="copy"; shift ;;
    --uninstall) MODE="uninstall"; shift ;;
    -h|--help) usage 0 ;;
    *) echo "未知参数: $1" >&2; usage 2 ;;
  esac
done

print_claude_install_hint() {
  # 官方首推原生安装，brew / npm 作为备选；只提示，不代装
  local indent="${1:-   }"
  echo "${indent}- 安装 Claude（官方推荐）: curl -fsSL https://claude.ai/install.sh | bash"
  echo "${indent}  macOS 备选: brew install --cask claude-code；npm 备选（需已安装 Node.js）: npm install -g @anthropic-ai/claude-code"
  echo "${indent}  安装后登录: claude auth login"
}

canon_path() {
  # 规范化路径：解析父目录中的符号链接与 ..，但不跟随末级符号链接（rm 末级链接不会影响其指向）
  local dir base suffix=""
  dir="$(dirname "$1")"
  base="$(basename "$1")"
  while [ ! -d "$dir" ]; do
    suffix="/$(basename "$dir")$suffix"
    dir="$(dirname "$dir")"
  done
  dir="$(cd "$dir" 2>/dev/null && pwd -P || printf '%s' "$dir")"
  printf '%s%s/%s\n' "${dir%/}" "$suffix" "$base"
}

assert_not_same_path() {
  local src="$1"
  local dst="$2"
  if [ "$(canon_path "$src")" = "$(canon_path "$dst")" ]; then
    echo "❌ 错误: 安装源与目标是同一个文件，已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   源文件: $src" >&2
    echo "   目标:   $dst" >&2
    echo "👉 请把 PEER_HOME 设为仓库以外的目录（默认 ~/.peer-review），并确认仓库不在 $LOCAL_BIN 的上级位置后重试。" >&2
    exit 1
  fi
}

preflight_paths() {
  # 任何 rm / ln / cp 之前统一校验，避免 PEER_HOME 指向仓库本身时删掉或自链接源文件
  if [ "$(canon_path "$PEER_HOME/_")" = "$(canon_path "$SCRIPT_DIR/_")" ]; then
    echo "❌ 错误: PEER_HOME 与 PeerAgent 仓库是同一目录（$SCRIPT_DIR），已安全终止（未删除或覆盖任何文件）。" >&2
    echo "👉 请把 PEER_HOME 设为仓库以外的目录（默认 ~/.peer-review）后重试。" >&2
    exit 1
  fi
  assert_not_same_path "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer"
  assert_not_same_path "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer"
  local f
  for f in "$SCRIPT_DIR/templates"/*.md; do
    assert_not_same_path "$f" "$PEER_HOME/templates/$(basename "$f")"
  done
  assert_not_same_path "$SCRIPT_DIR/skills/antigravity/codex/SKILL.md" "$HOME/.gemini/config/skills/codex/SKILL.md"
  assert_not_same_path "$SCRIPT_DIR/skills/antigravity/claude/SKILL.md" "$HOME/.gemini/config/skills/claude/SKILL.md"
  assert_not_same_path "$SCRIPT_DIR/skills/claude/codex/SKILL.md" "$HOME/.claude/skills/codex/SKILL.md"
  for d in "${CODEX_SKILL_DIRS[@]}"; do
    assert_not_same_path "$SCRIPT_DIR/skills/codex/claude/SKILL.md" "$d/claude/SKILL.md"
  done
}

safe_uninstall_skill() {
  local src="$1"
  local dst="$2"
  local is_our_file=0

  if [ -L "$dst" ]; then
    # 若是指向本仓库或同名 peer 技能的符号链接
    local target
    target="$(readlink "$dst" || true)"
    if [[ "$target" == *"$SCRIPT_DIR"* ]] || [[ "$target" == *"peer"* ]]; then
      is_our_file=1
    fi
  elif [ -f "$dst" ]; then
    # 若内容与仓库一致，或包含 peer 特征标记
    if cmp -s "$src" "$dst" 2>/dev/null || grep -q "PEER_HOME" "$dst" 2>/dev/null; then
      is_our_file=1
    fi
  fi

  if [ "$is_our_file" = "1" ]; then
    rm -f "$dst"
    local parent
    parent="$(dirname "$dst")"
    local base
    base="$(basename "$dst")"
    local latest_bak
    latest_bak="$(ls -t "${parent}/${base}".bak_* 2>/dev/null | head -n 1 || true)"
    if [ -n "$latest_bak" ] && { [ -f "$latest_bak" ] || [ -L "$latest_bak" ]; }; then
      echo "   还原备份技能: $(basename "$latest_bak") -> $base"
      mv "$latest_bak" "$dst"
    fi
    rmdir "$(dirname "$dst")" 2>/dev/null || true
  elif [ -e "$dst" ]; then
    echo "   跳过非 PeerAgent 自建技能文件: $dst"
  fi
}

uninstall_peer() {
  echo "正在卸载 PeerAgent..."
  if [ -L "$LOCAL_BIN/peer" ] || [ -f "$LOCAL_BIN/peer" ]; then
    rm -f "$LOCAL_BIN/peer"
  fi
  if [ -L "$PEER_HOME/bin/peer" ] || [ -f "$PEER_HOME/bin/peer" ]; then
    rm -f "$PEER_HOME/bin/peer"
  fi
  safe_uninstall_skill "$SCRIPT_DIR/skills/antigravity/codex/SKILL.md" "$HOME/.gemini/config/skills/codex/SKILL.md"
  safe_uninstall_skill "$SCRIPT_DIR/skills/antigravity/claude/SKILL.md" "$HOME/.gemini/config/skills/claude/SKILL.md"
  safe_uninstall_skill "$SCRIPT_DIR/skills/claude/codex/SKILL.md" "$HOME/.claude/skills/codex/SKILL.md"
  for d in "${CODEX_SKILL_DIRS[@]}"; do
    safe_uninstall_skill "$SCRIPT_DIR/skills/codex/claude/SKILL.md" "$d/claude/SKILL.md"
  done
  echo "✅ 已移除技能链接与执行程序。保留 ~/.peer-review 历史数据。"
  exit 0
}

safe_install_skill() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  local bak="${dst}.bak_$(date +%Y%m%d%H%M%S)"
  if [ -e "$bak" ] || [ -L "$bak" ]; then
    bak="${bak}_$$"
  fi
  if [ -L "$dst" ]; then
    local target
    target="$(readlink "$dst" || true)"
    if [ "$target" = "$src" ]; then
      # 上次 --link 安装留下的本仓库链接，直接替换
      rm -f "$dst"
    else
      # 外来软链接：连同原指向一起备份（mv 不解引用，只移动链接本身），卸载时可还原
      mv "$dst" "$bak"
      echo "      检测到已有技能软链接（原指向: $target），已备份至: $bak"
    fi
  elif [ -e "$dst" ]; then
    if ! cmp -s "$src" "$dst" 2>/dev/null; then
      mv "$dst" "$bak"
      echo "      检测到已有技能文件，已备份至: $bak"
    fi
  fi
  if [ "$MODE" = "link" ]; then
    ln -sf "$src" "$dst"
  else
    cp -f "$src" "$dst"
  fi
}

preflight_paths

if [ "$MODE" = "uninstall" ]; then
  uninstall_peer
fi

print_banner

echo "==> 1. 检查基础依赖环境..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 错误: 未检测到 python3，PeerAgent 核心调度器依赖 Python 3.9+。" >&2
  exit 1
fi

PY_VER=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
PY_CHECK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 9) else 0)")
if [ "$PY_CHECK" != "1" ]; then
  echo "❌ 错误: PeerAgent 要求 Python 3.9 及以上版本（当前检测到: ${PY_VER}）。" >&2
  if [ "$(uname -s)" = "Linux" ]; then
    echo "👉 Linux 升级建议：通过系统包管理器 apt / dnf / pacman 安装 Python 3.9+。" >&2
    echo "   若系统仓库版本过旧，可用 pyenv 或 uv 安装 Python 3.9+，并确保 python3 指向新版本。" >&2
  else
    echo "👉 macOS 升级建议（二选一）：" >&2
    echo "   1. 运行 Homebrew 安装: brew install python" >&2
    echo "   2. 访问官网下载安装包: https://www.python.org/downloads/macos/" >&2
  fi
  exit 1
fi
echo "   Python 版本: ${PY_VER} (符合 >= 3.9 要求)"

HAS_CLAUDE=0
HAS_CODEX=0

if command -v claude >/dev/null 2>&1; then
  HAS_CLAUDE=1
  echo "   Claude: 已安装 ($(claude --version 2>/dev/null || echo 'OK'))"
else
  echo "   ⚠️ 提示: 未检测到 'claude' CLI。若需调用 Claude，请先安装官方 Claude："
  print_claude_install_hint "     "
fi

if command -v codex >/dev/null 2>&1; then
  HAS_CODEX=1
  echo "   Codex: 已安装 ($(codex --version 2>/dev/null || echo 'OK'))"
else
  echo "   ⚠️ 提示: 未检测到 'codex' CLI。若需调用 Codex，请先安装官方 Codex: npm install -g @openai/codex"
fi

if [ "$HAS_CLAUDE" = "0" ] && [ "$HAS_CODEX" = "0" ]; then
  echo ""
  echo "💡 提示: 未检测到任何已安装的官方 CLI（Claude 或 Codex）。"
  echo "   PeerAgent 需驱动本机官方 CLI 进行对等审阅，建议至少安装并登录一个："
  echo "   - 安装 Codex:  npm install -g @openai/codex && codex login"
  print_claude_install_hint "   "
fi

echo "==> 2. 初始化目标目录与核心组件..."
mkdir -p "$PEER_HOME/bin" "$PEER_HOME/templates" "$PEER_HOME/logs" "$LOCAL_BIN"

if [ "$MODE" = "link" ]; then
  ln -sf "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer"
  ln -sf "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer"
  for f in "$SCRIPT_DIR/templates"/*.md; do
    ln -sf "$f" "$PEER_HOME/templates/$(basename "$f")"
  done
  echo "   已以符号链接模式安装核心工具。"
else
  rm -f "$PEER_HOME/bin/peer"
  cp -f "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer"
  chmod +x "$PEER_HOME/bin/peer"
  rm -f "$LOCAL_BIN/peer"
  cp -f "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer"
  chmod +x "$LOCAL_BIN/peer"
  for f in "$SCRIPT_DIR/templates"/*.md; do
    rm -f "$PEER_HOME/templates/$(basename "$f")"
    cp -f "$f" "$PEER_HOME/templates/"
  done
  echo "   已复制核心二进制与审阅模板。"
fi

if [ ! -f "$PEER_HOME/config.json" ]; then
  cp "$SCRIPT_DIR/config.example.json" "$PEER_HOME/config.json"
  echo "   已生成默认配置文件: $PEER_HOME/config.json"
fi

echo "==> 3. 安装三端 Agent 技能..."

# A. Antigravity Skills
safe_install_skill "$SCRIPT_DIR/skills/antigravity/codex/SKILL.md" "$HOME/.gemini/config/skills/codex/SKILL.md"
safe_install_skill "$SCRIPT_DIR/skills/antigravity/claude/SKILL.md" "$HOME/.gemini/config/skills/claude/SKILL.md"
echo "   [Antigravity] 已安装 /codex 和 /claude 技能。"

# B. Claude Skill
safe_install_skill "$SCRIPT_DIR/skills/claude/codex/SKILL.md" "$HOME/.claude/skills/codex/SKILL.md"
echo "   [Claude] 已安装 /codex 技能。"

# C. Codex Skill（旧版目录与官方现行目录各装一份）
for d in "${CODEX_SKILL_DIRS[@]}"; do
  safe_install_skill "$SCRIPT_DIR/skills/codex/claude/SKILL.md" "$d/claude/SKILL.md"
done
echo "   [Codex]   已安装 /claude 技能（~/.codex/skills 与 ~/.agents/skills）。"

configure_path_if_needed() {
  # Linux 登录 shell 读取 .profile；不受 .bashrc 非交互提前 return 的影响。
  # 即使当前 PATH 已包含目标目录，也确保后续登录可以加载配置。
  if [ "$(uname -s)" = "Linux" ]; then
    if ! grep -Fq '.local/bin' "$HOME/.profile" 2>/dev/null; then
      printf '\n# PeerAgent CLI PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.profile"
      echo "   ✅ 已将 PATH 配置写入 ~/.profile，后续登录时生效。"
    fi
    echo "提示: 非登录、非交互 shell 未必读取 ~/.profile；此时可使用 $LOCAL_BIN/peer。"
  fi

  if [[ ":$PATH:" == *":$LOCAL_BIN:"* ]]; then
    echo "提示: $LOCAL_BIN 已在系统 PATH 中，可直接全局运行 peer。"
    return
  fi

  local rc_file=""
  if [ -f "$HOME/.zshrc" ] || [[ "${SHELL:-}" == *"zsh"* ]]; then
    rc_file="$HOME/.zshrc"
  elif [ -f "$HOME/.bashrc" ] || [[ "${SHELL:-}" == *"bash"* ]]; then
    rc_file="$HOME/.bashrc"
  fi

  if [ -n "$rc_file" ]; then
    if ! grep -Fq '.local/bin' "$rc_file" 2>/dev/null; then
      echo "" >> "$rc_file"
      echo "# PeerAgent CLI PATH" >> "$rc_file"
      echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$rc_file"
      echo "   ✅ 已自动将 $LOCAL_BIN 配置到 $(basename "$rc_file")。"
      echo "👉 请运行以下命令使 PATH 在当前终端立即生效（新开终端将自动生效）："
      echo "   source $rc_file"
      return
    fi
  fi

  echo "⚠️  注意: $LOCAL_BIN 尚未加入系统的 PATH 环境变量。"
  echo "👉 建议在 ~/.zshrc 或 ~/.bashrc 追加以下内容并重新打开终端："
  echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
}

print_usage_hint() {
  # 只列出当前已安装 CLI 能实际跑通的命令，缺失一侧给出安装指引
  echo ""
  if [ "$HAS_CLAUDE" = "1" ] && [ "$HAS_CODEX" = "1" ]; then
    echo "使用方式："
    echo "  1. 在 Antigravity 对话框中直接输入: /codex 审一下当前代码"
    echo "  2. 在 Claude 终端中输入:       /codex 检查这个函数的逻辑边界"
    echo "  3. 在 Codex 中输入:             /claude 审阅当前改动"
  elif [ "$HAS_CLAUDE" = "1" ]; then
    echo "当前仅检测到 Claude CLI，已具备调用 Claude 的技能："
    echo "  - 在 Antigravity 对话框中输入: /claude 审一下当前代码"
    echo "  - 或在终端直接调用: peer ask claude review --request ./review-task.md --cwd ."
    echo ""
    echo "⚠️ 若要在 Claude 终端中使用 /codex 对等互审，需先安装并登录 Codex："
    echo "   npm install -g @openai/codex && codex login"
    echo "   安装后运行 peer doctor 确认双端就绪即可，无需重新安装 PeerAgent。"
  elif [ "$HAS_CODEX" = "1" ]; then
    echo "当前仅检测到 Codex CLI，已具备调用 Codex 的技能："
    echo "  - 在 Antigravity 对话框中输入: /codex 审一下当前代码"
    echo "  - 或在终端直接调用: peer ask codex review --request ./review-task.md --cwd ."
    echo ""
    echo "⚠️ 若要在 Codex 中使用 /claude 对等互审，需先安装并登录 Claude："
    print_claude_install_hint "   "
    echo "   安装后运行 peer doctor 确认双端就绪即可，无需重新安装 PeerAgent。"
  else
    echo "⚠️ 未检测到任何官方 CLI，/codex 与 /claude 暂不可用。请至少安装并登录一个："
    echo "   - 安装 Codex:  npm install -g @openai/codex && codex login"
    print_claude_install_hint "   "
    echo "   安装后运行 peer doctor 复查。"
  fi
  echo ""
}

echo "==> 4. 运行自检验证..."
# 显式保存 doctor 的真实退出码，不能让后续提示命令覆盖为 0
DOCTOR_RC=0
"$LOCAL_BIN/peer" doctor || DOCTOR_RC=$?
if [ "$DOCTOR_RC" = "0" ]; then
  echo ""
  if [ "$HAS_CLAUDE" = "1" ] && [ "$HAS_CODEX" = "1" ]; then
    echo "🎉 恭喜！PeerAgent 安装完成并自检通过！"
  else
    echo "✅ PeerAgent 已安装，自检通过（仅单侧 CLI 可用，对等互审需补装另一侧）。"
  fi
  print_usage_hint
  configure_path_if_needed
else
  echo ""
  if [ "$DOCTOR_RC" = "3" ]; then
    echo "⛔ 自检发现熔断停机锁仍在生效（peer doctor 退出码 3）。请先人工核实上方列出的锁文件原因，确认安全后再手动处理。"
  else
    echo "⚠️ 自检未通过（peer doctor 退出码 ${DOCTOR_RC}），请根据上述提示核查后运行 peer doctor 复查。"
  fi
  print_usage_hint
  configure_path_if_needed
  exit "$DOCTOR_RC"
fi
