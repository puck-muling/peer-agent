#!/usr/bin/env bash
# PeerAgent 一键安装脚本
# 支持 macOS 与 Linux (Ubuntu/Debian/Fedora/Arch)

set -euo pipefail

# 安装过程中会临时把 ~/.local/bin 加进 PATH（刚装的工具立即可用）；判断要不要写 shell 配置时必须看原始 PATH
ORIGINAL_PATH="$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PEER_HOME="${PEER_HOME:-$HOME/.peer-review}"
LOCAL_BIN="$HOME/.local/bin"
# Codex 技能目录：旧版扫描 ~/.codex/skills，OpenAI 现行文档为 ~/.agents/skills，两处都装
CODEX_SKILL_DIRS=("$HOME/.codex/skills" "$HOME/.agents/skills")
MODE="copy"
# 缺少的环境怎么处理：ask = 列出要做的事，按回车就自动完成；yes = 不问直接做；no = 只检查不安装
INSTALL_DEPS="ask"
PROXY_ARG=""
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
  echo "  --install-deps     缺少的环境（Python、Claude Code、Codex）不再询问，直接自动安装"
  echo "  --no-install-deps  只检查环境，缺什么只提示、不安装"
  echo "  --proxy 地址       设置代理（如 http://127.0.0.1:7890），安装时使用并保存给 peer"
  echo "  -h, --help   显示本帮助信息"
  exit "$code"
}

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --copy) MODE="copy"; shift ;;
    --uninstall) MODE="uninstall"; shift ;;
    --install-deps) INSTALL_DEPS="yes"; shift ;;
    --no-install-deps) INSTALL_DEPS="no"; shift ;;
    --proxy)
      if [ $# -lt 2 ] || [ -z "$2" ]; then echo "--proxy 后面要跟代理地址，例如 --proxy http://127.0.0.1:7890" >&2; usage 2; fi
      PROXY_ARG="$2"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "未知参数: $1" >&2; usage 2 ;;
  esac
done

print_codex_install_hint() {
  local indent="${1:-   }"
  echo "${indent}- 安装 Codex（官方命令）: curl -fsSL https://chatgpt.com/codex/install.sh | sh"
  [ "$(uname -s)" = "Darwin" ] && echo "${indent}  macOS 也可以用: brew install --cask codex"
  echo "${indent}  装好后登录: codex login"
}

print_claude_install_hint() {
  # 官方首推原生安装，brew / npm 作为备选；只提示，不代装
  local indent="${1:-   }"
  echo "${indent}- 安装 Claude Code（官方命令）: curl -fsSL https://claude.ai/install.sh | bash"
  [ "$(uname -s)" = "Darwin" ] && echo "${indent}  macOS 也可以用: brew install --cask claude-code"
  echo "${indent}  装好后登录: claude auth login"
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

# ---------------------------------------------------------------- 环境检测与自动安装
# 原则：先全面检查（只看不改），列出要做的事，用户按一次回车就逐项完成；已装好的不重复安装。
# 只使用写死在这里的官方安装地址，执行前把完整命令显示出来。
CLAUDE_INSTALL_CMD='curl -fsSL https://claude.ai/install.sh | bash'
# NON_INTERACTIVE=1：不让 Codex 安装脚本自己再问“现在启动吗”，登录由本脚本引导
CODEX_INSTALL_CMD='curl -fsSL https://chatgpt.com/codex/install.sh | NON_INTERACTIVE=1 sh'
if [ "${PEER_TEST_MODE:-}" = "1" ]; then
  # 仅供测试：用假的安装命令代替官方脚本，避免真的联网安装
  CLAUDE_INSTALL_CMD="${PEER_TEST_CLAUDE_INSTALL_CMD:-$CLAUDE_INSTALL_CMD}"
  CODEX_INSTALL_CMD="${PEER_TEST_CODEX_INSTALL_CMD:-$CODEX_INSTALL_CMD}"
fi

# 问答输入：通过 curl ... | bash 运行时，标准输入是脚本本身，所以改从终端（/dev/tty）读；
# 没有终端（CI、无人值守）时不提问。PEER_INSTALL_INPUT 仅供测试，从文件读取回答。
PROMPT_FD=""
INTERACTIVE_STDIN="/dev/null"
if [ -n "${PEER_INSTALL_INPUT:-}" ]; then
  exec 3<"$PEER_INSTALL_INPUT" && PROMPT_FD=3
elif ( : </dev/tty ) 2>/dev/null; then
  exec 3</dev/tty && PROMPT_FD=3 && INTERACTIVE_STDIN="/dev/tty"
fi

REPLY_LINE=""
ask_line() {
  # $1 提示语；回答放在 REPLY_LINE。读不到（无终端或输入结束）时视为空回答以外的“跳过”
  REPLY_LINE=""
  printf '%s' "$1"
  if [ -z "$PROMPT_FD" ] || ! IFS= read -r REPLY_LINE <&3; then
    REPLY_LINE="n"
    echo ""
  fi
}

ensure_local_bin_on_path() {
  # 官方安装脚本都装到 ~/.local/bin；本次运行内立即可用，不用重开终端
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
  esac
}

python_state() {
  # ok / old / missing。macOS 的 /usr/bin/python3 在没装“命令行开发者工具”时只是个占位程序，
  # 一运行就弹窗，所以先用 xcode-select 判断，不去触发它
  local py
  py="$(command -v python3 2>/dev/null || true)"
  if [ -z "$py" ]; then echo missing; return; fi
  if [ "$py" = "/usr/bin/python3" ] && [ "$(uname -s)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
    echo missing; return
  fi
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    echo ok
  else
    echo old
  fi
}

claude_state() {
  # ok / nologin / missing
  command -v claude >/dev/null 2>&1 || { echo missing; return; }
  if claude auth status 2>/dev/null | grep -Eq '"loggedIn"[[:space:]]*:[[:space:]]*true'; then echo ok; else echo nologin; fi
}

codex_state() {
  command -v codex >/dev/null 2>&1 || { echo missing; return; }
  if codex login status 2>&1 | grep -Eiq '^[[:space:]]*Logged in using'; then echo ok; else echo nologin; fi
}

network_ok() {
  # 能连上 Claude 和 OpenAI 的网站就算通（返回 403 之类也说明网络是通的）
  if [ "${PEER_TEST_MODE:-}" = "1" ] && [ -n "${PEER_TEST_NET:-}" ]; then
    [ "$PEER_TEST_NET" = "ok" ] || [ -n "${HTTPS_PROXY:-}" ]
    return
  fi
  curl -sS -m 8 -o /dev/null https://claude.ai >/dev/null 2>&1 &&
    curl -sS -m 8 -o /dev/null https://chatgpt.com >/dev/null 2>&1
}

valid_proxy() {
  case "$1" in
    http://?*|https://?*|socks5://?*|socks5h://?*)
      case "$1" in *[[:space:]]*) return 1 ;; esac
      return 0 ;;
  esac
  return 1
}

PROXY_TO_SAVE=""
use_proxy() {
  export HTTPS_PROXY="$1" HTTP_PROXY="$1" https_proxy="$1" http_proxy="$1"
  case "$1" in socks*) export ALL_PROXY="$1" all_proxy="$1" ;; esac
  PROXY_TO_SAVE="$1"
}

run_official_install() {
  # $1 名称，$2 命令。官方脚本不需要回答问题，标准输入接 /dev/null，避免吞掉本脚本的问答
  echo "   正在安装 $1，需要一两分钟，请稍候……"
  echo "   （运行的是官方安装命令：$2）"
  if bash -c "set -o pipefail; $2" </dev/null; then
    ensure_local_bin_on_path
    hash -r 2>/dev/null || true
    return 0
  fi
  return 1
}

install_python() {
  if [ "$(uname -s)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      echo "   正在用 Homebrew 安装 Python（运行：brew install python）……"
      brew install python </dev/null && hash -r && return 0
      return 1
    fi
    echo "   马上会弹出一个“安装命令行开发者工具”的窗口，请点【安装】，等它装完（几分钟）。"
    xcode-select --install >/dev/null 2>&1 || true
    echo ""
    echo "👉 装好后，请重新运行一次刚才的安装命令，剩下的会自动完成。"
    exit 1
  fi
  local cmd=""
  if command -v apt-get >/dev/null 2>&1; then cmd="sudo apt-get install -y python3"
  elif command -v dnf >/dev/null 2>&1; then cmd="sudo dnf install -y python3"
  elif command -v pacman >/dev/null 2>&1; then cmd="sudo pacman -S --noconfirm python"
  fi
  if [ -z "$cmd" ]; then
    echo "   没找到能自动安装 Python 的方式。请用系统自带的软件管理工具安装 Python 3.9 或更新版本，然后重新运行安装命令。"
    return 1
  fi
  echo "   正在安装 Python（运行：$cmd），可能会要求输入你的电脑登录密码……"
  bash -c "$cmd" <"$INTERACTIVE_STDIN" && hash -r
}

login_cli() {
  # $1 claude|codex
  if [ "$INTERACTIVE_STDIN" != "/dev/tty" ] && [ -z "${PEER_INSTALL_INPUT:-}" ]; then
    echo "   ⚠️ 现在不是在终端里运行，没法打开登录页面。装好后请自己运行：$( [ "$1" = claude ] && echo 'claude auth login' || echo 'codex login' )"
    return 1
  fi
  if [ "$1" = "claude" ]; then
    echo "   接下来登录 Claude：会打开浏览器，用你的 Claude 账号（Pro / Max 等付费版）登录并授权，完成后回到这里。"
    claude auth login <"$INTERACTIVE_STDIN"
  else
    echo "   接下来登录 Codex：会打开浏览器，选“用 ChatGPT 登录”（Plus / Pro 等付费版），完成后回到这里。"
    codex login <"$INTERACTIVE_STDIN"
  fi
}

state_text() {
  # $1 名称 $2 状态
  case "$2" in
    ok) echo "   ✅ $1：已安装，已登录" ;;
    nologin) echo "   ⚠️  $1：已安装，还没登录" ;;
    missing) echo "   ❌ $1：没有安装" ;;
  esac
}

