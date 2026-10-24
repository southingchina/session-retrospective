from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "retrospective_store.py"


def load_store():
    spec = importlib.util.spec_from_file_location("retrospective_store", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


store = load_store()


def make_lesson(**overrides):
    lesson = {
        "title": "浏览器控制失败时先重新获取标签页",
        "domain": "浏览器控制",
        "scenario": "页面跳转超时后继续操作",
        "trigger": "页面已加载但旧标签页对象返回连接错误",
        "wrong_path": "沿用跳转前的标签页对象反复点击",
        "wrong_assumption": "超时意味着页面没有加载",
        "root_cause": "页面状态已变化，控制对象已经失效",
        "rule": "先读取浏览器状态，再按当前标签页编号重新连接",
        "evidence": "重新连接后能够读取标题并点击页面",
        "verification": "检查地址和标题，再执行一次只读页面快照",
        "scope": "浏览器跳转超时但页面可能已经打开的场景",
        "invalid_when": "浏览器进程已经退出或控制扩展未加载",
        "confidence": "high",
        "impact": "high",
        "project": "general",
        "tags": ["Edge", "浏览器", "超时"],
        "status": "verified",
    }
    lesson.update(overrides)
    return lesson


def make_draft(lessons=None, **overrides):
    draft = {
        "schema_version": 1,
        "task_id": "session-001",
        "topic": "排查浏览器控制连接",
        "project": "general",
        "outcome": "completed",
        "tags": ["浏览器"],
        "summary": "恢复了页面控制并验证可读。",
        "detours": [],
        "lessons": lessons if lessons is not None else [make_lesson()],
        "unresolved": [],
    }
    draft.update(overrides)
    return draft


class CliSmokeTests(unittest.TestCase):
    def test_help_lists_all_supported_commands_in_chinese(self) -> None:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "init",
            "search",
            "compare",
            "plan",
            "apply",
            "validate",
            "rebuild-index",
        ):
            self.assertIn(command, result.stdout)
        self.assertIn("复盘", result.stdout)


class BoardInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "知识库"
        self.vault.mkdir()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_init_creates_only_the_empty_board_structure_and_is_idempotent(self) -> None:
        first = store.init_board(self.vault)
        second = store.init_board(self.vault)
        board = self.vault / "AI协作复盘"

        self.assertEqual(first["status"], "initialized")
        self.assertIn(second["status"], {"initialized", "already_initialized"})
        for relative in (
            "00-复盘导航.md",
            "对话复盘",
            "经验规则",
            "待验证",
            "已废弃",
            "_meta/index.json",
            "_meta/backups",
        ):
            self.assertTrue((board / relative).exists(), relative)
        index = json.loads((board / "_meta/index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["lessons"], [])
        self.assertEqual(list((board / "经验规则").rglob("*.md")), [])
        self.assertEqual(list((board / "待验证").rglob("*.md")), [])

    def test_chinese_components_remain_readable(self) -> None:
        self.assertEqual(store.slugify_component("浏览器 控制"), "浏览器-控制")
        self.assertEqual(store.slugify_component("错误：连接/失效"), "错误-连接-失效")

    def test_unsafe_paths_are_rejected(self) -> None:
        board = self.vault / "AI协作复盘"
        board.mkdir()
        for unsafe in ("../逃逸.md", "C:/Windows/win.ini", "/tmp/escape", "经验规则/CON.md", "经验规则/a\x01b.md"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(store.PathSafetyError):
                    store.safe_relative_path(board, unsafe)

    def test_symlink_escape_is_rejected_when_supported(self) -> None:
        board = self.vault / "AI协作复盘"
        board.mkdir()
        outside = self.vault / "outside"
        outside.mkdir()
        link = board / "link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("当前系统不允许测试进程创建符号链接")
        with self.assertRaises(store.PathSafetyError):
            store.safe_relative_path(board, "link/escape.md")


class DataModelTests(unittest.TestCase):
    def test_draft_rejects_more_than_five_lessons(self) -> None:
        with self.assertRaisesRegex(store.ValidationError, "最多 5 条"):
            store.validate_and_sanitize_draft(make_draft([make_lesson(title=f"规则{i}") for i in range(6)]))

    def test_canonical_identity_is_stable_after_whitespace_and_case_normalization(self) -> None:
        first = make_lesson(domain="Browser Control", trigger=" HTTP 401 ")
        second = make_lesson(domain="browser   control", trigger="http 401")
        self.assertEqual(store.canonical_key(first), store.canonical_key(second))
        self.assertEqual(store.lesson_id(first), store.lesson_id(second))

    def test_lesson_markdown_round_trip_preserves_structured_fields_and_chinese(self) -> None:
        prepared = store.prepare_lesson(make_lesson(), task_id="session-001")
        text = store.render_lesson(prepared)
        parsed = store.parse_lesson_text(text)

        for field in (
            "lesson_id",
            "canonical_key",
            "status",
            "confidence",
            "impact",
            "project",
            "tags",
            "evidence_count",
            "related_lessons",
            "source_sessions",
            "title",
            "root_cause",
            "rule",
        ):
            self.assertEqual(parsed[field], prepared[field], field)
        self.assertIn("## 下次直接行动", text)
        self.assertIn("先读取浏览器状态", text)

    def test_rebuild_index_recovers_from_a_corrupt_index(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            vault = Path(folder)
            store.init_board(vault)
            board = vault / "AI协作复盘"
            lesson = store.prepare_lesson(make_lesson(), task_id="session-001")
            path = store.lesson_path(board, lesson)
            store.atomic_write_text(path, store.render_lesson(lesson))
            (board / "_meta/index.json").write_text("{broken", encoding="utf-8")

            rebuilt = store.rebuild_index(vault)

            self.assertEqual(len(rebuilt["lessons"]), 1)
            self.assertEqual(rebuilt["lessons"][0]["lesson_id"], lesson["lesson_id"])

    def test_rebuild_index_rejects_malformed_lesson_in_mandatory_directory(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            vault = Path(folder)
            store.init_board(vault)
            bad = vault / "AI协作复盘/经验规则/浏览器/损坏.md"
            bad.parent.mkdir(parents=True)
            bad.write_text("不是规则文件", encoding="utf-8")
            with self.assertRaisesRegex(store.ValidationError, "无法解析"):
                store.rebuild_index(vault)


class RedactionAndQualityTests(unittest.TestCase):
    def test_nested_secrets_are_redacted_before_validation_output(self) -> None:
        secret = "sk-test-1234567890abcdef"
        draft = make_draft()
        draft["summary"] = f"Authorization: Bearer {secret}"
        draft["lessons"][0]["evidence"] = "password=not-a-real-secret-123; cookie=session=abcdef123456789"
        draft["unresolved"] = ["postgres://user:secretpass@host/db"]

        result = store.validate_and_sanitize_draft(draft)
        serialized = json.dumps(result, ensure_ascii=False)

        self.assertNotIn(secret, serialized)
        self.assertNotIn("not-a-real-secret-123", serialized)
        self.assertNotIn("secretpass", serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_no_valuable_lessons_returns_explicit_chinese_message(self) -> None:
        low_value = make_lesson(valuable=False)
        result = store.validate_and_sanitize_draft(make_draft([low_value]))
        self.assertEqual(result["lessons"], [])
        self.assertEqual(result["message"], "本次无需入库")
        self.assertEqual(len(result["skipped_lessons"]), 1)

    def test_missing_actionable_fields_is_skipped_as_low_value(self) -> None:
        vague = make_lesson(rule="", verification="")
        result = store.validate_and_sanitize_draft(make_draft([vague]))
        self.assertEqual(result["lessons"], [])
        self.assertIn("缺少", result["skipped_lessons"][0]["reason"])


class VaultFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "知识库"
        self.vault.mkdir()
        store.init_board(self.vault)
        self.board = self.vault / "AI协作复盘"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def add_lesson(self, lesson=None, task_id="old-session"):
        prepared = store.prepare_lesson(
            lesson or make_lesson(),
            task_id=task_id,
            now="2026-09-01T00:00:00+00:00",
        )
        path = store.lesson_path(self.board, prepared)
        store.atomic_write_text(path, store.render_lesson(prepared))
        store.rebuild_index(self.vault)
        return prepared, path


class SearchAndComparisonTests(VaultFixture):
    def test_exact_canonical_key_is_the_first_candidate(self) -> None:
        existing, _ = self.add_lesson()
        draft = make_draft([make_lesson(title="新标题也应精确命中")])

        comparison = store.compare_draft(self.vault, draft)

        candidates = comparison["lesson_comparisons"][0]["candidates"]
        self.assertEqual(candidates[0]["lesson_id"], existing["lesson_id"])
        self.assertEqual(candidates[0]["relation_hint"], "exact_canonical_key")
        self.assertNotIn("auto_action", comparison["lesson_comparisons"][0])

    def test_similar_topic_with_different_error_is_not_automatically_merged(self) -> None:
        first = make_lesson()
        existing, _ = self.add_lesson(first)
        different = make_lesson(
            title="扩展界面占用时释放控制通道",
            trigger="页面存在但提示另一个扩展界面已打开",
            wrong_path="继续刷新网页并重试点击",
            wrong_assumption="网页本身加载异常",
            root_cause="另一个扩展界面占用了浏览器控制通道",
            rule="关闭侧栏和其他控制会话，再重新连接标签页",
            evidence="释放扩展界面后控制恢复",
            verification="读取页面并执行一次无副作用点击",
        )

        comparison = store.compare_draft(self.vault, make_draft([different]))

        item = comparison["lesson_comparisons"][0]
        self.assertTrue(any(candidate["lesson_id"] == existing["lesson_id"] for candidate in item["candidates"]))
        self.assertIn(item["recommendation"], {"分别保留", "需要语义判断"})
        self.assertNotIn("auto_action", item)

    def test_same_root_cause_in_another_task_is_returned_as_a_link_candidate(self) -> None:
        existing, _ = self.add_lesson(make_lesson(project="广告后台"))
        other_task = make_lesson(
            title="NAS 面板跳转后重新连接",
            project="NAS",
            scenario="NAS 管理页跳转后读取信息",
            trigger="页面已加载但旧标签页对象返回连接错误",
        )

        comparison = store.compare_draft(self.vault, make_draft([other_task], project="NAS"))

        candidate = next(c for c in comparison["lesson_comparisons"][0]["candidates"] if c["lesson_id"] == existing["lesson_id"])
        self.assertIn(candidate["relation_hint"], {"same_root_cause", "exact_canonical_key"})

    def test_search_prefers_verified_and_limits_results_to_five(self) -> None:
        for i in range(7):
            status = "candidate" if i == 0 else "verified"
            self.add_lesson(make_lesson(
                title=f"浏览器经验{i}",
                trigger=f"浏览器连接错误{i}",
                root_cause=f"控制对象失效{i}",
                rule=f"重新连接标签页{i}",
                status=status,
            ), task_id=f"s{i}")

        default = store.search_lessons(self.vault, "浏览器连接错误", limit=5)
        expanded = store.search_lessons(self.vault, "浏览器连接错误", limit=5, include_candidates=True)

        self.assertLessEqual(len(default["results"]), 5)
        self.assertTrue(all(item["lesson"]["status"] == "verified" for item in default["results"]))
        self.assertLessEqual(len(expanded["results"]), 5)
        self.assertTrue(any(item["lesson"]["status"] == "candidate" for item in expanded["results"]))

    def test_other_vault_notes_are_background_links_only(self) -> None:
        note = self.vault / "普通知识/浏览器排错.md"
        note.parent.mkdir()
        note.write_text("浏览器控制连接错误和标签页状态", encoding="utf-8")

        comparison = store.compare_draft(self.vault, make_draft())

        self.assertIn("普通知识/浏览器排错.md", comparison["related_notes"])
        candidate_paths = [c["path"] for c in comparison["lesson_comparisons"][0]["candidates"]]
        self.assertNotIn("普通知识/浏览器排错.md", candidate_paths)

    def test_existing_session_retrospectives_are_in_the_mandatory_comparison(self) -> None:
        session = self.board / "对话复盘/2026/2026-09-01-浏览器复盘.md"
        session.parent.mkdir(parents=True)
        session.write_text("# 浏览器复盘\n\n旧标签页对象失效后重新连接。\n", encoding="utf-8")

        comparison = store.compare_draft(self.vault, make_draft())

        self.assertIn("对话复盘/2026/2026-09-01-浏览器复盘.md", comparison["related_sessions"])

    def test_unindexed_rule_in_mandatory_directory_blocks_comparison(self) -> None:
        prepared = store.prepare_lesson(make_lesson(), task_id="manual-session")
        path = store.lesson_path(self.board, prepared)
        store.atomic_write_text(path, store.render_lesson(prepared))

        with self.assertRaisesRegex(store.ValidationError, "强制比较"):
            store.compare_draft(self.vault, make_draft())


class PlanningAndApplyTests(VaultFixture):
    def decision_comparison(self, draft, action, target_lesson_id=None, **extra):
        comparison = store.compare_draft(self.vault, draft)
        lesson = store.prepare_lesson(draft["lessons"][0], draft["task_id"])
        decision = {
            "lesson_id": lesson["lesson_id"],
            "action": action,
            "reason": "已读取候选全文并比较触发条件、错误假设、根因和行动规则。",
        }
        if target_lesson_id:
            decision["target_lesson_id"] = target_lesson_id
        decision.update(extra)
        comparison["decisions"] = [decision]
        return comparison

    def test_plan_rejects_unknown_actions_or_missing_chinese_reason(self) -> None:
        draft = make_draft()
        bad_action = self.decision_comparison(draft, "overwrite")
        with self.assertRaisesRegex(store.ValidationError, "比较动作"):
            store.build_plan(self.vault, draft, bad_action)
        no_reason = self.decision_comparison(draft, "new_verified")
        no_reason["decisions"][0]["reason"] = ""
        with self.assertRaisesRegex(store.ValidationError, "理由"):
            store.build_plan(self.vault, draft, no_reason)

    def test_merge_target_must_exist_in_candidates(self) -> None:
        draft = make_draft()
        comparison = self.decision_comparison(draft, "merge", "missing-id")
        with self.assertRaisesRegex(store.ValidationError, "候选"):
            store.build_plan(self.vault, draft, comparison)

    def test_plan_contains_all_staleness_hashes_and_requires_confirmation(self) -> None:
        draft = make_draft()
        comparison = self.decision_comparison(draft, "new_verified")
        plan = store.build_plan(self.vault, draft, comparison)

        self.assertFalse(plan["confirmed"])
        self.assertRegex(plan["plan_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(plan["draft_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(plan["comparison_hash"], r"^[0-9a-f]{64}$")
        self.assertRegex(plan["index_hash"], r"^[0-9a-f]{64}$")
        self.assertIn("target_hash", plan["operations"][0])
        with self.assertRaisesRegex(store.ValidationError, "明确确认"):
            store.apply_plan(self.vault, plan)

    def test_index_change_invalidates_an_old_confirmed_plan(self) -> None:
        draft = make_draft()
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "new_verified"))
        confirmed = store.confirm_plan(plan)
        index_path = self.board / "_meta/index.json"
        index_path.write_text(index_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(store.ValidationError, "计划已失效"):
            store.apply_plan(self.vault, confirmed)

    def test_apply_new_rule_writes_session_index_and_validates(self) -> None:
        draft = make_draft()
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "new_verified"))

        result = store.apply_plan(self.vault, store.confirm_plan(plan))

        self.assertEqual(result["status"], "written")
        self.assertEqual(len(list((self.board / "经验规则").rglob("*.md"))), 1)
        self.assertEqual(len(list((self.board / "对话复盘").rglob("*.md"))), 1)
        self.assertEqual(store.validate_board(self.vault)["status"], "valid")
        self.assertTrue((self.board / "_meta/pending-plan.json").exists())

    def test_merge_increments_evidence_and_creates_backup(self) -> None:
        existing, original_path = self.add_lesson()
        draft = make_draft([make_lesson(title="重复验证")], task_id="new-session")
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "merge", existing["lesson_id"]))

        store.apply_plan(self.vault, store.confirm_plan(plan))

        merged = store.parse_lesson_text(original_path.read_text(encoding="utf-8"))
        self.assertEqual(merged["evidence_count"], 2)
        self.assertIn("new-session", merged["source_sessions"])
        self.assertTrue(any((self.board / "_meta/backups").rglob(original_path.name)))

    def test_different_error_can_create_a_new_rule_with_bidirectional_link(self) -> None:
        existing, old_path = self.add_lesson()
        different = make_lesson(
            title="释放扩展占用",
            trigger="提示另一个扩展界面已打开",
            wrong_assumption="页面刷新可以释放通道",
            root_cause="扩展侧栏占用了控制通道",
            rule="关闭侧栏与其他控制会话后重新连接",
        )
        draft = make_draft([different], task_id="new-session")
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "link", existing["lesson_id"]))

        store.apply_plan(self.vault, store.confirm_plan(plan))

        new_id = store.lesson_id(different)
        old = store.parse_lesson_text(old_path.read_text(encoding="utf-8"))
        self.assertIn(new_id, old["related_lessons"])
        new_record = next(item for item in store.rebuild_index(self.vault)["lessons"] if item["lesson_id"] == new_id)
        new = store.parse_lesson_text(store.safe_relative_path(self.board, new_record["path"]).read_text(encoding="utf-8"))
        self.assertIn(existing["lesson_id"], new["related_lessons"])

    def test_conflict_preserves_old_rule_and_creates_candidate(self) -> None:
        existing, old_path = self.add_lesson()
        old_text = old_path.read_text(encoding="utf-8")
        conflicting = make_lesson(
            title="超时后不要重新连接",
            rule="保留旧标签页对象等待恢复",
            evidence="某些页面等待后恢复",
            status="candidate",
        )
        draft = make_draft([conflicting], task_id="conflict-session")
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "conflict", existing["lesson_id"]))

        store.apply_plan(self.vault, store.confirm_plan(plan))

        self.assertIn("先读取浏览器状态", old_path.read_text(encoding="utf-8"))
        self.assertIn("先读取浏览器状态", old_text)
        self.assertEqual(len(list((self.board / "待验证").rglob("*.md"))), 1)

    def test_explicit_supersede_moves_old_rule_and_keeps_bidirectional_links(self) -> None:
        existing, old_path = self.add_lesson()
        replacement = make_lesson(
            title="改用当前浏览器状态重新连接",
            trigger="浏览器控制对象与当前标签页编号不一致",
            wrong_path="按旧编号重试",
            wrong_assumption="标签页编号不会变化",
            root_cause="页面跳转后标签页编号重新分配",
            rule="读取当前浏览器状态并按新编号连接",
            evidence="新编号连接连续两次成功",
        )
        draft = make_draft([replacement], task_id="replacement-session")
        comparison = self.decision_comparison(
            draft,
            "link",
            existing["lesson_id"],
            supersedes=True,
        )
        plan = store.build_plan(self.vault, draft, comparison)

        store.apply_plan(self.vault, store.confirm_plan(plan))

        self.assertFalse(old_path.exists())
        records = store.rebuild_index(self.vault)["lessons"]
        old_record = next(item for item in records if item["lesson_id"] == existing["lesson_id"])
        new_record = next(item for item in records if item["lesson_id"] == store.lesson_id(replacement))
        self.assertEqual(old_record["status"], "superseded")
        self.assertTrue(old_record["path"].startswith("已废弃/"))
        new_note = store.parse_lesson_text(store.safe_relative_path(self.board, new_record["path"]).read_text(encoding="utf-8"))
        self.assertIn(existing["lesson_id"], new_note["supersedes"])

    def test_target_change_invalidates_merge_plan(self) -> None:
        existing, target = self.add_lesson()
        draft = make_draft([make_lesson(title="重复验证")], task_id="new-session")
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "merge", existing["lesson_id"]))
        target.write_text(target.read_text(encoding="utf-8") + "外部修改", encoding="utf-8")
        with self.assertRaisesRegex(store.ValidationError, "计划已失效"):
            store.apply_plan(self.vault, store.confirm_plan(plan))

    def test_embedded_draft_or_comparison_change_invalidates_plan(self) -> None:
        draft = make_draft()
        original = store.build_plan(self.vault, draft, self.decision_comparison(draft, "new_verified"))
        changed_draft = store.confirm_plan(original)
        changed_draft["draft"]["summary"] = "后来改过的总结"
        with self.assertRaisesRegex(store.ValidationError, "计划已失效"):
            store.apply_plan(self.vault, changed_draft)
        changed_comparison = store.confirm_plan(original)
        changed_comparison["comparison"]["decisions"][0]["reason"] = "后来改过的理由"
        with self.assertRaisesRegex(store.ValidationError, "计划已失效"):
            store.apply_plan(self.vault, changed_comparison)

    def test_mandatory_session_change_invalidates_plan(self) -> None:
        session = self.board / "对话复盘/2026/旧复盘.md"
        session.parent.mkdir(parents=True)
        session.write_text("# 旧复盘\n\n浏览器连接错误。\n", encoding="utf-8")
        draft = make_draft()
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "new_verified"))
        session.write_text("# 旧复盘\n\n内容已经变化。\n", encoding="utf-8")
        with self.assertRaisesRegex(store.ValidationError, "计划已失效"):
            store.apply_plan(self.vault, store.confirm_plan(plan))

    def test_candidate_promotion_is_explicit_and_moves_rule_to_verified_directory(self) -> None:
        candidate, old_path = self.add_lesson(make_lesson(status="candidate"))
        draft = make_draft([make_lesson(title="第二次独立验证")], task_id="independent-session")
        comparison = self.decision_comparison(
            draft,
            "merge",
            candidate["lesson_id"],
            promote_to_verified=True,
        )
        plan = store.build_plan(self.vault, draft, comparison)
        self.assertTrue(plan["operations"][0]["promote_to_verified"])

        store.apply_plan(self.vault, store.confirm_plan(plan))

        self.assertFalse(old_path.exists())
        records = store.rebuild_index(self.vault)["lessons"]
        record = next(item for item in records if item["lesson_id"] == candidate["lesson_id"])
        self.assertEqual(record["status"], "verified")
        self.assertTrue(record["path"].startswith("经验规则/"))

    def test_write_failure_rolls_back_changed_files(self) -> None:
        existing, target = self.add_lesson()
        original = target.read_bytes()
        draft = make_draft([make_lesson(title="重复验证")], task_id="new-session")
        plan = store.build_plan(self.vault, draft, self.decision_comparison(draft, "merge", existing["lesson_id"]))
        real_atomic = store.atomic_write_text
        calls = {"count": 0}

        def fail_after_first(path, text):
            calls["count"] += 1
            if calls["count"] == 2:
                raise OSError("模拟写入失败")
            return real_atomic(path, text)

        with mock.patch.object(store, "atomic_write_text", side_effect=fail_after_first):
            with self.assertRaisesRegex(store.RetrospectiveError, "回滚"):
                store.apply_plan(self.vault, store.confirm_plan(plan))

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(self.board.rglob("*.tmp")), [])


