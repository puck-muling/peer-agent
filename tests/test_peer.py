#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PeerAgent Comprehensive Unit Test Suite"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

import importlib.util
from importlib.machinery import SourceFileLoader

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
peer_bin_path = os.path.join(REPO_DIR, "bin", "peer")

_loader = SourceFileLoader("peer", peer_bin_path)
_spec = importlib.util.spec_from_loader("peer", _loader)
peer = importlib.util.module_from_spec(_spec)
sys.modules["peer"] = peer
_loader.exec_module(peer)


def run_skill_router(text, workdir):
    """执行技能文件中的路由代码，避免用测试内的副本掩盖真实回归。"""
    skill_file = os.path.join(REPO_DIR, "skills", "claude", "codex", "SKILL.md")
    with open(skill_file, encoding="utf-8") as f:
        content = f.read()
    code = re.search(r"python3 -c '\n(.*?)\n' \"\$REQ_FILE\"", content, re.S).group(1)
    request = os.path.join(workdir, "request.md")
    with open(request, "w", encoding="utf-8") as f:
        f.write("# 任务\n%s\n" % text)
    return subprocess.run([sys.executable, "-c", code, request],
                          capture_output=True, text=True, check=True)


class TestPeerCore(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.test_dir = tmp.name

    def test_depth_tracking(self):
        """测试防递归调用的深度标记"""
        self.assertFalse(peer.is_nested_depth(""))
        self.assertFalse(peer.is_nested_depth("0"))
        self.assertTrue(peer.is_nested_depth("1"))
        self.assertTrue(peer.is_nested_depth("2"))
        self.assertTrue(peer.is_nested_depth("true"))
        self.assertTrue(peer.is_nested_depth("yes"))

    def test_child_env_taint(self):
        """测试环境变量清洗与 PEER_DEPTH 注入"""
        base = {"ANTIGRAVITY_TOKEN": "secret", "PATH": "/bin", "PEER_DEPTH": "0"}
        env = peer.child_env(base)
        self.assertNotIn("ANTIGRAVITY_TOKEN", env)
        self.assertEqual(env["PEER_DEPTH"], "1")

        # 嵌套时递增
        base2 = {"PATH": "/bin", "PEER_DEPTH": "1"}
        env2 = peer.child_env(base2)
        self.assertEqual(env2["PEER_DEPTH"], "2")

    def test_scrub_email(self):
        """测试个人邮箱脱敏过滤"""
        text = "Contact me at alice@example.com or bob.smith+dev@company.org."
        scrubbed = peer.scrub(text)
        self.assertNotIn("alice@example.com", scrubbed)
        self.assertNotIn("bob.smith+dev@company.org", scrubbed)
        self.assertIn("<邮箱已隐藏>", scrubbed)
        self.assertEqual(peer.scrub(None), "")

    def test_fatal_banned_patterns(self):
        """测试致命封号与风控停机检测正则"""
        banned_log = "Error: your account has been deactivated by policy."
        pat, snippet, cat = peer.scan_fatal_auth_error(None, info_error=banned_log)
        self.assertEqual(cat, "banned")
        self.assertIsNotNone(pat)

        relogin_log = "HTTP status 401 unauthorized: refresh_token_expired"
        pat2, snippet2, cat2 = peer.scan_fatal_auth_error(None, info_error=relogin_log)
        self.assertEqual(cat2, "relogin")

        normal_log = "SyntaxError: invalid syntax in file.py at line 10"
        pat3, snippet3, cat3 = peer.scan_fatal_auth_error(None, info_error=normal_log)
        self.assertEqual(cat3, "")

    def test_write_stop_lock_no_name_error(self):
        """测试写入熔断停机锁（验证 PEER_HOME 正确引用，绝无 NameError）"""
        tmp_dir = self.test_dir
        orig_home = peer.PEER_HOME
        try:
            peer.PEER_HOME = tmp_dir
            peer.trigger_circuit_breaker("Test trigger reason", "test-run-123", "codex")
            expected_lock = os.path.join(tmp_dir, "STOP-codex")
            self.assertTrue(os.path.exists(expected_lock))
            with open(expected_lock, "r", encoding="utf-8") as f:
                self.assertIn("Test trigger reason", f.read())
        finally:
            peer.PEER_HOME = orig_home

    def test_claude_skill_intent_parsing(self):
        """测试 Claude 端技能的真实 Python 意图解析逻辑。"""
        test_cases = [
            ("exec 修改这个函数", "exec"),
            ("review 审阅 README", "review"),
            ("plan 针对登录做个方案", "plan"),
            ("advice 看看为什么超时", "advice"),
            ("image 生成一张架构图", "image"),
            ("不要修改任何文件，只查代码", "review"),
            ("严禁修改代码，出个方案", "review"),
            ("请勿修改文件，给个建议", "review"),
            ("帮我评估是否需要修改这个函数", "review"),
            ("exec 请勿修改", "review"),
            ("修改这个 bug", "exec"),
            ("给个重构方案", "plan"),
            ("分析一下为什么内存泄露", "advice"),
            ("echo $(whoami)", "review"),  # 确保无 shell 命令注入
        ]

        for prompt, expected in test_cases:
            with self.subTest(prompt=prompt):
                res = run_skill_router(prompt, self.test_dir)
                self.assertEqual(json.loads(res.stdout)["kind"], expected)


class TestPeerExtended(unittest.TestCase):
    """扩展测试用例：覆盖快照对比、项目安全边界、配置读写、用量统计及 CLI 烟雾测试"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.test_dir = tmp.name

    def test_project_root_security(self):
        """测试根目录、家目录及桌面目录安全校验"""
        # 允许合法子目录
        sub = os.path.join(self.test_dir, "my_project")
        os.makedirs(sub, exist_ok=True)
        self.assertEqual(peer.project_root(sub), os.path.realpath(sub))

        # 拒绝非法路径
        with self.assertRaises(SystemExit):
            peer.project_root("/")
        with self.assertRaises(SystemExit):
            peer.project_root(peer.HOME)
        desktop = os.path.join(peer.HOME, "Desktop")
        if os.path.exists(desktop):
            with self.assertRaises(SystemExit):
                peer.project_root(desktop)

    def test_run_id_regex_validation(self):
        """测试 run_id 格式校验，防止路径穿越"""
        valid_ids = [
            "20261030-111801-codex-review",
            "20261030-111806-claude-plan",
            "20261030-120000-codex-exec-1",
        ]
        for vid in valid_ids:
            self.assertIsNotNone(re.fullmatch(r"[0-9]{8}-[0-9]{6}-(codex|claude)-[a-z]+(-[0-9]+)?", vid))

        invalid_ids = [
            "../../etc/passwd",
            "20261030-111801-gemini-review",
            "invalid_id",
            "",
            "20261030-111801-codex-review;rm -rf /",
        ]
        for inv in invalid_ids:
            self.assertIsNone(re.fullmatch(r"[0-9]{8}-[0-9]{6}-(codex|claude)-[a-z]+(-[0-9]+)?", inv))

    def test_is_text_detection(self):
        """测试文本与二进制文件识别"""
        text_file = os.path.join(self.test_dir, "hello.txt")
        with open(text_file, "w", encoding="utf-8") as f:
            f.write("Hello world!\nLine 2\n")
        self.assertTrue(peer.is_text(text_file, os.path.getsize(text_file)))

        bin_file = os.path.join(self.test_dir, "binary.dat")
        with open(bin_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\xff")
        self.assertFalse(peer.is_text(bin_file, os.path.getsize(bin_file)))

        # 超过上限视为非文本
        self.assertFalse(peer.is_text(text_file, peer.COPY_MAX + 1))

    def test_snapshot_and_compare_lifecycle(self):
        """测试项目快照与改动对比，确保敏感文件掩码及增删改正确检测"""
        proj = os.path.join(self.test_dir, "project")
        os.makedirs(proj, exist_ok=True)

        # 创建普通文件与敏感文件
        f1 = os.path.join(proj, "main.py")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("print('v1')\n")

        f_env = os.path.join(proj, ".env")
        with open(f_env, "w", encoding="utf-8") as f:
            f.write("SECRET_KEY=supersecret123\n")

        f_del = os.path.join(proj, "to_delete.txt")
        with open(f_del, "w", encoding="utf-8") as f:
            f.write("delete me\n")

        snap_dest = os.path.join(self.test_dir, "snap")
        manifest = peer.snapshot(proj, snap_dest)
        self.assertTrue(os.path.exists(os.path.join(snap_dest, "manifest.json")))
        self.assertTrue(manifest["entries"][".env"].get("secret"))

        # 修改 main.py，删除 to_delete.txt，新增 new.txt，修改 .env
        with open(f1, "w", encoding="utf-8") as f:
            f.write("print('v2')\n")
        os.remove(f_del)
        f_new = os.path.join(proj, "new.txt")
        with open(f_new, "w", encoding="utf-8") as f:
            f.write("new content\n")
        with open(f_env, "w", encoding="utf-8") as f:
            f.write("SECRET_KEY=changedsecret\n")

        diff_res = peer.compare(snap_dest, proj)
        self.assertIn("main.py", diff_res["modified"])
        self.assertIn(".env", diff_res["modified"])
        self.assertIn("to_delete.txt", diff_res["deleted"])
        self.assertIn("new.txt", diff_res["added"])

        # 确保敏感文件的具体内容不暴露在 diff 文本中
        self.assertNotIn("supersecret123", diff_res["diff"])
        self.assertNotIn("changedsecret", diff_res["diff"])
        self.assertTrue(any(".env" in item for item in diff_res["no_diff"]))

    def test_fmt_tokens_and_usage(self):
        """测试 Token 用量格式化"""
        self.assertEqual(peer.fmt_tokens(0), "0")
        self.assertEqual(peer.fmt_tokens(950), "950")
        self.assertEqual(peer.fmt_tokens(1000), "1,000")
        self.assertEqual(peer.fmt_tokens(10000), "1 万")
        self.assertEqual(peer.fmt_tokens(25000), "2.5 万")
        self.assertEqual(peer.fmt_tokens(None), "0")
        self.assertEqual(peer.fmt_tokens("invalid"), "?")

        usage = {"input": 12000, "cached": 4000, "output": 800, "thinking": 200, "cost_usd": 0.05}
        desc = peer.describe_usage(usage, auth_category="subscription")
        self.assertIn("读入 1.2 万", desc)
        self.assertIn("缓存 4,000", desc)
        self.assertIn("订阅不另收费", desc)

    def test_config_load_and_atomic_save(self):
        """测试配置文件读取默认值与原子写入"""
        cfg_file = os.path.join(self.test_dir, "config.json")
        orig_cfg_path = peer.CONFIG_PATH
        try:
            peer.CONFIG_PATH = cfg_file
            # 不存在时返回默认配置
            cfg = peer.load_config()
            self.assertEqual(cfg["bins"]["claude"], "claude")

            # 修改并保存
            cfg["bins"]["claude"] = "/usr/local/bin/claude"
            peer.save_config(cfg)
            self.assertTrue(os.path.exists(cfg_file))

            # 重新读取验证
            loaded = peer.load_config()
            self.assertEqual(loaded["bins"]["claude"], "/usr/local/bin/claude")
        finally:
            peer.CONFIG_PATH = orig_cfg_path

    def test_cli_smoke(self):
        """测试 CLI 命令行入口响应 --help、--version 与 stats"""
        bin_path = os.path.join(REPO_DIR, "bin", "peer")

        # --help
        res = subprocess.run([sys.executable, bin_path, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("peer", res.stdout)
        self.assertIn("doctor", res.stdout)
        self.assertIn("ask", res.stdout)

        # --version
        res_ver = subprocess.run([sys.executable, bin_path, "--version"], capture_output=True, text=True)
        self.assertEqual(res_ver.returncode, 0)
        self.assertIn("peer 0.1.1", res_ver.stdout)

        # stats
        res_stats = subprocess.run([sys.executable, bin_path, "stats"], capture_output=True, text=True)
        self.assertEqual(res_stats.returncode, 0)
        self.assertIn("今天", res_stats.stdout)

    def test_pyproject_toml_packaging_declaration(self):
        """测试 pyproject.toml 声明完整性，防止构建包目录混淆与破坏安装"""
        pyproject_path = os.path.join(REPO_DIR, "pyproject.toml")
        self.assertTrue(os.path.exists(pyproject_path))
        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('name = "peer-agent"', content)
        self.assertIn('license = { text = "MIT" }', content)
        self.assertIn('packages = []', content)
        self.assertIn('script-files = ["bin/peer"]', content)

    def test_standalone_freeze_and_verify(self):
        """测试无需外部回执的独立方案冻结、交接语及防篡改校验功能"""
        proj = os.path.join(self.test_dir, "freeze_proj")
        os.makedirs(proj, exist_ok=True)
        plan_file = os.path.join(proj, "architecture_plan.md")
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write("# Plan V1\nLine 1\nLine 2\n")

        class FreezeArgs:
            cwd = proj
            plan = plan_file
            quote = "Approved by human test"
            review_receipt = ""

        # 执行独立冻结
        peer.cmd_freeze(FreezeArgs)

        # 检查冻结文件与交接语生成
        frozen_file = os.path.join(proj, "architecture_plan_冻结v001.md")
        handoff_file = os.path.join(proj, "architecture_plan_冻结v001_交接语.txt")
        self.assertTrue(os.path.exists(frozen_file))
        self.assertTrue(os.path.exists(handoff_file))
        with open(handoff_file, "r", encoding="utf-8") as f:
            handoff_content = f.read()
        self.assertIn("独立模式，未附外部终审回执", handoff_content)

        # 校验 verify 命令
        class VerifyArgs:
            frozen = frozen_file

        # 未被修改时 verify 正常通过
        peer.cmd_verify(VerifyArgs)

        # 篡改冻结文件，verify 必须抛出 SystemExit(6) 阻断执行
        with open(frozen_file, "a", encoding="utf-8") as f:
            f.write("tampered line\n")
        with self.assertRaises(SystemExit) as cm:
            peer.cmd_verify(VerifyArgs)
        self.assertEqual(cm.exception.code, 6)

    def test_snapshot_skips_git_worktree_file(self):
        """测试快照能正确忽略以普通文件存在的 .git（如 Git Worktree）"""
        proj = os.path.join(self.test_dir, "worktree_proj")
        os.makedirs(proj, exist_ok=True)
        with open(os.path.join(proj, ".git"), "w", encoding="utf-8") as f:
            f.write("gitdir: /some/path/to/worktree\n")
        with open(os.path.join(proj, "hello.txt"), "w", encoding="utf-8") as f:
            f.write("hello\n")
        snap_dir = os.path.join(proj, ".peer-review", "snap")
        entries = peer.snapshot(proj, snap_dir)["entries"]
        self.assertIn("hello.txt", entries)
        self.assertNotIn(".git", entries)

    def test_since_freeze_reanchors_when_project_moved(self):
        """测试项目移动/重命名后，since-freeze 能够自动重锚快照与项目根目录"""
        proj = os.path.join(self.test_dir, "orig_proj")
        os.makedirs(proj, exist_ok=True)
        plan_file = os.path.join(proj, "plan.md")
        with open(plan_file, "w", encoding="utf-8") as f:
            f.write("# Plan\nInitial\n")
        with open(os.path.join(proj, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('v1')\n")

        class FreezeArgs:
            cwd = proj
            plan = plan_file
            quote = ""
            review_receipt = ""

        peer.cmd_freeze(FreezeArgs)
        frozen_file = os.path.join(proj, "plan_冻结v001.md")
        self.assertTrue(os.path.exists(frozen_file))

        # 移动整个项目文件夹
        new_proj = os.path.join(self.test_dir, "moved_proj")
        shutil.move(proj, new_proj)
        new_frozen_file = os.path.join(new_proj, "plan_冻结v001.md")

        # 修改新项目下的文件
        with open(os.path.join(new_proj, "app.py"), "w", encoding="utf-8") as f:
            f.write("print('v2')\n")

        class SinceArgs:
            frozen = new_frozen_file
            cwd = None

        # 执行 since-freeze，不报错且能检测到改动
        peer.cmd_since_freeze(SinceArgs)
        # 验证新位置下生成了 changes 文件
        freeze_dir = os.path.join(new_proj, ".peer-review", "freeze")
        subdirs = [os.path.join(freeze_dir, d) for d in os.listdir(freeze_dir) if os.path.isdir(os.path.join(freeze_dir, d))]
        self.assertTrue(any(any(f.startswith("changes-") for f in os.listdir(d)) for d in subdirs))

    def test_oauth_token_auth_state(self):
        """测试 Claude Code 官方 oauth_token 登录态能够被正确识别为 subscription"""
        with patch.dict(os.environ, {}, clear=True), patch.object(peer, "run_quick", return_value=(0, '{"loggedIn": true, "authMethod": "oauth_token", "subscriptionType": "pro"}', "")):
            cat, desc = peer.auth_state(peer.DEFAULT_CONFIG, "claude")
            self.assertEqual(cat, "subscription")
            self.assertIn("oauth_token", desc)

    def test_claude_auth_detects_key_before_environment_filtering(self):
        """检测原始环境中的 Key，但不改变子进程的过滤策略或泄露凭证。"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only-key"}, clear=True):
            with patch.object(peer, "run_quick") as run:
                cat, desc = peer.auth_state(peer.DEFAULT_CONFIG, "claude")
            self.assertEqual(cat, "api")
            self.assertIn("将被忽略", desc)
            self.assertNotIn("test-only-key", desc)
            self.assertNotIn("ANTHROPIC_API_KEY", peer.child_env())
            run.assert_not_called()

    def test_codex_key_without_login_remains_unknown_with_guidance(self):
        """有 Key 但未登录时仍阻断，不以环境变量代替已确认的登录状态。"""
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "test-only-key"}, clear=True):
                with patch.object(peer, "run_quick", return_value=(1, "", "Not logged in")):
                    cat, desc = peer.auth_state(peer.DEFAULT_CONFIG, "codex")
                self.assertEqual(cat, "unknown")
                self.assertIn("先运行 codex login --with-api-key，再运行 peer doctor --approve", desc)
                self.assertNotIn("test-only-key", desc)

    def test_codex_known_login_categories_are_preserved(self):
        for status, expected in [("Logged in using ChatGPT", "subscription"),
                                 ("Logged in using an API key", "api")]:
            with self.subTest(status=status), patch.dict(os.environ, {}, clear=True):
                with patch.object(peer, "run_quick", return_value=(0, "", status)):
                    cat, _ = peer.auth_state(peer.DEFAULT_CONFIG, "codex")
                self.assertEqual(cat, expected)

    def test_doctor_does_not_approve_unknown_codex_key(self):
        """doctor 展示登录引导，--approve 不能批准 unknown 状态。"""
        cfg = json.loads(json.dumps(peer.DEFAULT_CONFIG))
        cfg["bins"] = {"codex": sys.executable, "claude": "/nonexistent/claude"}
        stops = {name: os.path.join(self.test_dir, name) for name in
                 ("STOP_LOCK_PATH", "STOP_CODEX_PATH", "STOP_CLAUDE_PATH", "IMAGE_COOLDOWN_PATH")}
        output = StringIO()
        args = type("DoctorArgs", (), {"approve": True})()
        with patch.dict(os.environ, {"CODEX_API_KEY": "test-only-key"}, clear=True), \
             patch.multiple(peer, **stops), \
             patch.object(peer, "load_config", return_value=cfg), \
             patch.object(peer, "run_quick", return_value=(1, "", "Not logged in")), \
             patch.object(peer, "resolve_model_effort", side_effect=peer.PeerError("test config")), \
             patch.object(peer, "save_config") as save, redirect_stdout(output):
            peer.cmd_doctor(args)
        self.assertIn("codex login --with-api-key", output.getvalue())
        self.assertIn("登录方式无法识别，未记录", output.getvalue())
        self.assertNotIn("test-only-key", output.getvalue())
        self.assertEqual(save.call_args.args[0]["approved_auth"]["codex"], "subscription")

    def test_linux_installer_profile_path_is_persistent_and_idempotent(self):
        """模拟 Linux：.bashrc 提前 return，登录配置仍持久化且重复运行不追加。"""
        with open(os.path.join(REPO_DIR, "install.sh"), encoding="utf-8") as f:
            source = f.read()
        function = source[source.index("configure_path_if_needed() {"):source.index('echo "==> 4.')]
        profile = os.path.join(self.test_dir, ".profile")
        bashrc = os.path.join(self.test_dir, ".bashrc")
        with open(bashrc, "w", encoding="utf-8") as f:
            f.write('case $- in *i*) ;; *) return;; esac\n')
        env = dict(os.environ, HOME=self.test_dir, SHELL="/bin/bash", PATH="/usr/bin:/bin")
        script = ('set -eu\nuname() { echo Linux; }\nLOCAL_BIN="$HOME/.local/bin"\n'
                  + function + '\nconfigure_path_if_needed\nconfigure_path_if_needed\n')
        res = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(profile, encoding="utf-8") as f:
            self.assertEqual(f.read().count('export PATH="$HOME/.local/bin:$PATH"'), 1)
        with open(bashrc, encoding="utf-8") as f:
            self.assertEqual(f.read().count('export PATH="$HOME/.local/bin:$PATH"'), 1)
        res = subprocess.run(["bash", "-c", '. "$HOME/.profile"; printf "%s" "$PATH"'],
                             env=env, capture_output=True, text=True, check=True)
        self.assertEqual(res.stdout.split(":")[0], os.path.join(self.test_dir, ".local/bin"))
        # 当前会话 PATH 已就绪也不能跳过 .profile 的持久化。
        other = os.path.join(self.test_dir, "new-home")
        os.makedirs(other)
        env.update(HOME=other, PATH=other + "/.local/bin:/usr/bin:/bin")
        res = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(os.path.join(other, ".profile"), encoding="utf-8") as f:
            self.assertEqual(f.read().count('export PATH="$HOME/.local/bin:$PATH"'), 1)

    def test_installer_old_python_guidance_matches_platform(self):
        """模拟 Python 3.9，分别检查 Linux 与 macOS 的提示及失败退出码。"""
        with open(os.path.join(REPO_DIR, "install.sh"), encoding="utf-8") as f:
            source = f.read()
        check = source[source.index('PY_VER='):source.index('echo "   Python 版本:')]
        stub = 'python3() { if [[ "$2" == *"print(1 if"* ]]; then echo 0; else echo 3.9; fi; }\n'
        for system in ("Linux", "Darwin"):
            with self.subTest(system=system):
                script = 'set -eu\nuname() { echo ' + system + '; }\n' + stub + check
                res = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
                self.assertEqual(res.returncode, 1, res.stderr)
                self.assertIn("3.9", res.stderr)
                if system == "Linux":
                    for tool in ("apt", "dnf", "pacman", "pyenv", "uv"):
                        self.assertIn(tool, res.stderr)
                    self.assertNotIn("brew", res.stderr)
                    self.assertNotIn("downloads/macos", res.stderr)
                else:
                    self.assertIn("brew install python", res.stderr)

    SKILL_HOSTILE_INPUTS = [
        # 多行：旧版注释行里的 $ARGUMENTS 被替换后，第二行起会逃逸成裸露命令
        "审阅下\ntouch {marker}",
        # 多行带括号：旧版会直接 syntax error near unexpected token '('
        "检查以下几点：\n1. 锁(竞争)\n2. 收尾(进程组) && touch {marker}",
        # 含旧版固定分隔符：旧版 heredoc 会被提前闭合
        "审阅\nPEER_ARGUMENTS_EOF_7f3a9c\ntouch {marker}\nPEER_ARGUMENTS_EOF_7f3a9c",
        # 命令替换、变量与各类引号
        "审阅 `touch {marker}` $(touch {marker}) $HOME \"q\" 'r'",
        # 代码围栏、heredoc 关键字与孤立引号
        "审阅\n```\nEOF\n' \" ) ; touch {marker}\n```",
    ]

    @staticmethod
    def skill_bash_blocks(content):
        """取出 SKILL.md 中全部 bash 代码块（去掉列表缩进）。"""
        blocks = re.findall(r"^   ```bash\n(.*?)\n   ```$", content, re.S | re.M)
        return ["\n".join(l[3:] if l.startswith("   ") else l for l in b.splitlines()) for b in blocks]

    def test_skill_arguments_never_inside_shell_code(self):
        """所有 SKILL.md 的代码块内都不得出现 $ARGUMENTS，也不再使用固定 heredoc 分隔符。"""
        for agent, target in (("antigravity", "claude"), ("antigravity", "codex"),
                              ("claude", "codex"), ("codex", "claude")):
            with self.subTest(skill="%s/%s" % (agent, target)):
                with open(os.path.join(REPO_DIR, "skills", agent, target, "SKILL.md"), encoding="utf-8") as f:
                    content = f.read()
                self.assertNotIn("PEER_ARGUMENTS_EOF", content)
                for block in re.findall(r"```.*?```", content, re.S):
                    self.assertNotIn("$ARGUMENTS", block)

    def test_claude_skill_full_text_substitution_is_injection_safe(self):
        """模拟 Claude Code 对整份 SKILL.md 做 $ARGUMENTS 文本替换：bash 语法必须通过、不执行任何注入，且意图解析正确。"""
        skill_file = os.path.join(REPO_DIR, "skills", "claude", "codex", "SKILL.md")
        with open(skill_file, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("  - Write", content.split("---")[1], "落盘依赖 Write 工具，必须在 allowed-tools 中声明")

        stub_bin = os.path.join(self.test_dir, "stubbin")
        os.makedirs(stub_bin)
        os.symlink(sys.executable, os.path.join(stub_bin, "python3"))
        stub_log = os.path.join(self.test_dir, "peer-calls.log")
        with open(os.path.join(stub_bin, "peer"), "w", encoding="utf-8") as f:
            f.write('#!/bin/sh\nprintf "%s\\n" "$@" >> "$PEER_STUB_LOG"\n'
                    '[ "$1" = ask ] && echo "运行编号：RUN-1"\nexit 0\n')
        os.chmod(os.path.join(stub_bin, "peer"), 0o755)
        env = {"HOME": self.test_dir, "PEER_HOME": os.path.join(self.test_dir, "peer-home"),
               "PATH": stub_bin + ":/usr/bin:/bin", "PEER_STUB_LOG": stub_log}

        for i, template in enumerate(self.SKILL_HOSTILE_INPUTS):
            marker = os.path.join(self.test_dir, "pwned-%d" % i)
            hostile = template.format(marker=marker)
            with self.subTest(case=i):
                blocks = self.skill_bash_blocks(content.replace("$ARGUMENTS", hostile))
                self.assertEqual(len(blocks), 2)
                for block in blocks:
                    res = subprocess.run(["bash", "-n", "-c", block], capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, res.stderr)

                workdir = os.path.join(self.test_dir, "proj-%d" % i)
                os.makedirs(workdir)
                res = subprocess.run(["bash", "-c", blocks[0]], cwd=workdir, env=env,
                                     capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr)
                req_file = re.search(r"^REQ_FILE=(.*)$", res.stdout, re.M).group(1)
                self.assertFalse(os.path.exists(req_file), "第一步只生成路径，不得创建文件")
                # 模拟第二步 Write 工具：参数原文经工具参数落盘，不经过任何 Shell
                with open(req_file, "w", encoding="utf-8") as f:
                    f.write("# 任务\n" + hostile + "\n")

                if os.path.exists(stub_log):
                    os.remove(stub_log)
                step3 = blocks[1].replace("__REQ_FILE__", req_file, 1)
                res = subprocess.run(["bash", "-c", step3], cwd=workdir, env=env,
                                     capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertFalse(os.path.exists(marker), "用户参数被当成 Shell 命令执行")
                with open(req_file, encoding="utf-8") as f:
                    self.assertEqual(f.read(), "# 任务\n" + hostile + "\n")
                with open(stub_log, encoding="utf-8") as f:
                    calls = f.read().splitlines()
                self.assertEqual(calls[:3], ["ask", "codex", "review"])
                self.assertIn(req_file, calls)
                self.assertIn("RUN-1", calls)  # wait 只针对 ask 返回的运行编号

        # 未替换占位符或路径不符时必须拒绝运行
        res = subprocess.run(["bash", "-c", self.skill_bash_blocks(content)[1]], cwd=self.test_dir, env=env,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 5)
        self.assertIn("REQ_FILE", res.stderr)

    def test_claude_skill_routing_review_verbs_beat_edit_words(self):
        """审阅类动词必须优先于修改类词，避免“审阅当前修改”被误升级为 exec"""
        cases = {"审阅当前修改": "review", "检查修复结果": "review", "review the fix": "review",
                 "不要修改，看看方案": "review", "修复登录问题": "exec", "实现导出功能": "exec",
                 "exec 修复 bug": "exec", "exec 只读检查": "review", "出个方案": "plan", "给个建议": "advice"}
        for text, expected in cases.items():
            with self.subTest(text=text):
                out = run_skill_router(text, self.test_dir).stdout
                self.assertEqual(json.loads(out)["kind"], expected)

    def test_claude_skill_spaced_negations_stay_readonly(self):
        """隔字否定必须保持只读，包括显式 exec 与英文否定。"""
        cases = [
            "不要对代码做任何修改，给个建议", "不许修改任何文件",
            "请勿对文件进行修改，只给建议", "不得对当前项目做任何修改",
            "无需对源码进行重构", "别对配置做任何编辑", "禁止对文件写入内容",
            "exec 不要对代码做任何修改", "exec 请勿对文件进行修改",
            "exec do not modify any files", "exec don't change the code",
            "exec without editing files", "exec never write files",
        ]
        for text in cases:
            with self.subTest(text=text):
                res = run_skill_router(text, self.test_dir)
                self.assertEqual(json.loads(res.stdout)["kind"], "review")
                self.assertIn("已按只读处理", res.stderr)

    def test_claude_skill_english_review_word_boundaries(self):
        """英文审阅词独立匹配，不把 checksum/preview 等误判为审阅。"""
        cases = {
            "实现 checksum 功能": "exec", "修复 preview 界面": "exec",
            "重构 different 模块": "exec", "实现 auditing 功能": "exec",
            "修复 inspection 模块": "exec", "修改 checklist": "exec",
            "REVIEW 当前修改": "review", "inspect 当前修改": "review",
            "audit 当前修改": "review", "diff 当前修改": "review",
            "check 当前修改": "review", "exec 修复 diff 显示错乱": "exec",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                res = run_skill_router(text, self.test_dir)
                self.assertEqual(json.loads(res.stdout)["kind"], expected)
                if expected == "review":
                    self.assertIn("已按只读处理", res.stderr)
                else:
                    self.assertEqual(res.stderr, "")

    def test_claude_readonly_sandbox_fails_closed(self):
        """Claude 只读沙箱不可用时必须直接失败，不得静默退回无沙箱"""
        with open(os.path.join(REPO_DIR, "bin", "peer"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('"failIfUnavailable": True', src)

    def test_doctor_exit_code_on_missing_tools(self):
        """测试当没有任何 CLI 工具可用时，doctor 命令必须以非零（2）退出码阻断"""
        from unittest.mock import patch
        class DoctorArgs:
            approve = False
        fake_cfg = dict(peer.DEFAULT_CONFIG)
        fake_cfg["bins"] = {"codex": "/nonexistent/codex", "claude": "/nonexistent/claude"}
        with patch.object(peer, "load_config", return_value=fake_cfg):
            with self.assertRaises(SystemExit) as cm:
                peer.cmd_doctor(DoctorArgs)
            self.assertEqual(cm.exception.code, 2)

    def test_cross_platform_fcntl_fallback(self):
        """测试在无 fcntl 支持平台（如 Windows 原生环境）时的优雅降级"""
        jsonl_path = os.path.join(self.test_dir, "test.jsonl")
        with patch.object(peer, "fcntl", None):
            peer.append_jsonl(jsonl_path, {"test": 123})
            with open(jsonl_path, "r", encoding="utf-8") as f:
                data = json.loads(f.readline())
            self.assertEqual(data.get("test"), 123)

            # 测试 ImageGlobalLock 在无 fcntl 时优雅降级不报错（锁文件指向临时目录，不依赖真实 ~/.peer-review）
            lock_dir = os.path.join(self.test_dir, "fresh-home", ".peer-review")
            with patch.object(peer, "IMAGE_LOCK_PATH", os.path.join(lock_dir, "image.lock")), \
                 patch.object(peer, "IMAGE_COOLDOWN_PATH", os.path.join(lock_dir, "last_image_time.json")):
                with peer.ImageGlobalLock("run_mock_win"):
                    self.assertTrue(True)


class TestHardeningFixes(unittest.TestCase):
    """覆盖本轮加固：计费 key 隔离、认证探测、生图锁目录、安装器路径/退出码/软链接备份/提示。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.test_dir = tmp.name

    # ---------------------------------------------------------- bin/peer
    def test_child_env_strips_billing_api_keys(self):
        base = {"PATH": "/bin", "OPENAI_API_KEY": "k1", "CODEX_API_KEY": "k2",
                "ANTHROPIC_API_KEY": "k3", "OPENAI_BASE_URL": "https://example.invalid"}
        env = peer.child_env(base)
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY"):
            self.assertNotIn(key, env)
        self.assertEqual(env["PATH"], "/bin")
        self.assertEqual(env["OPENAI_BASE_URL"], "https://example.invalid")

    def test_codex_auth_requires_zero_exit_code(self):
        for status in ("Logged in using ChatGPT", "Logged in using an API key"):
            with self.subTest(status=status), patch.dict(os.environ, {}, clear=True):
                with patch.object(peer, "run_quick", return_value=(1, "", status)):
                    cat, _ = peer.auth_state(peer.DEFAULT_CONFIG, "codex")
                self.assertEqual(cat, "unknown")

    def test_codex_auth_rejects_negative_or_partial_phrases(self):
        for status in ("Not logged in to ChatGPT", "Error: login with ChatGPT failed",
                       "Not logged in. Run codex login --with-api-key", "chatgpt api",
                       "You are not Logged in using ChatGPT"):
            with self.subTest(status=status), patch.dict(os.environ, {}, clear=True):
                with patch.object(peer, "run_quick", return_value=(0, status, "")):
                    cat, _ = peer.auth_state(peer.DEFAULT_CONFIG, "codex")
                self.assertEqual(cat, "unknown")

    def test_codex_auth_accepts_full_phrase_with_suffix(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(peer, "run_quick", return_value=(0, "Logged in using an API key - sk-***\n", "")):
            cat, _ = peer.auth_state(peer.DEFAULT_CONFIG, "codex")
        self.assertEqual(cat, "api")

    def test_claude_auth_requires_zero_exit_and_json_object(self):
        ok_json = '{"loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "pro"}'
        for code, out in [(1, ok_json), (0, "[1, 2]"), (0, "not json"),
                          (0, '{"loggedIn": "yes", "authMethod": "claude.ai"}')]:
            with self.subTest(code=code, out=out), patch.dict(os.environ, {}, clear=True):
                with patch.object(peer, "run_quick", return_value=(code, out, "")):
                    cat, _ = peer.auth_state(peer.DEFAULT_CONFIG, "claude")
                self.assertEqual(cat, "unknown")
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(peer, "run_quick", return_value=(0, ok_json, "")):
            self.assertEqual(peer.auth_state(peer.DEFAULT_CONFIG, "claude")[0], "subscription")

    def test_image_lock_creates_missing_parent_dir(self):
        lock_dir = os.path.join(self.test_dir, "not", "yet", "created")
        with patch.object(peer, "IMAGE_LOCK_PATH", os.path.join(lock_dir, "image.lock")), \
             patch.object(peer, "IMAGE_COOLDOWN_PATH", os.path.join(lock_dir, "last_image_time.json")):
            with peer.ImageGlobalLock("run_mock_dir"):
                self.assertTrue(os.path.exists(os.path.join(lock_dir, "image.lock")))

    def test_terminate_child_uses_process_group_on_posix(self):
        """进程组号直接取 child.pid，不调用 os.getpgid（直接子进程已回收时它会报 ESRCH）。"""
        child = Mock(pid=4321)
        with patch.object(peer.os, "killpg", create=True) as killpg, \
             patch.object(peer.os, "getpgid", create=True,
                          side_effect=ProcessLookupError(3, "No such process")) as getpgid, \
             patch.object(peer.time, "sleep") as sleep:
            peer.terminate_child(child, 5)
        sigkill = getattr(peer.signal, "SIGKILL", peer.signal.SIGTERM)
        self.assertEqual([c.args for c in killpg.call_args_list],
                         [(4321, peer.signal.SIGTERM), (4321, sigkill)])
        sleep.assert_called_once_with(5)
        getpgid.assert_not_called()
        child.terminate.assert_not_called()

    def test_terminate_child_skips_wait_when_group_already_gone(self):
        child = Mock(pid=4321)
        with patch.object(peer.os, "killpg", create=True,
                          side_effect=ProcessLookupError(3, "No such process")) as killpg, \
             patch.object(peer.time, "sleep") as sleep:
            peer.terminate_child(child, 5)
        self.assertEqual(killpg.call_count, 1)
        sleep.assert_not_called()
        child.terminate.assert_not_called()

    def test_terminate_child_falls_back_without_killpg(self):
        """模拟 Windows 原生：os 模块没有 killpg / getpgid 时改用 terminate / kill，不抛 AttributeError。"""
        for exited in (True, False):
            with self.subTest(exited=exited):
                child = Mock(pid=4321)
                if not exited:
                    child.wait.side_effect = subprocess.TimeoutExpired("x", 5)
                with patch.object(peer, "os") as fake_os:
                    del fake_os.killpg
                    del fake_os.getpgid
                    peer.terminate_child(child, 5)
                child.terminate.assert_called_once_with()
                child.wait.assert_called_once_with(timeout=5)
                if exited:
                    child.kill.assert_not_called()
                else:
                    child.kill.assert_called_once_with()

    def test_terminate_child_really_stops_a_process(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                 start_new_session=True)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        peer.terminate_child(child, 0.2)
        self.assertIsNotNone(child.wait(timeout=10))

    @staticmethod
    def pid_alive(pid):
        """进程仍在运行返回 True；已不存在或只剩僵尸（容器内 PID 1 未必回收）返回 False。"""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            with open("/proc/%d/stat" % pid, encoding="utf-8") as f:
                return f.read().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            pass
        res = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
        return res.returncode == 0 and not res.stdout.strip().startswith("Z")

    @unittest.skipUnless(hasattr(os, "killpg"), "需要 POSIX 进程组")
    def test_terminate_child_kills_grandchild_after_direct_child_reaped(self):
        """直接子进程先退出并被回收后，仍要按进程组杀掉它留下的孙进程。"""
        child = subprocess.Popen(["sh", "-c", "sleep 30 >/dev/null 2>&1 & echo $!"],
                                 stdout=subprocess.PIPE, text=True, start_new_session=True)
        grandchild = int(child.stdout.readline())
        child.stdout.close()

        def kill_grandchild():
            try:
                os.kill(grandchild, signal.SIGKILL)
            except OSError:
                pass
        self.addCleanup(kill_grandchild)

        child.wait(timeout=10)
        self.assertTrue(self.pid_alive(grandchild))
        with self.assertRaises(ProcessLookupError):
            os.getpgid(child.pid)  # 旧实现正是在这里失败而漏杀孙进程
        peer.terminate_child(child, 0.2)
        deadline = time.time() + 5
        while self.pid_alive(grandchild) and time.time() < deadline:
            time.sleep(0.05)
        self.assertFalse(self.pid_alive(grandchild), "孙进程未被进程组清理杀掉")

    # ---------------------------------------------------------- install.sh
    def make_repo(self, doctor_rc=0):
        """在临时目录复制一份安装所需文件，并把 bin/peer 换成按指定退出码返回的 doctor 桩。"""
        repo = os.path.join(self.test_dir, "repo")
        os.makedirs(os.path.join(repo, "bin"))
        for name in ("install.sh", "config.example.json"):
            shutil.copy2(os.path.join(REPO_DIR, name), os.path.join(repo, name))
        for name in ("templates", "skills"):
            shutil.copytree(os.path.join(REPO_DIR, name), os.path.join(repo, name))
        stub = os.path.join(repo, "bin", "peer")
        with open(stub, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho doctor-stub\nexit %d\n" % doctor_rc)
        os.chmod(stub, 0o755)
        return repo

    def run_installer(self, repo, *args, peer_home=None, home=None):
        """home 显式传入时按原样使用、不预先创建（用于验证含 .. 的路径）。"""
        if home is None:
            home = os.path.join(self.test_dir, "home")
            os.makedirs(home, exist_ok=True)
        tool_bin = os.path.join(self.test_dir, "toolbin")
        os.makedirs(tool_bin, exist_ok=True)
        py = os.path.join(tool_bin, "python3")
        if not os.path.exists(py):
            os.symlink(sys.executable, py)
        env = {"HOME": home, "SHELL": "/bin/bash", "PATH": tool_bin + ":/usr/bin:/bin",
               "PEER_HOME": peer_home or os.path.join(home, ".peer-review")}
        res = subprocess.run(["bash", os.path.join(repo, "install.sh")] + list(args),
                             env=env, capture_output=True, text=True, cwd=repo)
        return res, home

    def test_installer_refuses_peer_home_equal_to_repo(self):
        for mode in ("--copy", "--link", "--uninstall"):
            with self.subTest(mode=mode):
                repo = self.make_repo()
                src = os.path.join(repo, "bin", "peer")
                with open(src, encoding="utf-8") as f:
                    before = f.read()
                res, _ = self.run_installer(repo, mode, peer_home=repo)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("已安全终止", res.stderr)
                self.assertFalse(os.path.islink(src))
                with open(src, encoding="utf-8") as f:
                    self.assertEqual(f.read(), before)
                for t in os.listdir(os.path.join(repo, "templates")):
                    self.assertFalse(os.path.islink(os.path.join(repo, "templates", t)))
                shutil.rmtree(repo)

    def assert_repo_untouched(self, repo, before):
        src = os.path.join(repo, "bin", "peer")
        self.assertFalse(os.path.islink(src))
        with open(src, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        for t in os.listdir(os.path.join(repo, "templates")):
            self.assertFalse(os.path.islink(os.path.join(repo, "templates", t)))
        self.assertFalse(os.path.exists(os.path.join(repo, "config.json")))

    def test_installer_refuses_peer_home_with_dotdot_segment(self):
        """PEER_HOME=repo/nope/..：nope 不存在时旧版 canon_path 拼不回 repo，会放行并删掉仓库 bin/peer。"""
        for mode in ("--copy", "--link", "--uninstall"):
            with self.subTest(mode=mode):
                repo = self.make_repo()
                with open(os.path.join(repo, "bin", "peer"), encoding="utf-8") as f:
                    before = f.read()
                res, _ = self.run_installer(repo, mode, peer_home=os.path.join(repo, "nope", ".."))
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn("已安全终止", res.stderr)
                self.assertFalse(os.path.exists(os.path.join(repo, "nope")))
                self.assert_repo_untouched(repo, before)
                shutil.rmtree(repo)

    def test_installer_canon_path_rejects_unresolvable_dotdot(self):
        """即便 PEER_HOME 合法，其他目标路径含“不存在目录 + ..”时 canon_path 也必须阻断而非放行。"""
        repo = self.make_repo()
        with open(os.path.join(repo, "bin", "peer"), encoding="utf-8") as f:
            before = f.read()
        os.makedirs(os.path.join(self.test_dir, "home"))
        home = os.path.join(self.test_dir, "home", "nope", "..")
        res, _ = self.run_installer(repo, "--copy", home=home,
                                    peer_home=os.path.join(self.test_dir, "ph"))
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("无法规范化路径", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "home", "nope")))
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "ph")))
        self.assert_repo_untouched(repo, before)

    def test_installer_uninstall_keeps_foreign_files(self):
        """卸载只删本工具装的文件：同名技能、名字含 peer 的外来软链接、他人的 ~/.local/bin/peer 一律保留。"""
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        other = os.path.join(self.test_dir, "other-peer-tools", "SKILL.md")
        os.makedirs(os.path.dirname(other))
        with open(other, "w", encoding="utf-8") as f:
            f.write("someone else's skill\n")
        claude_skill = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
        codex_link = os.path.join(home, ".codex", "skills", "claude", "SKILL.md")
        local_peer = os.path.join(home, ".local", "bin", "peer")
        old_ours = os.path.join(home, ".agents", "skills", "claude", "SKILL.md")
        for p in (claude_skill, codex_link, local_peer, old_ours):
            os.makedirs(os.path.dirname(p))
        with open(claude_skill, "w", encoding="utf-8") as f:
            f.write("my own skill, mentions $PEER_HOME\n")
        os.symlink(other, codex_link)
        with open(local_peer, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho mine\n")
        with open(old_ours, "w", encoding="utf-8") as f:
            f.write("---\nname: claude\n---\n<!-- managed-by: peer-agent -->\nolder version\n")

        res, _ = self.run_installer(repo, "--uninstall")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        with open(claude_skill, encoding="utf-8") as f:
            self.assertEqual(f.read(), "my own skill, mentions $PEER_HOME\n")
        self.assertEqual(os.readlink(codex_link), other)
        with open(local_peer, encoding="utf-8") as f:
            self.assertEqual(f.read(), "#!/bin/sh\necho mine\n")
        self.assertFalse(os.path.exists(old_ours))
        for p in (claude_skill, codex_link, local_peer):
            self.assertIn(p, res.stdout)

    def test_installer_uninstall_removes_own_files_in_both_modes(self):
        for mode in ("--copy", "--link"):
            with self.subTest(mode=mode):
                repo = self.make_repo()
                res, home = self.run_installer(repo, mode)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                local_peer = os.path.join(home, ".local", "bin", "peer")
                skill = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
                self.assertTrue(os.path.lexists(local_peer))
                self.assertTrue(os.path.lexists(skill))
                res, _ = self.run_installer(repo, "--uninstall")
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertFalse(os.path.lexists(local_peer))
                self.assertFalse(os.path.lexists(skill))
                self.assertNotIn("跳过", res.stdout)
                shutil.rmtree(repo)
                shutil.rmtree(home)

    def test_skill_files_carry_managed_marker(self):
        for agent, target in (("antigravity", "claude"), ("antigravity", "codex"),
                              ("claude", "codex"), ("codex", "claude")):
            with self.subTest(skill="%s/%s" % (agent, target)):
                with open(os.path.join(REPO_DIR, "skills", agent, target, "SKILL.md"), encoding="utf-8") as f:
                    content = f.read()
                self.assertTrue(content.startswith("---\n"), "frontmatter 必须仍在首行")
                self.assertIn("<!-- managed-by: peer-agent -->", content)

    def test_installer_refuses_non_directory_target_before_writing(self):
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        os.makedirs(home)
        with open(os.path.join(home, ".agents"), "w", encoding="utf-8") as f:
            f.write("not a directory\n")
        res, _ = self.run_installer(repo)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("不是目录", res.stderr)
        self.assertFalse(os.path.exists(os.path.join(home, ".peer-review")))
        self.assertFalse(os.path.exists(os.path.join(home, ".claude")))
        self.assertFalse(os.path.exists(os.path.join(home, ".local")))

    def test_installer_restores_backup_when_skill_copy_fails(self):
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        dst = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
        os.makedirs(os.path.dirname(dst))
        with open(dst, "w", encoding="utf-8") as f:
            f.write("user skill\n")
        tool_bin = os.path.join(self.test_dir, "toolbin")
        os.makedirs(tool_bin)
        fake_cp = os.path.join(tool_bin, "cp")
        with open(fake_cp, "w", encoding="utf-8") as f:
            f.write('#!/bin/sh\nfor a; do last="$a"; done\n'
                    'case "$last" in */.claude/skills/codex/SKILL.md*) echo "cp: simulated failure" >&2; exit 1 ;; esac\n'
                    'exec /bin/cp "$@"\n')
        os.chmod(fake_cp, 0o755)

        res, _ = self.run_installer(repo)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("技能写入失败", res.stderr)
        self.assertIn("已还原原有技能文件", res.stderr)
        with open(dst, encoding="utf-8") as f:
            self.assertEqual(f.read(), "user skill\n")
        self.assertEqual([n for n in os.listdir(os.path.dirname(dst)) if ".bak_" in n], [])

    def test_installer_refuses_peer_home_symlinked_to_repo(self):
        repo = self.make_repo()
        alias = os.path.join(self.test_dir, "alias")
        os.symlink(repo, alias)
        res, _ = self.run_installer(repo, "--copy", peer_home=alias)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertTrue(os.path.isfile(os.path.join(repo, "bin", "peer")))

    def test_installer_propagates_doctor_exit_code(self):
        for rc in (0, 2, 3):
            with self.subTest(rc=rc):
                repo = self.make_repo(doctor_rc=rc)
                res, home = self.run_installer(repo)
                self.assertEqual(res.returncode, rc, res.stdout + res.stderr)
                self.assertIn("doctor-stub", res.stdout)
                if rc == 3:
                    self.assertIn("熔断停机锁", res.stdout)
                elif rc:
                    self.assertIn("退出码 %d" % rc, res.stdout)
                shutil.rmtree(repo)
                shutil.rmtree(home)

    def test_installer_claude_hint_prefers_native_install(self):
        repo = self.make_repo()
        res, _ = self.run_installer(repo)
        out = res.stdout
        native = "curl -fsSL https://claude.ai/install.sh | bash"
        self.assertIn(native, out)
        self.assertIn("brew install --cask claude-code", out)
        # 每一处 npm 备选都必须排在原生安装命令之后
        npm = "npm install -g @anthropic-ai/claude-code"
        pos = 0
        while True:
            idx = out.find(npm, pos)
            if idx < 0:
                break
            self.assertGreater(idx, out.rfind(native, 0, idx), "npm 不能先于原生安装出现")
            self.assertGreaterEqual(out.rfind(native, 0, idx), 0)
            pos = idx + 1

    def test_installer_backs_up_foreign_skill_symlink_and_restores_it(self):
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        foreign = os.path.join(self.test_dir, "my-own-skill.md")
        with open(foreign, "w", encoding="utf-8") as f:
            f.write("user skill\n")
        dst = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
        os.makedirs(os.path.dirname(dst))
        os.symlink(foreign, dst)

        res, _ = self.run_installer(repo)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("原指向: %s" % foreign, res.stdout)
        baks = [n for n in os.listdir(os.path.dirname(dst)) if n.startswith("SKILL.md.bak_")]
        self.assertEqual(len(baks), 1)
        bak = os.path.join(os.path.dirname(dst), baks[0])
        self.assertTrue(os.path.islink(bak))
        self.assertEqual(os.readlink(bak), foreign)
        self.assertFalse(os.path.islink(dst))

        res, _ = self.run_installer(repo, "--uninstall")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.islink(dst))
        self.assertEqual(os.readlink(dst), foreign)
        with open(foreign, encoding="utf-8") as f:
            self.assertEqual(f.read(), "user skill\n")

    def test_installer_link_reinstall_does_not_back_up_own_link(self):
        repo = self.make_repo()
        for _ in range(2):
            res, home = self.run_installer(repo, "--link")
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        skill_dir = os.path.join(home, ".claude", "skills", "codex")
        self.assertEqual([n for n in os.listdir(skill_dir) if ".bak_" in n], [])
        self.assertEqual(os.readlink(os.path.join(skill_dir, "SKILL.md")),
                         os.path.join(repo, "skills", "claude", "codex", "SKILL.md"))

    def test_installer_codex_skill_installs_to_both_dirs_and_uninstalls(self):
        repo = self.make_repo()
        src = os.path.join(repo, "skills", "codex", "claude", "SKILL.md")
        res, home = self.run_installer(repo)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        dsts = [os.path.join(home, d, "skills", "claude", "SKILL.md") for d in (".codex", ".agents")]
        for dst in dsts:
            with self.subTest(dst=dst):
                self.assertTrue(os.path.isfile(dst))
                with open(src, encoding="utf-8") as a, open(dst, encoding="utf-8") as b:
                    self.assertEqual(a.read(), b.read())

        res, _ = self.run_installer(repo, "--uninstall")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        for dst in dsts:
            with self.subTest(dst=dst):
                self.assertFalse(os.path.exists(dst))

    def test_installer_backs_up_foreign_local_peer_and_restores_on_uninstall(self):
        """$LOCAL_BIN/peer 若是第三方同名工具：两种模式安装时都先备份，卸载时还原保留。"""
        for mode in ("--copy", "--link"):
            with self.subTest(mode=mode):
                repo = self.make_repo()
                home = os.path.join(self.test_dir, "home")
                foreign = "#!/bin/sh\necho third-party peer\n"
                local_peer = os.path.join(home, ".local", "bin", "peer")
                home_peer = os.path.join(home, ".peer-review", "bin", "peer")
                for path in (local_peer, home_peer):
                    os.makedirs(os.path.dirname(path))
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(foreign)

                res, _ = self.run_installer(repo, mode)
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                for path in (local_peer, home_peer):
                    baks = [n for n in os.listdir(os.path.dirname(path)) if n.startswith("peer.bak_")]
                    self.assertEqual(len(baks), 1, os.listdir(os.path.dirname(path)))
                    with open(os.path.join(os.path.dirname(path), baks[0]), encoding="utf-8") as f:
                        self.assertEqual(f.read(), foreign)
                    self.assertEqual([n for n in os.listdir(os.path.dirname(path)) if ".tmp." in n], [])
                with open(local_peer, encoding="utf-8") as f:
                    self.assertIn("doctor-stub", f.read())
                self.assertTrue(os.access(local_peer, os.X_OK))

                res, _ = self.run_installer(repo, "--uninstall")
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                for path in (local_peer, home_peer):
                    self.assertFalse(os.path.islink(path))
                    with open(path, encoding="utf-8") as f:
                        self.assertEqual(f.read(), foreign)
                    self.assertEqual([n for n in os.listdir(os.path.dirname(path)) if ".bak_" in n], [])
                shutil.rmtree(repo)
                shutil.rmtree(home)

    def test_installer_copy_over_previous_link_never_writes_through_to_repo(self):
        """先 --link 再 --copy：必须替换链接本身，不能透过链接改写仓库源文件，也不产生备份。"""
        repo = self.make_repo()
        src = os.path.join(repo, "bin", "peer")
        with open(src, encoding="utf-8") as f:
            before = f.read()
        res, home = self.run_installer(repo, "--link")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        res, _ = self.run_installer(repo, "--copy")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        local_peer = os.path.join(home, ".local", "bin", "peer")
        self.assertFalse(os.path.islink(local_peer))
        self.assertFalse(os.path.islink(src))
        with open(src, encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        for d in (os.path.dirname(local_peer), os.path.join(home, ".claude", "skills", "codex")):
            self.assertEqual([n for n in os.listdir(d) if ".bak_" in n or ".tmp." in n], [])

    def test_installer_upgrade_replaces_managed_skill_without_backup(self):
        """升级：已带 managed-by 标记的旧版技能直接替换，不产生 .bak；卸载只还原原始用户备份。"""
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        dst = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
        os.makedirs(os.path.dirname(dst))
        with open(dst, "w", encoding="utf-8") as f:
            f.write("user original skill\n")
        res, _ = self.run_installer(repo)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        skill_dir = os.path.dirname(dst)
        self.assertEqual(len([n for n in os.listdir(skill_dir) if ".bak_" in n]), 1)

        # 模拟已安装的是旧版 PeerAgent 技能（内容不同但带标记），再次安装
        with open(dst, "w", encoding="utf-8") as f:
            f.write("---\nname: codex\n---\n<!-- managed-by: peer-agent -->\nolder version\n")
        res, _ = self.run_installer(repo)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len([n for n in os.listdir(skill_dir) if ".bak_" in n]), 1)
        # 历史版本遗留的受管理备份（时间戳更新）不得被当成原始文件还原
        legacy = dst + ".bak_29991231235959"
        with open(legacy, "w", encoding="utf-8") as f:
            f.write("<!-- managed-by: peer-agent -->\nlegacy managed backup\n")

        res, _ = self.run_installer(repo, "--uninstall")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        with open(dst, encoding="utf-8") as f:
            self.assertEqual(f.read(), "user original skill\n")
        self.assertTrue(os.path.exists(legacy), "受管理的旧备份只是不还原，不做删除")

    def test_installer_uninstall_canonicalizes_symlink_target(self):
        """软链接指向 repo/../thirdparty 时，规范化后不在仓库内，卸载必须保留。"""
        repo = self.make_repo()
        home = os.path.join(self.test_dir, "home")
        third = os.path.join(self.test_dir, "thirdparty", "SKILL.md")
        os.makedirs(os.path.dirname(third))
        with open(third, "w", encoding="utf-8") as f:
            f.write("third-party skill\n")
        dst = os.path.join(home, ".claude", "skills", "codex", "SKILL.md")
        os.makedirs(os.path.dirname(dst))
        sneaky = os.path.join(repo, "..", "thirdparty", "SKILL.md")
        os.symlink(sneaky, dst)
        res, _ = self.run_installer(repo, "--uninstall")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(os.path.islink(dst))
        self.assertEqual(os.readlink(dst), sneaky)
        self.assertIn("跳过", res.stdout)

    def test_installer_preflight_checks_peer_home_subdirs_and_targets(self):
        """$PEER_HOME/bin 被文件占用、或目标文件被目录占用时，写入前就终止。"""
        cases = {
            "bin-is-file": (os.path.join(".peer-review", "bin"), "file", "不是目录"),
            "templates-is-file": (os.path.join(".peer-review", "templates"), "file", "不是目录"),
            "target-is-dir": (os.path.join(".local", "bin", "peer"), "dir", "是目录"),
        }
        for name, (rel, kind, msg) in cases.items():
            with self.subTest(case=name):
                repo = self.make_repo()
                home = os.path.join(self.test_dir, "home")
                path = os.path.join(home, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if kind == "file":
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("occupied\n")
                else:
                    os.makedirs(path)
                res, _ = self.run_installer(repo)
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(msg, res.stderr)
                self.assertFalse(os.path.exists(os.path.join(home, ".claude")))
                self.assertFalse(os.path.exists(os.path.join(home, ".peer-review", "config.json")))
                shutil.rmtree(repo)
                shutil.rmtree(home)


class TestWriteLockAndLifecycle(unittest.TestCase):
    """可写锁原子发布 / 残缺锁宽限 / 并发互斥，以及调度器收尾顺序。"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.join(tmp.name, "proj")
        os.makedirs(os.path.join(self.root, ".peer-review", "runs"))
        self.lock = peer.write_lock_path(self.root)

    def lock_run_id(self):
        with open(self.lock, encoding="utf-8") as f:
            return json.load(f)["run_id"]

    def dead_pid(self):
        p = subprocess.Popen(["true"])
        p.wait()
        return p.pid

    def assert_no_leftovers(self):
        names = os.listdir(os.path.dirname(self.lock))
        self.assertEqual([n for n in names if ".tmp." in n or ".stale." in n or n.endswith(".reclaim")], [], names)

    def test_lock_file_is_never_empty_after_acquire(self):
        self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_A"))
        self.assertEqual(self.lock_run_id(), "RUN_A")
        self.assertIn("RUN_A", peer.acquire_write_lock(self.root, "RUN_B"))
        self.assertEqual(self.lock_run_id(), "RUN_A")
        self.assert_no_leftovers()

    def test_fresh_empty_or_corrupt_lock_gets_grace_period(self):
        """空文件 / 残缺 JSON 可能正被写入：30 秒内绝不判死亡、绝不删除。"""
        for content in ("", "{\"run_id\": \"RUN_A\", \"pi"):
            with self.subTest(content=content):
                with open(self.lock, "w", encoding="utf-8") as f:
                    f.write(content)
                err = peer.acquire_write_lock(self.root, "RUN_B")
                self.assertIsNotNone(err)
                with open(self.lock, encoding="utf-8") as f:
                    self.assertEqual(f.read(), content)
                os.remove(self.lock)

    def test_old_empty_lock_is_reclaimed_after_grace(self):
        with open(self.lock, "w", encoding="utf-8"):
            pass
        old = time.time() - peer.WRITE_LOCK_GRACE_SECONDS - 5
        os.utime(self.lock, (old, old))
        self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_B"))
        self.assertEqual(self.lock_run_id(), "RUN_B")
        self.assert_no_leftovers()

    def test_stale_lock_of_dead_owner_is_reclaimed_but_recent_one_is_kept(self):
        dead = self.dead_pid()
        with open(self.lock, "w", encoding="utf-8") as f:
            json.dump({"run_id": "RUN_OLD", "pid": dead, "created_ts": time.time()}, f)
        self.assertIsNotNone(peer.acquire_write_lock(self.root, "RUN_B"), "启动宽限期内不得回收")
        with open(self.lock, "w", encoding="utf-8") as f:
            json.dump({"run_id": "RUN_OLD", "pid": dead, "created_ts": time.time() - 120}, f)
        self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_B"))
        self.assertEqual(self.lock_run_id(), "RUN_B")

    def test_reclaim_puts_back_a_lock_that_changed_after_judgement(self):
        """判定陈旧之后锁被并发新进程替换：回收时核对 run_id/inode 不符，必须原样放回。"""
        with open(self.lock, "w", encoding="utf-8") as f:
            json.dump({"run_id": "RUN_OLD"}, f)
        old_ino = os.stat(self.lock).st_ino
        os.remove(self.lock)
        self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_NEW"))
        peer._reclaim_write_lock(self.lock, "RUN_OLD", old_ino)
        self.assertEqual(self.lock_run_id(), "RUN_NEW")
        self.assert_no_leftovers()

    def test_release_only_removes_own_lock(self):
        self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_A"))
        peer.release_write_lock(self.root, "RUN_OTHER")
        self.assertEqual(self.lock_run_id(), "RUN_A")
        peer.release_write_lock(self.root, "RUN_A")
        self.assertFalse(os.path.exists(self.lock))

    def test_fallback_without_hard_links_still_excludes(self):
        with patch.object(peer.os, "link", side_effect=PermissionError("no hard links")):
            self.assertIsNone(peer.acquire_write_lock(self.root, "RUN_A"))
            self.assertEqual(self.lock_run_id(), "RUN_A")
            self.assertIsNotNone(peer.acquire_write_lock(self.root, "RUN_B"))
        self.assert_no_leftovers()

    def run_concurrent(self, n, use_guard):
        import threading
        barrier = threading.Barrier(n)
        results = []

        def worker(i):
            barrier.wait()
            results.append(peer.acquire_write_lock(self.root, "RUN_%d" % i))
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        ctx = patch.object(peer, "fcntl", None) if not use_guard else patch.object(peer, "fcntl", peer.fcntl)
        with ctx:
            for th in threads:
                th.start()
            for th in threads:
                th.join(10)
        return results

    def test_concurrent_acquire_admits_exactly_one(self):
        """并发抢锁（含残缺陈旧锁待回收的场景）绝不穿透：恰好一个成功，锁归属于成功者。"""
        for use_guard in (True, False):
            for preset in ("none", "stale-empty"):
                with self.subTest(guard=use_guard, preset=preset):
                    if os.path.exists(self.lock):
                        os.remove(self.lock)
                    if preset == "stale-empty":
                        with open(self.lock, "w", encoding="utf-8"):
                            pass
                        old = time.time() - 120
                        os.utime(self.lock, (old, old))
                    results = self.run_concurrent(12, use_guard)
                    winners = [i for i, r in enumerate(results) if r is None]
                    self.assertEqual(len(winners), 1, results)
                    self.assertTrue(self.lock_run_id().startswith("RUN_"))
                    self.assert_no_leftovers()

    def test_concurrent_acquire_across_processes(self):
        script = ("import sys\nfrom importlib.machinery import SourceFileLoader\n"
                  "import importlib.util\n"
                  "l = SourceFileLoader('peer', sys.argv[1]); s = importlib.util.spec_from_loader('peer', l)\n"
                  "m = importlib.util.module_from_spec(s); l.exec_module(m)\n"
                  "import time\nwhile time.time() < float(sys.argv[3]): pass\n"
                  "print('OK' if m.acquire_write_lock(sys.argv[2], 'P%s' % sys.argv[4]) is None else 'BUSY')\n")
        start_at = str(time.time() + 1.5)
        procs = [subprocess.Popen([sys.executable, "-c", script, peer_bin_path, self.root, start_at, str(i)],
                                  stdout=subprocess.PIPE, text=True) for i in range(8)]
        outs = [p.communicate(timeout=30)[0].strip() for p in procs]
        self.assertEqual(outs.count("OK"), 1, outs)
        self.assert_no_leftovers()

    # ---------------------------------------------------------- 调度器收尾
    def make_run(self, run_id, args, mode="read"):
        rdir = os.path.join(self.root, ".peer-review", "runs", run_id)
        os.makedirs(rdir)
        meta = {"run_id": run_id, "root": self.root, "cwd": self.root, "agent": "claude",
                "kind": "exec" if mode == "write" else "review", "mode": mode, "args": args,
                "timeout_minutes": 1, "auth": {"category": "subscription", "desc": "test"}}
        with open(os.path.join(rdir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        if mode == "write":
            peer.snapshot(self.root, os.path.join(rdir, "snapshot"))
            self.assertIsNone(peer.acquire_write_lock(self.root, run_id))
        return rdir

    def run_dispatcher(self, rdir):
        saved = {}
        for name in ("SIGTERM", "SIGINT", "SIGHUP"):
            sig = getattr(signal, name, None)
            if sig is not None:
                saved[sig] = signal.getsignal(sig)
        try:
            with patch.object(peer, "GLOBAL_LOG", os.path.join(self.root, "global.jsonl")), \
                 patch.object(peer, "get_active_stop_lock", return_value=(None, None)):
                peer.cmd_run(rdir)
        finally:
            for sig, handler in saved.items():
                signal.signal(sig, handler)

    @unittest.skipUnless(hasattr(os, "killpg"), "需要 POSIX 进程组")
    def test_dispatcher_cleans_process_group_on_normal_exit(self):
        """直接子进程正常退出后，调度器仍须清理其后台孙进程。"""
        pidfile = os.path.join(self.root, "grandchild.pid")
        rdir = self.make_run("RUN_NORMAL", ["sh", "-c", "sleep 30 >/dev/null 2>&1 & echo $! > '%s'; exit 0" % pidfile])
        calls = []
        real = peer.terminate_child

        def spy(child, grace):
            calls.append(grace)
            return real(child, grace)
        with patch.object(peer, "terminate_child", side_effect=spy):
            self.run_dispatcher(rdir)
        self.assertTrue(calls, "正常退出路径没有调用 terminate_child")
        with open(pidfile, encoding="utf-8") as f:
            grandchild = int(f.read())
        deadline = time.time() + 5
        while peer.pid_alive(grandchild) and time.time() < deadline:
            time.sleep(0.05)
        alive = peer.pid_alive(grandchild)
        if alive:
            os.kill(grandchild, signal.SIGKILL)
        self.assertFalse(alive, "孙进程在正常退出路径下未被清理")
        self.assertTrue(os.path.exists(os.path.join(rdir, "response.md")))

    def test_dispatcher_teardown_order_in_write_mode(self):
        """收尾顺序固定：销毁进程组 → 比对快照 → 释放写锁。"""
        rdir = self.make_run("RUN_WRITE", [sys.executable, "-c", "print('x')"], mode="write")
        events = []
        real_t, real_c, real_r = peer.terminate_child, peer.compare, peer.release_write_lock

        def t(child, grace):
            events.append("terminate")
            return real_t(child, grace)

        def c(*a, **k):
            events.append("compare")
            return real_c(*a, **k)

        def r(root, run_id):
            events.append("release:" + ("held" if os.path.exists(self.lock) else "gone"))
            return real_r(root, run_id)
        with patch.object(peer, "terminate_child", side_effect=t), \
             patch.object(peer, "compare", side_effect=c), \
             patch.object(peer, "release_write_lock", side_effect=r):
            self.run_dispatcher(rdir)
        self.assertEqual(events, ["terminate", "compare", "release:held"])
        self.assertFalse(os.path.exists(self.lock))
        self.assertTrue(os.path.exists(os.path.join(rdir, "changes.md")))

    def test_dispatcher_releases_write_lock_when_spawn_fails(self):
        rdir = self.make_run("RUN_BAD", ["/nonexistent/peer-test-binary"], mode="write")
        self.run_dispatcher(rdir)
        self.assertFalse(os.path.exists(self.lock))
        with open(os.path.join(rdir, "status.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["state"], "failed")


if __name__ == "__main__":
    unittest.main()
