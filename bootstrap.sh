#!/usr/bin/env bash
# managed-by: peer-agent
# PeerAgent 一行命令安装入口：
#   curl -fsSL https://raw.githubusercontent.com/puck-muling/peer-agent/main/bootstrap.sh | bash
# 只做三件事：查最新发布版本 → 下载该版本源码到 ~/.peer-review/src/ → 运行其中的 install.sh。
# 后面可以跟 install.sh 的参数，例如：... | bash -s -- --proxy http://127.0.0.1:7890
# 指定版本：... | bash -s -- --version v0.1.3

set -euo pipefail

REPO="puck-muling/peer-agent"
PEER_HOME="${PEER_HOME:-$HOME/.peer-review}"
VERSION=""
PASS=()

fail() {
  echo "" >&2
  echo "❌ $1" >&2
  [ -n "${2:-}" ] && echo "👉 $2" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version)
      [ $# -ge 2 ] || fail "--version 后面要跟版本号，例如 --version v0.1.3"
      VERSION="$2"; shift 2 ;;
    *) PASS+=("$1"); shift ;;
  esac
done

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) fail "这台电脑的系统暂不支持一行命令安装。" "PeerAgent 支持 macOS 和 Linux；Windows 请先装 WSL2，在 WSL2 的终端里运行这条命令。" ;;
esac
command -v curl >/dev/null 2>&1 || fail "这台电脑没有 curl，没法下载安装包。" "macOS 自带 curl；Linux 可以运行 sudo apt-get install curl（Ubuntu / Debian）后再试。"
command -v tar >/dev/null 2>&1 || fail "这台电脑没有 tar，没法解压安装包。" "Linux 可以运行 sudo apt-get install tar 后再试。"

# --proxy 也用于下载本身：国内网络连 GitHub 常常需要代理
for ((i = 0; i < ${#PASS[@]}; i++)); do
  if [ "${PASS[$i]}" = "--proxy" ] && [ $((i + 1)) -lt ${#PASS[@]} ]; then
    p="${PASS[$((i + 1))]}"
    export HTTPS_PROXY="$p" HTTP_PROXY="$p" https_proxy="$p" http_proxy="$p"
  fi
done

echo "==> 下载 PeerAgent ..."
if [ -z "$VERSION" ]; then
  # 最新发布版本：跟随 releases/latest 的跳转地址取版本号，不依赖 GitHub API 的调用次数限制
  latest_url="$(curl -fsSIL -m 30 -o /dev/null -w '%{url_effective}' "https://github.com/$REPO/releases/latest" 2>/dev/null || true)"
  VERSION="${latest_url##*/}"
fi
case "$VERSION" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) fail "连不上 GitHub，查不到最新版本。" "国内网络一般需要代理：先打开代理软件，再运行：curl -fsSL https://raw.githubusercontent.com/$REPO/main/bootstrap.sh | bash -s -- --proxy http://127.0.0.1:你的代理端口" ;;
esac
case "$VERSION" in
  *[!A-Za-z0-9._-]*) fail "版本号的写法不对：$VERSION" "应该像 v0.1.3 这样。" ;;
esac

ARCHIVE_URL="${PEER_BOOTSTRAP_ARCHIVE_URL:-https://github.com/$REPO/archive/refs/tags/$VERSION.tar.gz}"
DEST="$PEER_HOME/src/peer-agent-$VERSION"
if [ -f "$DEST/install.sh" ]; then
  echo "   已经下载过 $VERSION，直接使用：$DEST"
else
  mkdir -p "$PEER_HOME/src"
  tmp="$(mktemp -d "$PEER_HOME/src/.download.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  echo "   版本：$VERSION（从 GitHub 下载）"
  curl -fsSL -m 300 "$ARCHIVE_URL" -o "$tmp/src.tar.gz" ||
    fail "下载安装包失败（$ARCHIVE_URL）。" "多半是网络问题：打开代理软件后，在命令末尾加上 --proxy 参数再试，例如 ... | bash -s -- --proxy http://127.0.0.1:7890"
  tar -xzf "$tmp/src.tar.gz" -C "$tmp" || fail "安装包解压失败，可能没下载完整。" "请重新运行一次安装命令。"
  extracted="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [ -n "$extracted" ] && [ -f "$extracted/install.sh" ] || fail "安装包里没有找到 install.sh，下载的内容不对。" "请重新运行一次安装命令；还不行的话到 https://github.com/$REPO/issues 反馈。"
  mv "$extracted" "$DEST"
  # 下面用 exec 交给 install.sh，EXIT 陷阱不会再触发，临时目录在这里清掉
  rm -rf "$tmp"
  trap - EXIT
fi

echo "==> 开始安装（$DEST）"
cd "$DEST"
exec bash ./install.sh --copy ${PASS[@]+"${PASS[@]}"}
