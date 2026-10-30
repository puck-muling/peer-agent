#!/usr/bin/env bash
# PeerAgent 一键安装脚本
# 支持 macOS 与 Linux (Ubuntu/Debian/Fedora/Arch)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PEER_HOME="${PEER_HOME:-$HOME/.peer-review}"
LOCAL_BIN="$HOME/.local/bin"
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
  echo "用法: $0 [选项]"
  echo "选项:"
  echo "  --link       使用软链接安装（适合开发者，修改代码立即生效）"
  echo "  --copy       使用文件复制安装（默认方式）"
  echo "  --uninstall  卸载 PeerAgent 及相关技能配置（若有安装前备份将自动还原）"
  echo "  -h, --help   显示本帮助信息"
  exit 0
}

# 解析参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --copy) MODE="copy"; shift ;;
    --uninstall) MODE="uninstall"; shift ;;
    -h|--help) usage ;;
    *) echo "未知参数: $1" >&2; usage ;;
  esac
done

safe_uninstall_skill() {
  local dst="$1"
  if [ -L "$dst" ] || [ -f "$dst" ]; then
    rm -f "$dst"
    local parent
    parent="$(dirname "$dst")"
    local base
    base="$(basename "$dst")"
    local latest_bak
    latest_bak="$(ls -t "${parent}/${base}".bak_* 2>/dev/null | head -n 1 || true)"
    if [ -n "$latest_bak" ] && [ -f "$latest_bak" ]; then
      echo "   还原备份技能: $(basename "$latest_bak") -> $base"
      mv "$latest_bak" "$dst"
    fi
  fi
  rmdir "$(dirname "$dst")" 2>/dev/null || true
}

uninstall_peer() {
  echo "正在卸载 PeerAgent..."
  rm -f "$LOCAL_BIN/peer"
  rm -f "$PEER_HOME/bin/peer"
  safe_uninstall_skill "$HOME/.gemini/config/skills/codex/SKILL.md"
  safe_uninstall_skill "$HOME/.gemini/config/skills/claude/SKILL.md"
  safe_uninstall_skill "$HOME/.claude/skills/codex/SKILL.md"
  safe_uninstall_skill "$HOME/.codex/skills/claude/SKILL.md"
  echo "✅ 已移除技能链接与执行程序。保留 ~/.peer-review 历史数据。"
  exit 0
}

safe_install_skill() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ]; then
    rm -f "$dst"
  elif [ -e "$dst" ]; then
    if ! cmp -s "$src" "$dst" 2>/dev/null; then
      local bak="${dst}.bak_$(date +%Y%m%d%H%M%S)"
      echo "      检测到已有技能文件，已备份至: $bak"
      mv "$dst" "$bak"
    fi
  fi
  if [ "$MODE" = "link" ]; then
    ln -sf "$src" "$dst"
  else
    cp -f "$src" "$dst"
  fi
}

if [ "$MODE" = "uninstall" ]; then
  uninstall_peer
fi

print_banner

echo "==> 1. 检查基础依赖环境..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 错误: 未检测到 python3，PeerAgent 核心调度器依赖 Python 3.10+。" >&2
  exit 1
fi

PY_VER=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
PY_CHECK=$(python3 -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)")
if [ "$PY_CHECK" != "1" ]; then
  echo "❌ 错误: PeerAgent 要求 Python 3.10 及以上版本（当前检测到: $PY_VER）。请先升级 Python。" >&2
  exit 1
fi
echo "   Python 版本: $PY_VER (符合 >= 3.10 要求)"

if command -v claude >/dev/null 2>&1; then
  echo "   Claude CLI: 已安装 ($(claude --version 2>/dev/null || echo 'OK'))"
else
  echo "   ⚠️ 提示: 未检测到 'claude' CLI。若需调用 Claude，请先安装官方 Claude Code: npm install -g @anthropic-ai/claude-code"
fi

if command -v codex >/dev/null 2>&1; then
  echo "   Codex CLI: 已安装 ($(codex --version 2>/dev/null || echo 'OK'))"
else
  echo "   ⚠️ 提示: 未检测到 'codex' CLI。若需调用 Codex，请先安装官方 Codex CLI。"
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
  cp -f "$SCRIPT_DIR/bin/peer" "$PEER_HOME/bin/peer"
  chmod +x "$PEER_HOME/bin/peer"
  cp -f "$SCRIPT_DIR/bin/peer" "$LOCAL_BIN/peer"
  chmod +x "$LOCAL_BIN/peer"
  cp -f "$SCRIPT_DIR/templates"/*.md "$PEER_HOME/templates/"
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

# B. Claude Code Skill
safe_install_skill "$SCRIPT_DIR/skills/claude/codex/SKILL.md" "$HOME/.claude/skills/codex/SKILL.md"
echo "   [Claude Code] 已安装 /codex 技能。"

# C. Codex Skill
safe_install_skill "$SCRIPT_DIR/skills/codex/claude/SKILL.md" "$HOME/.codex/skills/claude/SKILL.md"
echo "   [Codex CLI]   已安装 /claude 技能。"

echo "==> 4. 运行自检验证..."
if "$LOCAL_BIN/peer" doctor; then
  echo ""
  echo "🎉 恭喜！PeerAgent 安装完成并自检通过！"
  echo ""
  echo "使用方式："
  echo "  1. 在 Antigravity 对话框中直接输入: /codex 审一下当前代码"
  echo "  2. 在 Claude Code 终端中输入:       /codex 检查这个函数的逻辑边界"
  echo "  3. 在 Codex CLI 中输入:             /claude 审阅当前改动"
  echo ""
  echo "提示: 请确保 $LOCAL_BIN 已加入系统的 PATH 环境变量（如 export PATH=\"\$HOME/.local/bin:\$PATH\"）。"
else
  echo "⚠️ 自检发现部分配置需确认，请根据上述提示核查。"
fi