print_manual_steps() {
  echo ""
  echo "   需要你手动完成的事："
  if [ "$PY_STATE" != "ok" ]; then
    if [ "$(uname -s)" = "Darwin" ]; then
      echo "   - 安装 Python 3.9 或更新版本：运行 xcode-select --install（会弹窗，点【安装】），或者 brew install python"
    else
      echo "   - 安装 Python 3.9 或更新版本：Ubuntu / Debian 运行 sudo apt-get install python3，Fedora 运行 sudo dnf install python3，Arch 运行 sudo pacman -S python"
    fi
  fi
  [ "$CLAUDE_STATE" = "missing" ] && print_claude_install_hint "   "
  [ "$CLAUDE_STATE" = "nologin" ] && echo "   - 登录 Claude: claude auth login"
  [ "$CODEX_STATE" = "missing" ] && print_codex_install_hint "   "
  [ "$CODEX_STATE" = "nologin" ] && echo "   - 登录 Codex: codex login"
  [ "$NET_STATE" = "fail" ] && echo "   - 连不上 Claude / OpenAI：国内网络一般要开代理，可以重新运行并加上 --proxy http://127.0.0.1:你的代理端口"
  return 0
}

setup_environment() {
  echo "==> 1. 检查电脑环境（只检查，不做改动）..."
  case "$(uname -s)" in
    Darwin|Linux) ;;
    *)
      echo "❌ 这台电脑的系统暂不支持。PeerAgent 支持 macOS 和 Linux；Windows 请先装 WSL2，在 WSL2 里运行安装命令。" >&2
      exit 1 ;;
  esac
  ensure_local_bin_on_path
  if [ -n "$PROXY_ARG" ]; then
    if ! valid_proxy "$PROXY_ARG"; then
      echo "❌ 代理地址的写法不对：$PROXY_ARG。应该像 http://127.0.0.1:7890 或 socks5://127.0.0.1:7891 这样。" >&2
      exit 2
    fi
    use_proxy "$PROXY_ARG"
  fi

  PY_STATE="$(python_state)"
  CLAUDE_STATE="$(claude_state)"
  CODEX_STATE="$(codex_state)"
  NET_STATE="skip"
  local acting=0
  if [ "$INSTALL_DEPS" = "yes" ] || { [ "$INSTALL_DEPS" = "ask" ] && [ -n "$PROMPT_FD" ]; }; then
    acting=1
    if network_ok; then NET_STATE="ok"; else NET_STATE="fail"; fi
  fi

  echo "   检查结果："
  case "$PY_STATE" in
    ok) echo "   ✅ Python：$(python3 -c 'import platform; print(platform.python_version())')" ;;
    old) echo "   ❌ Python：版本太旧（$(python3 -c 'import platform; print(platform.python_version())' 2>/dev/null)），需要 3.9 或更新" ;;
    missing) echo "   ❌ Python：没有安装" ;;
  esac
  state_text "Claude Code（在 Codex 里用 /claude 需要它）" "$CLAUDE_STATE"
  state_text "Codex（在 Claude 里用 /codex 需要它）" "$CODEX_STATE"
  case "$NET_STATE" in
    ok) echo "   ✅ 网络：能连上 Claude 和 OpenAI" ;;
    fail) echo "   ❌ 网络：连不上 Claude / OpenAI（国内网络一般需要代理）" ;;
  esac
  # 代理是靠环境变量连上的：保存给 peer，从桌面 App 里调用时也能用上
  if [ "$NET_STATE" = "ok" ] && [ -z "$PROXY_TO_SAVE" ]; then
    local envp="${HTTPS_PROXY:-${https_proxy:-${ALL_PROXY:-${all_proxy:-}}}}"
    if [ -n "$envp" ] && valid_proxy "$envp"; then PROXY_TO_SAVE="$envp"; fi
  fi

  local todo=()
  [ "$NET_STATE" = "fail" ] && todo+=("设置代理（你输入代理地址，没有就跳过）")
  [ "$PY_STATE" = "ok" ] || todo+=("安装 Python")
  [ "$CLAUDE_STATE" = "missing" ] && todo+=("安装 Claude Code（官方命令：curl -fsSL https://claude.ai/install.sh | bash）")
  [ "$CODEX_STATE" = "missing" ] && todo+=("安装 Codex（官方命令：curl -fsSL https://chatgpt.com/codex/install.sh | sh）")
  [ "$CLAUDE_STATE" = "ok" ] || todo+=("登录 Claude（会打开浏览器）")
  [ "$CODEX_STATE" = "ok" ] || todo+=("登录 Codex（会打开浏览器）")

  if [ ${#todo[@]} -eq 0 ]; then
    echo "   一切就绪，不需要额外安装。"
  elif [ "$acting" = "0" ]; then
    if [ "$INSTALL_DEPS" = "no" ]; then
      echo "   （你选择了只检查不安装）"
    else
      echo "   （现在不是在终端里交互运行，不会自动安装；想全自动安装可以加上 --install-deps）"
    fi
    print_manual_steps
  else
    echo ""
    echo "   接下来会自动帮你完成："
    local i=1 t
    for t in "${todo[@]}"; do echo "   $i. $t"; i=$((i + 1)); done
    local go=1
    if [ "$INSTALL_DEPS" = "ask" ]; then
      ask_line "   按【回车】开始，输入 n 再回车可跳过这些步骤："
      case "$REPLY_LINE" in ""|y|Y|yes|YES|是|好) go=1 ;; *) go=0 ;; esac
    fi
    if [ "$go" = "0" ]; then
      echo "   好的，跳过自动安装。"
      print_manual_steps
    else
      do_environment_steps
    fi
  fi

  if [ "$PY_STATE" != "ok" ]; then
    echo "" >&2
    echo "❌ 还没有可用的 Python（需要 3.9 或更新版本），PeerAgent 暂时装不上。按上面的提示装好 Python 后，重新运行安装命令即可。" >&2
    exit 1
  fi
  HAS_CLAUDE=0; HAS_CODEX=0
  [ "$CLAUDE_STATE" = "missing" ] || HAS_CLAUDE=1
  [ "$CODEX_STATE" = "missing" ] || HAS_CODEX=1
}

