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
# 写入本工具安装的每个文件，卸载时据此精确识别归属，避免误删用户同名文件
PEER_MARKER="managed-by: peer-agent"

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
  # 不存在的目录后接 . 或 .. 无法按字面拼回（如 repo/nope/.. 会被拼成 repo/nope/.. 而非 repo），直接返回非零
  local dir base seg suffix=""
  dir="$(dirname "$1")"
  base="$(basename "$1")"
  case "$base" in .|..) return 1 ;; esac
  while [ ! -d "$dir" ]; do
    seg="$(basename "$dir")"
    case "$seg" in .|..) return 1 ;; esac
    suffix="/$seg$suffix"
    dir="$(dirname "$dir")"
  done
  dir="$(cd "$dir" 2>/dev/null && pwd -P || printf '%s' "$dir")"
  printf '%s%s/%s\n' "${dir%/}" "$suffix" "$base"
}

canon_or_die() {
  if ! canon_path "$1"; then
    echo "❌ 错误: 无法规范化路径（不存在的目录后接 . 或 .. 路径段），已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   路径: $1" >&2
    exit 1
  fi
}

assert_not_same_path() {
  local src="$1"
  local dst="$2"
  local src_c dst_c
  src_c="$(canon_or_die "$src")" || exit 1
  dst_c="$(canon_or_die "$dst")" || exit 1
  if [ "$src_c" = "$dst_c" ]; then
    echo "❌ 错误: 安装源与目标是同一个文件，已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   源文件: $src" >&2
    echo "   目标:   $dst" >&2
    echo "👉 请把 PEER_HOME 设为仓库以外的目录（默认 ~/.peer-review），并确认仓库不在 $LOCAL_BIN 的上级位置后重试。" >&2
    exit 1
  fi
}