class CliWorkflowTests(unittest.TestCase):
    def test_init_validate_and_search_commands_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            vault = Path(folder) / "知识库"
            vault.mkdir()
            commands = (
                ["init", "--vault", str(vault)],
                ["validate", "--vault", str(vault)],
                ["search", "--vault", str(vault), "--query", "浏览器"],
            )
            outputs = []
            for args in commands:
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", str(SCRIPT), *args],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(json.loads(result.stdout))
            self.assertEqual(outputs[0]["status"], "initialized")
            self.assertEqual(outputs[1]["status"], "valid")
            self.assertEqual(outputs[2]["results"], [])


class SkillContractTests(unittest.TestCase):
    def test_skill_document_contains_the_required_chinese_workflow_boundaries(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        required_phrases = (
            "复盘一下",
            "总结弯路",
            "生成复盘草稿",
            "查经验",
            "写入",
            "草稿阶段不得修改 Obsidian",
            "写入前必须比较",
            "相似度只能用于寻找候选",
            "最多 5 条",
            "[REDACTED]",
            "本次无需入库",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, text)
        self.assertNotIn("TODO", text)

    def test_description_only_states_trigger_conditions(self) -> None:
        frontmatter = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("description: Use when", frontmatter)
        self.assertIn("复盘", frontmatter)
        self.assertIn("经验", frontmatter)
        self.assertNotIn("哈希", frontmatter)

    def test_openai_yaml_mentions_the_skill_and_keeps_explicit_invocation(self) -> None:
        text = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('$session-retrospective', text)
        self.assertIn('display_name: "复盘入库"', text)
        self.assertIn("allow_implicit_invocation: false", text)

    def test_config_and_templates_are_chinese_and_contain_no_credentials(self) -> None:
        config = json.loads((ROOT / "assets/config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["vault_root"], "./example-vault")
        self.assertEqual(config["board_name"], "AI协作复盘")
        self.assertEqual(config["max_lessons_per_session"], 5)
        combined = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "assets/retrospective-template.md",
                "assets/lesson-template.md",
                "references/schema.md",
                "references/source-synthesis.md",
            )
        )
        for phrase in ("任务场景", "走过的弯路", "下次直接行动", "写前比较"):
            self.assertIn(phrase, combined)
        self.assertNotIn("czs@", combined)
        self.assertNotIn("TODO", combined)

    def test_evidence_pending_draft_package_contract_is_documented(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        schema = (ROOT / "references/schema.md").read_text(encoding="utf-8")
        required_skill_phrases = (
            "evidence-pending",
            "用户已确认",
            "客观观察",
            "候选规则",
            "待验证假设",
            "last_reviewed",
            "next_review",
            "复测触发条件",
            "独立 `.md` 文件",
            "JSONL 行号",
        )
        for phrase in required_skill_phrases:
            self.assertIn(phrase, skill)
        self.assertIn("内容摘要或哈希", schema)
        self.assertIn("未覆盖范围", schema)
        for relative in (
            "assets/moc-template.md",
            "assets/evidence-ledger-template.md",
            "assets/atomic-draft-template.md",
            "assets/issue-register-template.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_retrospective_does_not_take_over_the_handoff_workflow(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("仅要求交接", skill)
        self.assertIn("session-reopen", skill)
        self.assertIn("交接记录只能作为复盘证据", skill)


if __name__ == "__main__":
    unittest.main()