do_environment_steps() {
  if [ "$NET_STATE" = "fail" ]; then
    echo ""
    echo "   【设置代理】如果你在用代理软件（如 Clash、V2Ray），请输入它的地址，"
    echo "   例如 http://127.0.0.1:7890（端口号在代理软件的设置里能看到）。没有代理就直接按回车跳过。"
    if [ "$INSTALL_DEPS" = "ask" ]; then
      while :; do
        ask_line "   代理地址："
        [ -z "$REPLY_LINE" ] || [ "$REPLY_LINE" = "n" ] && break
        if valid_proxy "$REPLY_LINE"; then
          use_proxy "$REPLY_LINE"
          if network_ok; then NET_STATE="ok"; echo "   ✅ 用这个代理能连上了。"; break; fi
          echo "   ⚠️ 用这个代理还是连不上，请检查代理软件是否已打开、端口是否正确，然后再输入一次（直接回车跳过）。"
        else
          echo "   ⚠️ 写法不对，应该像 http://127.0.0.1:7890 这样，请再输入一次（直接回车跳过）。"
        fi
      done
    fi
    [ "$NET_STATE" = "ok" ] || echo "   ⚠️ 网络还是不通，下面的安装和登录可能会失败；失败了也没关系，开好代理后重新运行安装命令即可。"
  fi

  if [ "$PY_STATE" != "ok" ]; then
    echo ""
    echo "   【安装 Python】"
    if install_python; then PY_STATE="$(python_state)"; fi
    [ "$PY_STATE" = "ok" ] && echo "   ✅ Python 装好了。" || echo "   ❌ Python 没装成功。"
  fi

  if [ "$CLAUDE_STATE" = "missing" ]; then
    echo ""
    echo "   【安装 Claude Code】"
    if run_official_install "Claude Code" "$CLAUDE_INSTALL_CMD"; then CLAUDE_STATE="$(claude_state)"; fi
    if [ "$CLAUDE_STATE" = "missing" ]; then
      echo "   ❌ Claude Code 没装成功。多半是网络问题：开好代理后重新运行安装命令；也可以参考官方说明 https://code.claude.com/docs/en/setup"
    else
      echo "   ✅ Claude Code 装好了。"
    fi
  fi

  if [ "$CODEX_STATE" = "missing" ]; then
    echo ""
    echo "   【安装 Codex】"
    if run_official_install "Codex" "$CODEX_INSTALL_CMD"; then CODEX_STATE="$(codex_state)"; fi
    if [ "$CODEX_STATE" = "missing" ]; then
      echo "   ❌ Codex 没装成功。多半是网络问题：开好代理后重新运行安装命令；也可以参考官方说明 https://github.com/openai/codex"
    else
      echo "   ✅ Codex 装好了。"
    fi
  fi

  if [ "$CLAUDE_STATE" = "nologin" ]; then
    echo ""
    echo "   【登录 Claude】"
    login_cli claude || true
    CLAUDE_STATE="$(claude_state)"
    [ "$CLAUDE_STATE" = "ok" ] && echo "   ✅ Claude 已登录。" || echo "   ⚠️ Claude 还没登录成功，稍后可以自己运行：claude auth login"
  fi

  if [ "$CODEX_STATE" = "nologin" ]; then
    echo ""
    echo "   【登录 Codex】"
    login_cli codex || true
    CODEX_STATE="$(codex_state)"
    [ "$CODEX_STATE" = "ok" ] && echo "   ✅ Codex 已登录。" || echo "   ⚠️ Codex 还没登录成功，稍后可以自己运行：codex login"
  fi
  return 0
}

