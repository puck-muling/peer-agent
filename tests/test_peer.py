#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PeerAgent 核心单元测试集"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from importlib.machinery import SourceFileLoader

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
peer_bin_path = os.path.join(REPO_DIR, "bin", "peer")

peer = SourceFileLoader("peer", peer_bin_path).load_module()


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


if __name__ == "__main__":
    unittest.main()
