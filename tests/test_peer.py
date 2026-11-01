#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PeerAgent Comprehensive Unit Test Suite"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

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
        self.assertIn("peer 0.1.0", res_ver.stdout)

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

    def test_claude_skill_bash_evaluation(self):
        """普通请求中的命令替换在真实 Bash 落盘时保持字面量。"""
        skill_file = os.path.join(REPO_DIR, "skills", "claude", "codex", "SKILL.md")
        self.assertTrue(os.path.exists(skill_file))
        with open(skill_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Claude Code 会在执行前把 $ARGUMENTS 做文本替换，所以必须用带引号的 heredoc 原样落盘，不能再包进双引号里求值
        self.assertNotIn("printf '# 任务\\n%s\\n' \"$ARGUMENTS\"", content)
        self.assertIn("<<'PEER_ARGUMENTS_EOF_7f3a9c'", content)

        # 取出 SKILL.md 中真实的落盘片段，模拟 Claude Code 的文本替换后在 Bash 中执行
        start = content.index("   REQ_DIR=")
        end = content.index("   # 5. 安全提取意图")
        snippet = "\n".join(l[3:] if l.startswith("   ") else l for l in content[start:end].splitlines())
        marker = os.path.join(self.test_dir, "injected")
        hostile = "审阅 `touch %s` $(touch %s) $HOME \"q\" 'r'" % (marker, marker)
        script = "set -e\ncd \"$1\"\n" + snippet.replace("$ARGUMENTS", hostile) + "\ncat \"$REQ_FILE\"\n"
        workdir = self.test_dir
        res = subprocess.run(["bash", "-c", script, "bash", workdir], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn(hostile, res.stdout)
        self.assertFalse(os.path.exists(marker), "用户参数中的命令替换被意外执行")

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

            # 测试 ImageGlobalLock 在无 fcntl 时优雅降级不报错
            with peer.ImageGlobalLock("run_mock_win"):
                self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