save_proxy_config() {
  # 把代理写进 config.json 的 child_env，让 peer 调用 Claude / Codex 时也走代理；已有 child_env 时不动
  [ -n "$PROXY_TO_SAVE" ] || return 0
  python3 - "$PEER_HOME/config.json" "$PROXY_TO_SAVE" <<'PY' || echo "   ⚠️ 代理没能写进配置文件，可以稍后手动在 ~/.peer-review/config.json 的 child_env 里填写。"
import json, os, sys
path, url = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)
env = cfg.get("child_env")
if isinstance(env, dict) and env:
    print("   代理：配置文件里已经设置过 child_env，保持不变。")
    sys.exit(0)
keys = ["HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"]
if url.startswith("socks"):
    keys += ["ALL_PROXY", "all_proxy"]
cfg["child_env"] = {k: url for k in keys}
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
os.replace(tmp, path)
print("   ✅ 已把代理 %s 保存给 peer（config.json 的 child_env），以后调用 Claude / Codex 都会走这个代理。" % url)
PY
}

preflight_paths

if [ "$MODE" = "uninstall" ]; then
  uninstall_peer
fi

print_banner

setup_environment

echo "==> 2. 安装 PeerAgent 本身..."
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
save_proxy_config

echo "==> 3. 把 /codex、/claude 技能装进各个 AI 工具..."

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

  if [[ ":$ORIGINAL_PATH:" == *":$LOCAL_BIN:"* ]]; then
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
  # 只列出现在真能用的用法；缺的一侧告诉用户重新运行安装命令就会自动补上
  echo ""
  if [ "$HAS_CLAUDE" = "1" ] || [ "$HAS_CODEX" = "1" ]; then
    echo "怎么用：在你平时用的 AI 编程工具里直接输入"
    [ "$HAS_CODEX" = "1" ] && echo "  - 在 Claude Code 里：/codex 帮我审一下刚才的改动"
    [ "$HAS_CLAUDE" = "1" ] && echo "  - 在 Codex 里：/claude 帮我审一下刚才的改动"
    echo "  - 在 Antigravity 里：/codex 或 /claude，后面写上你的要求"
    echo "  提问和审阅不会改动你的文件；要让它动手修改，请以 exec 开头，例如：/codex exec 修复登录超时的问题"
  fi
  if [ "$HAS_CLAUDE" = "0" ] || [ "$HAS_CODEX" = "0" ]; then
    echo ""
    [ "$HAS_CODEX" = "0" ] && echo "  还不能在 Claude Code 里用 /codex：这台电脑没装 Codex。"
    [ "$HAS_CLAUDE" = "0" ] && echo "  还不能在 Codex 里用 /claude：这台电脑没装 Claude Code。"
    echo "  想补上的话，重新运行一次安装命令，缺的会自动装好。"
  fi
  echo ""
}

