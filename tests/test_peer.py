#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PeerAgent 核心单元测试集"""

import os
import subprocess
import sys
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

    def test_claude_skill_intent_parsing(self):
        """测试 Claude 端技能的子命令提取与否定词严格只读逻辑"""
        test_cases = [
            ("exec 修改这个函数", "exec"),
            ("review 审阅 README", "review"),
            ("plan 针对登录做个方案", "plan"),
            ("advice 看看为什么超时", "advice"),
            ("image 生成一张架构图", "image"),
            ("不要修改任何文件，只查代码", "review"),
            ("严禁修改代码，出个方案", "review"),
            ("请勿修改文件，给个建议", "review"),
            ("修改这个 bug", "exec"),
            ("给个重构方案", "plan"),
            ("分析一下为什么内存泄露", "advice"),
        ]

        # 模拟技能中的 bash 意图识别脚本
        bash_script = """
        ARGUMENTS="$1"
        RAW_TASK=$(echo "$ARGUMENTS" | sed -e 's/^[[:space:]]*//')
        FIRST_WORD=$(echo "$RAW_TASK" | awk '{print $1}' | tr '[:upper:]' '[:lower:]')

        if [ "$FIRST_WORD" = "exec" ]; then
          KIND="exec"
        elif [ "$FIRST_WORD" = "review" ]; then
          KIND="review"
        elif [ "$FIRST_WORD" = "plan" ]; then
          KIND="plan"
        elif [ "$FIRST_WORD" = "advice" ]; then
          KIND="advice"
        elif [ "$FIRST_WORD" = "image" ]; then
          KIND="image"
        elif echo "$RAW_TASK" | grep -qE "只读|仅审阅|仅查看|仅分析|仅排查|不要改|不要修改|无需修改|不用修改|不得修改|严禁修改|禁止修改|请勿修改|不修改|只查|只看"; then
          KIND="review"
        elif echo "$RAW_TASK" | grep -qE "出方案|出计划|设计方案|怎么做|出个计划|方案"; then
          KIND="plan"
        elif echo "$RAW_TASK" | grep -qE "生图|生成图片|生成.*图|做张图|出张图|画一张|做一张|出海报|做立绘|画立绘"; then
          KIND="image"
        elif echo "$RAW_TASK" | grep -qE "修改|实现|编辑|写入|创建|新建|修复|重构|编写|修掉|改一下"; then
          KIND="exec"
        elif echo "$RAW_TASK" | grep -qE "为什么|怎么看|分析一下|给个建议|给个结论|结论|建议"; then
          KIND="advice"
        else
          KIND="review"
        fi
        echo -n "$KIND"
        """

        for prompt, expected in test_cases:
            res = subprocess.run(["bash", "-c", bash_script, "bash", prompt], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), expected, f"Failed on prompt: '{prompt}', got: '{res.stdout}' instead of '{expected}'")


if __name__ == "__main__":
    unittest.main()