preflight_paths() {
  # 任何 rm / ln / cp 之前统一校验，避免 PEER_HOME 指向仓库本身时删掉或自链接源文件
  case "/$PEER_HOME/" in
    */../*|*/./*)
      echo "❌ 错误: PEER_HOME 含有 . 或 .. 路径段（$PEER_HOME），已安全终止（未删除或覆盖任何文件）。" >&2
      echo "👉 请把 PEER_HOME 设为不含 . / .. 的绝对路径（默认 ~/.peer-review）后重试。" >&2
      exit 1
      ;;
  esac
  local home_c repo_c
  home_c="$(canon_or_die "$PEER_HOME/_")" || exit 1
  repo_c="$(canon_or_die "$SCRIPT_DIR/_")" || exit 1
  if [ "$home_c" = "$repo_c" ]; then
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

path_within() {
  # $1 是否等于目录 $2 或位于其下（逐段字面比较，不做模糊子串匹配）
  case "$1" in
    "$2"|"$2"/*) return 0 ;;
  esac
  return 1
}

is_peer_owned() {
  # 判断 $2 是否由本工具安装（$1 为对应安装源）：
  #   软链接：规范化后的指向与安装源一致，或位于本仓库 / PEER_HOME 之内（先规范化，防止 repo/../x 绕过前缀判断）
  #   普通文件：内容与安装源一致，或带有 PEER_MARKER 标记
  local src="$1"
  local dst="$2"
  if [ -L "$dst" ]; then
    local target src_c root_c
    target="$(readlink "$dst" || true)"
    [ -n "$target" ] || return 1
    case "$target" in
      /*) ;;
      *) target="$(dirname "$dst")/$target" ;;
    esac
    target="$(canon_path "$target")" || return 1
    src_c="$(canon_path "$src")" || return 1
    [ "$target" = "$src_c" ] && return 0
    local root
    for root in "$SCRIPT_DIR" "$PEER_HOME"; do
      root_c="$(canon_path "$root/_")" || continue
      path_within "$target" "$(dirname "$root_c")" && return 0
    done
    return 1
  elif [ -f "$dst" ]; then
    cmp -s "$src" "$dst" 2>/dev/null && return 0
    grep -qF "$PEER_MARKER" "$dst" 2>/dev/null && return 0
  fi
  return 1
}

backup_path() {
  local bak="${1}.bak_$(date +%Y%m%d%H%M%S)"
  if [ -e "$bak" ] || [ -L "$bak" ]; then
    bak="${bak}_$$"
  fi
  printf '%s\n' "$bak"
}

restore_original_backup() {
  # 只还原安装前的原始用户文件：跳过旧版 PeerAgent 自身的备份（带标记、内容一致或指向本仓库），取时间戳最新的一份
  local src="$1"
  local dst="$2"
  local b pick=""
  for b in "$dst".bak_*; do
    { [ -e "$b" ] || [ -L "$b" ]; } || continue
    if is_peer_owned "$src" "$b"; then
      continue
    fi
    pick="$b"
  done
  if [ -n "$pick" ]; then
    echo "   还原安装前的原有文件: $(basename "$pick") -> $(basename "$dst")"
    mv "$pick" "$dst"
  fi
}

safe_uninstall_file() {
  # $3=1 时删除后顺带移除已空的父目录（技能目录）；执行程序所在的 bin 目录不动
  local src="$1"
  local dst="$2"
  local prune="${3:-1}"
  local label="${4:-技能}"

  if is_peer_owned "$src" "$dst"; then
    rm -f "$dst"
    restore_original_backup "$src" "$dst"
    if [ "$prune" = "1" ]; then
      rmdir "$(dirname "$dst")" 2>/dev/null || true
    fi
  elif [ -e "$dst" ] || [ -L "$dst" ]; then
    echo "   ⚠️ 跳过非 PeerAgent 安装的${label}文件（未删除）: $dst"
  fi
}

safe_uninstall_skill() {
  safe_uninstall_file "$1" "$2" 1 "技能"
}

uninstall_peer() {
  echo "正在卸载 PeerAgent..."
  safe_uninstall_file "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer" 0 "执行程序"
  safe_uninstall_file "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer" 0 "执行程序"
  safe_uninstall_skill "$SCRIPT_DIR/skills/antigravity/codex/SKILL.md" "$HOME/.gemini/config/skills/codex/SKILL.md"
  safe_uninstall_skill "$SCRIPT_DIR/skills/antigravity/claude/SKILL.md" "$HOME/.gemini/config/skills/claude/SKILL.md"
  safe_uninstall_skill "$SCRIPT_DIR/skills/claude/codex/SKILL.md" "$HOME/.claude/skills/codex/SKILL.md"
  for d in "${CODEX_SKILL_DIRS[@]}"; do
    safe_uninstall_skill "$SCRIPT_DIR/skills/codex/claude/SKILL.md" "$d/claude/SKILL.md"
  done
  echo "✅ 已移除技能链接与执行程序。保留 ~/.peer-review 历史数据。"
  exit 0
}

check_install_dir() {
  # 目标目录（或其最近的已存在上级）必须是可写目录；不能是常规文件或失效链接
  local probe="$1"
  while [ ! -e "$probe" ] && [ ! -L "$probe" ]; do
    probe="$(dirname "$probe")"
  done
  if [ ! -d "$probe" ]; then
    echo "❌ 错误: 安装目标路径被非目录占用，已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   目标目录: $1" >&2
    echo "   冲突路径: $probe（不是目录）" >&2
    echo "👉 请人工确认该路径用途，移走或改名后重试。" >&2
    exit 1
  fi
  if [ ! -w "$probe" ]; then
    echo "❌ 错误: 安装目标目录不可写，已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   目标目录: $1" >&2
    echo "   无写权限: $probe" >&2
    echo "👉 请检查该目录的属主与权限后重试（不要用 sudo 运行本脚本）。" >&2
    exit 1
  fi
}

check_install_target() {
  # 最终目标文件不能被真实目录占用，否则 mv / ln 会把文件放进该目录而非替换它
  if [ -d "$1" ] && [ ! -L "$1" ]; then
    echo "❌ 错误: 安装目标文件被目录占用，已安全终止（未删除或覆盖任何文件）。" >&2
    echo "   冲突路径: $1（是目录）" >&2
    echo "👉 请人工确认该路径用途，移走或改名后重试。" >&2
    exit 1
  fi
}

preflight_install_dirs() {
  # 任何写入之前一次性检查全部目标目录与目标文件，避免装到一半才失败、留下半套技能
  # check_install_dir 会逐级回溯到最近的已存在上级，父目录随之一并校验
  local d f
  for d in "$PEER_HOME" "$PEER_HOME/bin" "$PEER_HOME/templates" "$PEER_HOME/logs" "$LOCAL_BIN" \
           "$HOME/.gemini/config/skills/codex" "$HOME/.gemini/config/skills/claude" \
           "$HOME/.claude/skills/codex"; do
    check_install_dir "$d"
  done
  for d in "${CODEX_SKILL_DIRS[@]}"; do
    check_install_dir "$d/claude"
    check_install_target "$d/claude/SKILL.md"
  done
  for f in "$PEER_HOME/bin/peer" "$LOCAL_BIN/peer" \
           "$HOME/.gemini/config/skills/codex/SKILL.md" "$HOME/.gemini/config/skills/claude/SKILL.md" \
           "$HOME/.claude/skills/codex/SKILL.md"; do
    check_install_target "$f"
  done
  for f in "$SCRIPT_DIR/templates"/*.md; do
    check_install_target "$PEER_HOME/templates/$(basename "$f")"
  done
}

install_file() {
  # 统一安装执行程序与技能：
  #   已归属本工具（is_peer_owned：指向本仓库的软链、内容一致或带 PEER_MARKER 的旧版本）直接替换，不产生备份；
  #   外来文件（第三方同名工具或用户自己的技能）先 mv 备份为 .bak_<时间戳>，绝不直接覆盖，卸载时还原。
  #   复制模式先写同目录临时文件，再 mv -f 原子替换。
  local src="$1"
  local dst="$2"
  local label="$3"
  local exe="${4:-0}"
  mkdir -p "$(dirname "$dst")"
  local bak=""
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    if is_peer_owned "$src" "$dst"; then
      if [ -L "$dst" ]; then
        # 本仓库的旧软链接先移除：复制模式下绝不能透过链接写回仓库源文件
        rm -f "$dst"
      fi
    else
      bak="$(backup_path "$dst")"
      mv "$dst" "$bak"
      if [ -L "$bak" ]; then
        # mv 不解引用，只移动链接本身，原指向随备份一起保留
        echo "      检测到已有${label}软链接（原指向: $(readlink "$bak" || true)），已备份至: $bak"
      else
        echo "      检测到已有${label}文件，已备份至: $bak"
      fi
    fi
  fi
  local ok=1
  local tmp="${dst}.tmp.$$"
  if [ "$MODE" = "link" ]; then
    ln -sf "$src" "$dst" || ok=0
  else
    rm -f "$tmp"
    if cp "$src" "$tmp" && { [ "$exe" = "0" ] || chmod +x "$tmp"; } && mv -f "$tmp" "$dst"; then
      :
    else
      ok=0
    fi
  fi
  if [ "$ok" = "0" ]; then
    rm -f "$tmp" 2>/dev/null || true
    echo "❌ 错误: ${label}写入失败，已安全终止。" >&2
    echo "   源文件: $src" >&2
    echo "   目标:   $dst" >&2
    if [ -n "$bak" ]; then
      if [ ! -e "$dst" ] && [ ! -L "$dst" ] && mv "$bak" "$dst"; then
        echo "   已还原原有${label}文件: $dst" >&2
      else
        echo "   ⚠️ 原有${label}文件还原失败，备份仍保留在: $bak" >&2
      fi
    fi
    echo "👉 请检查目标目录的权限与剩余空间后重试。" >&2
    exit 1
  fi
}

safe_install_skill() {
  install_file "$1" "$2" "技能"
}

install_template() {
  # 模板目录 $PEER_HOME/templates 归本工具所有，直接替换；复制模式同样走临时文件 + mv -f
  local src="$1"
  local dst="$2"
  if [ "$MODE" = "link" ]; then
    ln -sf "$src" "$dst"
  else
    if [ -L "$dst" ]; then
      rm -f "$dst"
    fi
    cp "$src" "${dst}.tmp.$$"
    mv -f "${dst}.tmp.$$" "$dst"
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
preflight_install_dirs
mkdir -p "$PEER_HOME/bin" "$PEER_HOME/templates" "$PEER_HOME/logs" "$LOCAL_BIN"

# 两种模式统一先判断归属：外来的同名 peer 先备份再安装，绝不直接覆盖
install_file "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer" "执行程序" 1
install_file "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer" "执行程序" 1
for f in "$SCRIPT_DIR/templates"/*.md; do
  install_template "$f" "$PEER_HOME/templates/$(basename "$f")"
done
if [ "$MODE" = "link" ]; then
  echo "   已以符号链接模式安装核心工具。"
else
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