echo "==> 4. 最后检查一遍..."
# 显式保存 doctor 的真实退出码，不能让后续提示命令覆盖为 0
DOCTOR_RC=0
"$LOCAL_BIN/peer" doctor || DOCTOR_RC=$?
if [ "$DOCTOR_RC" = "0" ]; then
  echo ""
  if [ "$HAS_CLAUDE" = "1" ] && [ "$HAS_CODEX" = "1" ]; then
    echo "🎉 安装完成，全部检查通过！"
  else
    echo "✅ 安装完成，检查通过（目前只装了一边，所以只能单向使用）。"
  fi
  print_usage_hint
  configure_path_if_needed
else
  echo ""
  if [ "$DOCTOR_RC" = "3" ]; then
    echo "⛔ 之前检测到账号可能出了严重问题（比如被停用），peer 已暂停调用来保护账号。"
    echo "   请先确认账号正常，再按上面列出的路径，由你本人手动删除那个 STOP 文件。"
  else
    echo "⚠️ PeerAgent 已经装好，但还有几项没就绪：请看上面带 ⚠️ 或“找不到”的行。"
    echo "   最常见的是还没登录：运行 claude auth login 或 codex login；也可以直接重新运行一次安装命令，缺的会自动补上。"
    echo "   处理完后运行 peer doctor 再检查一次。"
  fi
  print_usage_hint
  configure_path_if_needed
  exit "$DOCTOR_RC"
fi
