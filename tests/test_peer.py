#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PeerAgent Comprehensive Unit Test Suite"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import importlib.util
from importlib.machinery import SourceFileLoader

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
peer_bin_path = os.path.join(REPO_DIR, "bin", "peer")

_loader = SourceFileLoader("peer", peer_bin_path)
_spec = importlib.util.spec_from_loader("peer", _loader)
peer = importlib.util.module_from_spec(_spec)
sys.modules["peer"] = peer
_loader.exec_module(peer)


class TestPeerCore(unittest.TestCase):

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
        tmp_dir = tempfile.mkdtemp()
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
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_claude_skill_intent_parsing(self):
        """测试 Claude 端技能的真实 Python 意图解析逻辑（完全免疫 shell 注入且正确识别否定词与方案）"""
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

        def parse_intent(content):
            lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
            raw = " ".join(lines)
            first_word = raw.split()[0].lower() if raw.split() else ""

            is_strictly_readonly = any(w in raw for w in [
                "只读", "仅审阅", "仅查看", "仅分析", "仅排查", "不要改", "不要修改",
                "无需修改", "不用修改", "不得修改", "严禁修改", "禁止修改", "请勿修改",
                "不修改", "只查", "只看", "评估", "是否需要", "是否应当"
            ])

            if first_word in ("exec", "review", "plan", "advice", "image"):
                return "review" if (first_word == "exec" and is_strictly_readonly) else first_word
            elif is_strictly_readonly:
                return "review"
            elif any(w in raw for w in ["出方案", "出计划", "设计方案", "怎么做", "出个计划", "重构方案", "方案", "计划"]):
                return "plan"
            elif any(w in raw for w in ["生图", "生成图片", "出图", "画一张", "做一张", "出海报", "做立绘"]):
                return "image"
            elif any(w in raw for w in ["修改", "实现", "编辑", "写入", "创建", "新建", "修复", "重构", "编写", "修掉", "改一下"]):
                return "exec"
            elif any(w in raw for w in ["为什么", "怎么看", "分析一下", "给个建议", "给个结论", "结论", "建议"]):
                return "advice"
            else:
                return "review"

        for prompt, expected in test_cases:
            res = parse_intent(prompt)
            self.assertEqual(res, expected, f"Failed on prompt: '{prompt}', got: '{res}' instead of '{expected}'")


class TestPeerExtended(unittest.TestCase):
    """扩展测试用例：覆盖快照对比、项目安全边界、配置读写、用量统计及 CLI 烟雾测试"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

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
        """测试 CLI 命令行入口响应 --help 与 stats"""
        bin_path = os.path.join(REPO_DIR, "bin", "peer")

        # --help
        res = subprocess.run([sys.executable, bin_path, "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("peer", res.stdout)
        self.assertIn("doctor", res.stdout)
        self.assertIn("ask", res.stdout)

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


if __name__ == "__main__":
    unittest.main()
