#!/usr/bin/env python3
"""“复盘入库”Skill 的确定性存储工具。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOARD_NAME = "AI协作复盘"
SCHEMA_VERSION = 1
STATUS_DIR = {
    "candidate": "待验证",
    "verified": "经验规则",
    "superseded": "已废弃",
    "deprecated": "已废弃",
}
VALID_STATUS = set(STATUS_DIR)
VALID_CONFIDENCE = {"low", "medium", "high"}
VALID_IMPACT = {"low", "medium", "high", "critical"}
WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
LESSON_BODY_FIELDS = (
    ("scenario", "任务场景"),
    ("trigger", "触发信号"),
    ("wrong_path", "走过的弯路"),
    ("wrong_assumption", "错误假设"),
    ("root_cause", "根因"),
    ("rule", "下次直接行动"),
    ("evidence", "验证证据"),
    ("verification", "验证方法"),
    ("scope", "适用范围"),
    ("invalid_when", "失效条件"),
)
FRONTMATTER_FIELDS = (
    "type", "lesson_id", "canonical_key", "status", "confidence", "impact",
    "project", "domain", "tags", "evidence_count", "created", "last_verified",
    "related_lessons", "supersedes", "source_sessions",
)


class RetrospectiveError(RuntimeError):
    """可向用户显示的基础错误。"""


class ValidationError(RetrospectiveError):
    """输入或知识库结构不符合约定。"""


class PathSafetyError(RetrospectiveError):
    """目标路径可能越过复盘板块。"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"\s+", " ", text)


def canonical_key(lesson: dict[str, Any]) -> str:
    return "|".join(normalize_text(lesson.get(field, "")) for field in ("domain", "trigger", "root_cause", "rule"))


def lesson_id(lesson: dict[str, Any]) -> str:
    return sha256_text(canonical_key(lesson))[:16]


def slugify_component(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).strip()
    text = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip(" .-")
    if not text:
        raise PathSafetyError("文件名为空或只包含非法字符")
    if text.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        raise PathSafetyError(f"Windows 保留名称不能作为文件名：{value}")
    return text[:96].rstrip(" .")


def safe_relative_path(board: Path, relative: str | Path) -> Path:
    raw = str(relative)
    if not raw or re.match(r"^[A-Za-z]:", raw) or raw.startswith(("/", "\\")):
        raise PathSafetyError(f"只允许板块内相对路径：{raw}")
    parts = re.split(r"[/\\]+", raw)
    if any(part in {"", ".", ".."} for part in parts):
        raise PathSafetyError(f"路径包含越界片段：{raw}")
    for part in parts:
        if any(ord(char) < 32 for char in part):
            raise PathSafetyError("路径包含控制字符")
        base = part.rstrip(" .").split(".", 1)[0].upper()
        if base in WINDOWS_RESERVED:
            raise PathSafetyError(f"路径包含 Windows 保留名称：{part}")
    base_path = board.resolve()
    candidate = (base_path / Path(*parts)).resolve(strict=False)
    try:
        candidate.relative_to(base_path)
    except ValueError as exc:
        raise PathSafetyError(f"路径越过复盘板块：{raw}") from exc
    return candidate


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def board_path(vault: str | Path) -> Path:
    root = Path(vault).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValidationError(f"知识库目录不存在：{root}")
    return root / BOARD_NAME


def empty_index() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "updated_at": utc_now(), "lessons": []}


def navigation_text() -> str:
    return """# AI 协作复盘

这里保存与 AI 协作时经过验证的经验、待验证规则和对话复盘。

## 使用方式

- 说“复盘一下”：生成草稿并比较已有经验，不写入知识库。
- 审阅草稿后说“写入”：执行当前最新且未失效的计划。
- 说“查经验：任务描述”：只读召回相关经验。

## 状态

- **经验规则**：已有明确证据，可以优先采用。
- **待验证**：可能有用，仍需新的独立证据。
- **已废弃**：已经失效或被新规则替代，只用于追溯。
"""


def init_board(vault: str | Path) -> dict[str, Any]:
    board = board_path(vault)
    existed = board.exists()
    for relative in ("对话复盘", "经验规则", "待验证", "已废弃", "_meta/backups"):
        safe_relative_path(board, relative).mkdir(parents=True, exist_ok=True)
    nav = safe_relative_path(board, "00-复盘导航.md")
    index_path = safe_relative_path(board, "_meta/index.json")
    if not nav.exists():
        atomic_write_text(nav, navigation_text())
    if not index_path.exists():
        atomic_write_json(index_path, empty_index())
    return {"status": "already_initialized" if existed else "initialized", "board": str(board)}


SECRET_PATTERNS = (
    (re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+\-/=]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(sk-[A-Za-z0-9_-]{8,})\b"), "[REDACTED]"),
    (re.compile(r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret)\s*[:=]\s*([^\s;,]+)"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(cookie\s*[:=]\s*)[^\s;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^\s:/]+:)[^@\s/]+(@)"), r"\1[REDACTED]\2"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED]"),
)


def redact_text(text: str) -> str:
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_data(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items()}
    return value


def validate_and_sanitize_draft(draft: dict[str, Any]) -> dict[str, Any]:
    clean = redact_data(copy.deepcopy(draft))
    for field in ("schema_version", "task_id", "topic", "project", "outcome", "summary", "lessons"):
        if field not in clean:
            raise ValidationError(f"复盘草稿缺少字段：{field}")
    if clean["schema_version"] != SCHEMA_VERSION:
        raise ValidationError("不支持的草稿版本")
    if clean["outcome"] not in {"completed", "partial", "failed"}:
        raise ValidationError("outcome 必须是 completed、partial 或 failed")
    if not isinstance(clean["lessons"], list):
        raise ValidationError("lessons 必须是数组")
    if len(clean["lessons"]) > 5:
        raise ValidationError("每次复盘最多 5 条经验")
    accepted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    required = ("title", "domain", "scenario", "trigger", "wrong_path", "wrong_assumption", "root_cause", "rule", "evidence", "verification", "scope", "invalid_when")
    for raw in clean["lessons"]:
        title = str(raw.get("title", "未命名经验"))
        if raw.get("valuable", True) is False:
            skipped.append({"title": title, "reason": "复用价值不足"})
            continue
        missing = [field for field in required if not str(raw.get(field, "")).strip()]
        if missing:
            skipped.append({"title": title, "reason": f"缺少必要内容：{', '.join(missing)}"})
            continue
        if raw.get("status", "candidate") not in VALID_STATUS:
            raise ValidationError(f"未知经验状态：{raw.get('status')}")
        if raw.get("confidence", "medium") not in VALID_CONFIDENCE:
            raise ValidationError(f"未知置信度：{raw.get('confidence')}")
        if raw.get("impact", "medium") not in VALID_IMPACT:
            raise ValidationError(f"未知影响级别：{raw.get('impact')}")
        accepted.append(raw)
    clean["lessons"] = accepted
    clean["skipped_lessons"] = skipped
    clean["message"] = "已生成复盘草稿" if accepted else "本次无需入库"
    return clean


def prepare_lesson(lesson: dict[str, Any], task_id: str, now: str | None = None) -> dict[str, Any]:
    prepared = redact_data(copy.deepcopy(lesson))
    timestamp = now or utc_now()
    prepared["type"] = "ai-lesson"
    prepared["canonical_key"] = canonical_key(prepared)
    prepared["lesson_id"] = lesson_id(prepared)
    prepared.setdefault("status", "candidate")
    prepared.setdefault("confidence", "medium")
    prepared.setdefault("impact", "medium")
    prepared.setdefault("project", "general")
    prepared.setdefault("tags", [])
    prepared.setdefault("domain", "通用")
    prepared.setdefault("evidence_count", 1)
    prepared.setdefault("created", timestamp)
    prepared.setdefault("last_verified", timestamp)
    prepared.setdefault("related_lessons", [])
    prepared.setdefault("supersedes", [])
    prepared.setdefault("source_sessions", [task_id])
    return prepared


def render_lesson(lesson: dict[str, Any]) -> str:
    lines = ["---"]
    for field in FRONTMATTER_FIELDS:
        lines.append(f"{field}: {json.dumps(lesson.get(field), ensure_ascii=False)}")
    lines.extend(["---", "", f"# {lesson['title']}", ""])
    for field, heading in LESSON_BODY_FIELDS:
        lines.extend([f"## {heading}", "", str(lesson.get(field, "")).strip(), ""])
    lines.extend(["## 关联与替代关系", ""])
    related = lesson.get("related_lessons", [])
    supersedes = lesson.get("supersedes", [])
    lines.append(f"- 关联经验：{', '.join(related) if related else '无'}")
    lines.append(f"- 替代规则：{', '.join(supersedes) if supersedes else '无'}")
    lines.append("")
    return "\n".join(lines)


def parse_lesson_text(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValidationError("无法解析经验规则：缺少前置信息")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError as exc:
        raise ValidationError("无法解析经验规则：前置信息不完整") from exc
    result: dict[str, Any] = {}
    try:
        for line in frontmatter.strip().splitlines():
            key, raw = line.split(":", 1)
            result[key.strip()] = json.loads(raw.strip())
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValidationError("无法解析经验规则：前置信息格式错误") from exc
    if result.get("type") != "ai-lesson" or not result.get("lesson_id"):
        raise ValidationError("无法解析经验规则：类型或编号缺失")
    title_match = re.search(r"(?m)^# (.+)$", body)
    if not title_match:
        raise ValidationError("无法解析经验规则：标题缺失")
    result["title"] = title_match.group(1).strip()
    for field, heading in LESSON_BODY_FIELDS:
        match = re.search(rf"(?ms)^## {re.escape(heading)}\n\n(.*?)(?=\n## |\Z)", body)
        if not match:
            raise ValidationError(f"无法解析经验规则：缺少“{heading}”")
        result[field] = match.group(1).strip()
    return result


def lesson_path(board: Path, lesson: dict[str, Any]) -> Path:
    directory = STATUS_DIR.get(lesson.get("status", "candidate"))
    if not directory:
        raise ValidationError(f"未知经验状态：{lesson.get('status')}")
    domain = slugify_component(str(lesson.get("domain", "通用")))
    title = slugify_component(str(lesson["title"]))
    return safe_relative_path(board, f"{directory}/{domain}/{title}--{lesson['lesson_id']}.md")


def _index_record(board: Path, path: Path, lesson: dict[str, Any]) -> dict[str, Any]:
    return {
        "lesson_id": lesson["lesson_id"],
        "canonical_key": lesson["canonical_key"],
        "title": lesson["title"],
        "status": lesson["status"],
        "confidence": lesson["confidence"],
        "impact": lesson["impact"],
        "project": lesson["project"],
        "domain": lesson["domain"],
        "tags": lesson["tags"],
        "trigger": lesson["trigger"],
        "wrong_assumption": lesson["wrong_assumption"],
        "root_cause": lesson["root_cause"],
        "rule": lesson["rule"],
        "evidence_count": lesson["evidence_count"],
        "last_verified": lesson["last_verified"],
        "path": path.relative_to(board).as_posix(),
        "file_hash": file_hash(path),
    }


def rebuild_index(vault: str | Path) -> dict[str, Any]:
    board = board_path(vault)
    if not board.exists():
        raise ValidationError("复盘板块尚未初始化")
    records: list[dict[str, Any]] = []
    for directory in ("经验规则", "待验证", "已废弃"):
        root = safe_relative_path(board, directory)
        try:
            paths = sorted(root.rglob("*.md"))
        except OSError as exc:
            raise ValidationError(f"强制比较目录读取失败：{root}") from exc
        for path in paths:
            try:
                lesson = parse_lesson_text(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValidationError) as exc:
                raise ValidationError(f"无法解析强制目录中的经验规则：{path}: {exc}") from exc
            records.append(_index_record(board, path, lesson))
    records.sort(key=lambda item: item["lesson_id"])
    index = {"schema_version": SCHEMA_VERSION, "updated_at": utc_now(), "lessons": records}
    atomic_write_json(safe_relative_path(board, "_meta/index.json"), index)
    return index


def load_index(vault: str | Path) -> tuple[dict[str, Any], Path]:
    board = board_path(vault)
    index_path = safe_relative_path(board, "_meta/index.json")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"索引损坏或无法读取：{index_path}") from exc
    if index.get("schema_version") != SCHEMA_VERSION or not isinstance(index.get("lessons"), list):
        raise ValidationError("索引结构无效，请先运行 rebuild-index")
    return index, index_path


def _tokens(value: Any) -> set[str]:
    text = normalize_text(value)
    tokens = set(re.findall(r"[a-z0-9][a-z0-9._-]*", text))
    chinese_runs = re.findall(r"[\u3400-\u9fff]+", text)
    for run in chinese_runs:
        tokens.update(run)
        tokens.update(run[index:index + 2] for index in range(len(run) - 1))
    return {token for token in tokens if token}


def _weighted_similarity(query: dict[str, Any] | str, record: dict[str, Any]) -> float:
    if isinstance(query, str):
        query_text = query
    else:
        query_text = " ".join(str(query.get(field, "")) for field in (
            "title", "domain", "scenario", "trigger", "wrong_assumption", "root_cause", "rule", "tags", "project"
        ))
    record_text = " ".join(str(record.get(field, "")) for field in (
        "title", "domain", "trigger", "wrong_assumption", "root_cause", "rule", "tags", "project"
    ))
    left, right = _tokens(query_text), _tokens(record_text)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _full_lesson(board: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = safe_relative_path(board, record["path"])
    try:
        return parse_lesson_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError) as exc:
        raise ValidationError(f"候选全文读取失败：{path}") from exc


def search_lessons(vault: str | Path, query: str, limit: int = 5, include_candidates: bool = False) -> dict[str, Any]:
    if not 1 <= limit <= 20:
        raise ValidationError("limit 必须在 1 到 20 之间")
    index, _ = load_index(vault)
    board = board_path(vault)
    allowed = {"verified"} if not include_candidates else {"verified", "candidate"}
    scored: list[dict[str, Any]] = []
    for record in index["lessons"]:
        if record.get("status") not in allowed:
            continue
        score = _weighted_similarity(query, record)
        lesson = _full_lesson(board, record)
        scored.append({
            "score": round(score, 6),
            "reason": "字段与任务描述相似" if score else "作为同领域备选",
            "lesson": lesson,
            "path": record["path"],
        })
    scored.sort(key=lambda item: (item["lesson"]["status"] == "verified", item["score"], item["lesson"].get("evidence_count", 0)), reverse=True)
    selected = scored[:limit]
    if include_candidates and limit > 0:
        candidates = [item for item in scored if item["lesson"]["status"] == "candidate"]
        if candidates and not any(item["lesson"]["status"] == "candidate" for item in selected):
            selected = (selected[: max(0, limit - 1)] + [candidates[0]])[:limit]
    return {"query": query, "results": selected, "count": len(selected)}


def _relation_hint(lesson: dict[str, Any], existing: dict[str, Any]) -> str:
    if canonical_key(lesson) == existing.get("canonical_key"):
        return "exact_canonical_key"
    if normalize_text(lesson.get("root_cause")) == normalize_text(existing.get("root_cause")):
        return "same_root_cause"
    if normalize_text(lesson.get("trigger")) == normalize_text(existing.get("trigger")):
        return "same_trigger"
    return "text_similarity"


def _related_background_notes(vault: Path, board: Path, draft: dict[str, Any], limit: int = 10) -> tuple[list[str], list[str]]:
    query = " ".join(
        [str(draft.get("topic", "")), str(draft.get("summary", ""))]
        + [" ".join(str(item.get(key, "")) for key in ("title", "trigger", "root_cause", "rule")) for item in draft.get("lessons", [])]
    )
    terms = sorted(_tokens(query), key=len, reverse=True)
    found: list[str] = []
    gaps: list[str] = []
    try:
        roots = list(vault.iterdir())
    except OSError as exc:
        return [], [f"知识库根目录无法列出：{exc}"]
    for root in roots:
        if root.resolve() == board.resolve() or not root.is_dir():
            continue
        try:
            paths = root.rglob("*.md")
            for path in paths:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError as exc:
                    gaps.append(f"无法读取：{path.relative_to(vault).as_posix()}：{exc}")
                    continue
                if any(term in normalize_text(text) for term in terms[:40]):
                    found.append(path.relative_to(vault).as_posix())
                    if len(found) >= limit:
                        return found, gaps
        except OSError as exc:
            gaps.append(f"无法搜索：{root.relative_to(vault).as_posix()}：{exc}")
    return found, gaps


def _mandatory_files(board: Path) -> list[dict[str, Any]]:
    state: list[dict[str, Any]] = []
    for directory in ("经验规则", "待验证", "已废弃", "对话复盘"):
        root = safe_relative_path(board, directory)
        try:
            paths = sorted(root.rglob("*.md"))
        except OSError as exc:
            raise ValidationError(f"强制比较目录读取失败：{root}") from exc
        for path in paths:
            try:
                digest = file_hash(path)
            except OSError as exc:
                raise ValidationError(f"强制比较文件读取失败：{path}") from exc
            state.append({"path": path.relative_to(board).as_posix(), "file_hash": digest})
    return state


def _mandatory_state_hash(board: Path) -> str:
    return sha256_text(stable_json(_mandatory_files(board)))


def _audit_rule_index(board: Path, index: dict[str, Any]) -> None:
    indexed = {record.get("path"): record.get("file_hash") for record in index["lessons"]}
    actual = {
        item["path"]: item["file_hash"]
        for item in _mandatory_files(board)
        if item["path"].startswith(("经验规则/", "待验证/", "已废弃/"))
    }
    if indexed != actual:
        raise ValidationError("强制比较目录与索引不一致，请先运行 rebuild-index")


def _related_session_notes(board: Path, draft: dict[str, Any], limit: int = 10) -> list[str]:
    root = safe_relative_path(board, "对话复盘")
    query = " ".join(
        [str(draft.get("topic", "")), str(draft.get("summary", ""))]
        + [" ".join(str(item.get(key, "")) for key in ("title", "trigger", "root_cause", "rule")) for item in draft.get("lessons", [])]
    )
    terms = sorted(_tokens(query), key=len, reverse=True)
    matches: list[str] = []
    try:
        paths = sorted(root.rglob("*.md"))
    except OSError as exc:
        raise ValidationError(f"强制比较目录读取失败：{root}") from exc
    for path in paths:
        try:
            text = normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError as exc:
            raise ValidationError(f"强制比较文件读取失败：{path}") from exc
        if any(term in text for term in terms[:40]):
            matches.append(path.relative_to(board).as_posix())
            if len(matches) >= limit:
                break
    return matches


def compare_draft(vault: str | Path, draft: dict[str, Any], candidate_limit: int = 5) -> dict[str, Any]:
    clean = validate_and_sanitize_draft(draft)
    index, index_path = load_index(vault)
    board = board_path(vault)
    _audit_rule_index(board, index)
    comparisons: list[dict[str, Any]] = []
    for raw in clean["lessons"]:
        lesson = prepare_lesson(raw, clean["task_id"])
        candidates: list[dict[str, Any]] = []
        for record in index["lessons"]:
            full = _full_lesson(board, record)
            score = 1.0 if lesson["canonical_key"] == record.get("canonical_key") else _weighted_similarity(lesson, record)
            candidates.append({
                "lesson_id": record["lesson_id"],
                "path": record["path"],
                "score": round(score, 6),
                "relation_hint": _relation_hint(lesson, full),
                "full_lesson": full,
            })
        candidates.sort(key=lambda item: (item["relation_hint"] == "exact_canonical_key", item["score"]), reverse=True)
        candidates = candidates[:candidate_limit]
        recommendation = "需要语义判断"
        if candidates:
            top = candidates[0]
            existing = top["full_lesson"]
            same_context = normalize_text(lesson.get("domain")) == normalize_text(existing.get("domain"))
            different_error = (
                normalize_text(lesson.get("wrong_assumption")) != normalize_text(existing.get("wrong_assumption"))
                or normalize_text(lesson.get("root_cause")) != normalize_text(existing.get("root_cause"))
            )
            if same_context and different_error:
                recommendation = "分别保留"
        comparisons.append({
            "lesson_id": lesson["lesson_id"],
            "title": lesson["title"],
            "recommendation": recommendation,
            "candidates": candidates,
        })
    vault_root = Path(vault).resolve()
    related, gaps = _related_background_notes(vault_root, board, clean)
    related_sessions = _related_session_notes(board, clean)
    return {
        "schema_version": SCHEMA_VERSION,
        "draft_hash": sha256_text(stable_json(clean)),
        "index_hash": file_hash(index_path),
        "mandatory_state_hash": _mandatory_state_hash(board),
        "lesson_comparisons": comparisons,
        "related_sessions": related_sessions,
        "related_notes": related,
        "coverage_gaps": gaps,
        "decisions": [],
    }


ALLOWED_ACTIONS = {"new_verified", "new_candidate", "merge", "link", "conflict", "skip"}


def _plan_core(plan: dict[str, Any]) -> dict[str, Any]:
    core = copy.deepcopy(plan)
    core.pop("plan_hash", None)
    core.pop("confirmed", None)
    return core


def _find_record(index: dict[str, Any], target_id: str) -> dict[str, Any]:
    for record in index["lessons"]:
        if record.get("lesson_id") == target_id:
            return record
    raise ValidationError(f"目标经验不存在：{target_id}")


def build_plan(vault: str | Path, draft: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    clean = validate_and_sanitize_draft(draft)
    current_draft_hash = sha256_text(stable_json(clean))
    if comparison.get("draft_hash") != current_draft_hash:
        raise ValidationError("比较结果与当前草稿不一致")
    index, index_path = load_index(vault)
    if comparison.get("index_hash") != file_hash(index_path):
        raise ValidationError("比较使用的索引已经变化，请重新比较")
    board = board_path(vault)
    if comparison.get("mandatory_state_hash") != _mandatory_state_hash(board):
        raise ValidationError("强制比较范围已经变化，请重新比较")
    decisions = comparison.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != len(clean["lessons"]):
        raise ValidationError("每条经验都必须有一个比较决定")
    comparison_by_id = {item["lesson_id"]: item for item in comparison.get("lesson_comparisons", [])}
    lesson_by_id = {lesson_id(item): item for item in clean["lessons"]}
    operations: list[dict[str, Any]] = []
    for decision in decisions:
        action = decision.get("action")
        if action not in ALLOWED_ACTIONS:
            raise ValidationError(f"未知比较动作：{action}")
        if not str(decision.get("reason", "")).strip():
            raise ValidationError("每个比较动作都必须写明中文理由")
        current_id = decision.get("lesson_id")
        if current_id not in lesson_by_id or current_id not in comparison_by_id:
            raise ValidationError(f"比较决定引用了未知经验：{current_id}")
        if action == "skip":
            continue
        raw = copy.deepcopy(lesson_by_id[current_id])
        if action == "new_verified":
            raw["status"] = "verified"
        elif action in {"new_candidate", "conflict"}:
            raw["status"] = "candidate"
        prepared = prepare_lesson(raw, clean["task_id"])
        operation: dict[str, Any] = {
            "action": action,
            "reason": decision["reason"],
            "lesson": prepared,
            "target_hash": None,
        }
        if action in {"merge", "link", "conflict"}:
            target_id = decision.get("target_lesson_id")
            candidate_ids = {candidate["lesson_id"] for candidate in comparison_by_id[current_id].get("candidates", [])}
            if target_id not in candidate_ids:
                raise ValidationError("合并、关联或冲突目标必须来自已读取的候选全文")
            target_record = _find_record(index, target_id)
            operation.update({
                "target_lesson_id": target_id,
                "target_path": target_record["path"],
                "target_hash": file_hash(safe_relative_path(board, target_record["path"])),
                "promote_to_verified": bool(decision.get("promote_to_verified", False)),
                "supersedes": bool(decision.get("supersedes", False)),
            })
            if action == "link" and operation["supersedes"]:
                target_full = next(candidate["full_lesson"] for candidate in comparison_by_id[current_id]["candidates"] if candidate["lesson_id"] == target_id)
                superseded = copy.deepcopy(target_full)
                superseded["status"] = "superseded"
                superseded_path = lesson_path(board, superseded)
                operation["superseded_path"] = superseded_path.relative_to(board).as_posix()
                operation["superseded_target_hash"] = file_hash(superseded_path)
            if action == "merge" and operation["promote_to_verified"]:
                target_full = next(candidate["full_lesson"] for candidate in comparison_by_id[current_id]["candidates"] if candidate["lesson_id"] == target_id)
                promoted = copy.deepcopy(target_full)
                promoted["status"] = "verified"
                promoted_path = lesson_path(board, promoted)
                operation["promoted_path"] = promoted_path.relative_to(board).as_posix()
                operation["promoted_target_hash"] = file_hash(promoted_path)
        if action in {"new_verified", "new_candidate", "link", "conflict"}:
            new_path = lesson_path(board, prepared)
            operation["new_path"] = new_path.relative_to(board).as_posix()
            operation["new_target_hash"] = file_hash(new_path)
        if action == "merge":
            operation["new_target_hash"] = None
        operations.append(operation)
    date = datetime.now().date().isoformat()
    session_name = f"{date}-{slugify_component(str(clean['topic']))}--{sha256_text(str(clean['task_id']))[:8]}.md"
    session_relative = f"对话复盘/{date[:4]}/{session_name}"
    session_path = safe_relative_path(board, session_relative)
    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "draft_hash": current_draft_hash,
        "comparison_hash": sha256_text(stable_json(comparison)),
        "index_hash": file_hash(index_path),
        "mandatory_state_hash": comparison["mandatory_state_hash"],
        "draft": clean,
        "comparison": comparison,
        "operations": operations,
        "session_path": session_relative,
        "session_target_hash": file_hash(session_path),
        "confirmed": False,
    }
    plan["plan_hash"] = sha256_text(stable_json(_plan_core(plan)))
    return plan


def confirm_plan(plan: dict[str, Any]) -> dict[str, Any]:
    confirmed = copy.deepcopy(plan)
    confirmed["confirmed"] = True
    return confirmed


def render_session(draft: dict[str, Any], operations: list[dict[str, Any]]) -> str:
    lesson_ids = [operation["lesson"]["lesson_id"] for operation in operations]
    date = datetime.now().date().isoformat()
    metadata = {
        "type": "ai-session-retrospective",
        "date": date,
        "task_id": draft["task_id"],
        "topic": draft["topic"],
        "project": draft.get("project", "general"),
        "outcome": draft["outcome"],
        "tags": draft.get("tags", []),
        "lesson_ids": lesson_ids,
        "source": "codex",
    }
    lines = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items()]
    lines.extend(["---", "", f"# {draft['topic']}", "", "## 目标与结果", "", draft["summary"], "", "## 走过的弯路", ""])
    if draft.get("detours"):
        for item in draft["detours"]:
            lines.append(f"- {item.get('what_happened', '')}；根因：{item.get('root_cause', '')}；建议：{item.get('recommendation', '')}")
    else:
        lines.append("- 见本次沉淀的原子经验。")
    lines.extend(["", "## 已有知识比较", ""])
    for operation in operations:
        lines.append(f"- {operation['lesson']['title']}：{operation['action']}；{operation['reason']}")
    lines.extend(["", "## 沉淀结果", ""])
    lines.extend(f"- [[{operation['lesson']['title']}]]" for operation in operations)
    lines.extend(["", "## 未解决问题", ""])
    unresolved = draft.get("unresolved", [])
    lines.extend((f"- {item}" for item in unresolved) if unresolved else ["- 无"])
    lines.append("")
    return "\n".join(lines)


def _atomic_restore(path: Path, content: bytes | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.restore.", dir=path.parent)
    temp = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _ensure_plan_fresh(vault: str | Path, plan: dict[str, Any]) -> tuple[Path, dict[str, Any], Path]:
    if not plan.get("confirmed"):
        raise ValidationError("写入计划尚未得到用户明确确认")
    if plan.get("plan_hash") != sha256_text(stable_json(_plan_core(plan))):
        raise ValidationError("计划已失效：计划内容或确认范围发生变化")
    if plan.get("draft_hash") != sha256_text(stable_json(plan.get("draft"))):
        raise ValidationError("计划已失效：草稿内容发生变化")
    if plan.get("comparison_hash") != sha256_text(stable_json(plan.get("comparison"))):
        raise ValidationError("计划已失效：比较结果发生变化")
    index, index_path = load_index(vault)
    if plan.get("index_hash") != file_hash(index_path):
        raise ValidationError("计划已失效：知识库索引发生变化")
    board = board_path(vault)
    if plan.get("mandatory_state_hash") != _mandatory_state_hash(board):
        raise ValidationError("计划已失效：强制比较范围发生变化")
    for operation in plan.get("operations", []):
        if operation.get("target_path"):
            path = safe_relative_path(board, operation["target_path"])
            if file_hash(path) != operation.get("target_hash"):
                raise ValidationError("计划已失效：目标经验已被修改")
        if operation.get("new_path"):
            path = safe_relative_path(board, operation["new_path"])
            if file_hash(path) != operation.get("new_target_hash"):
                raise ValidationError("计划已失效：新建目标路径状态发生变化")
        if operation.get("promoted_path"):
            path = safe_relative_path(board, operation["promoted_path"])
            if file_hash(path) != operation.get("promoted_target_hash"):
                raise ValidationError("计划已失效：晋级目标路径状态发生变化")
        if operation.get("superseded_path"):
            path = safe_relative_path(board, operation["superseded_path"])
            if file_hash(path) != operation.get("superseded_target_hash"):
                raise ValidationError("计划已失效：替代目标路径状态发生变化")
    session_path = safe_relative_path(board, plan["session_path"])
    if file_hash(session_path) != plan.get("session_target_hash"):
        raise ValidationError("计划已失效：对话复盘目标已变化")
    return board, index, index_path


def apply_plan(vault: str | Path, plan: dict[str, Any]) -> dict[str, Any]:
    board, index, index_path = _ensure_plan_fresh(vault, plan)
    changes: dict[Path, str] = {}
    deletions: set[Path] = set()
    operations = copy.deepcopy(plan.get("operations", []))
    records = {record["lesson_id"]: record for record in index["lessons"]}
    for operation in operations:
        action = operation["action"]
        lesson = operation["lesson"]
        if action == "merge":
            target_path = safe_relative_path(board, operation["target_path"])
            existing = parse_lesson_text(target_path.read_text(encoding="utf-8"))
            existing["evidence_count"] = int(existing.get("evidence_count", 1)) + 1
            existing["last_verified"] = utc_now()
            existing["source_sessions"] = sorted(set(existing.get("source_sessions", []) + lesson.get("source_sessions", [])))
            existing["evidence"] = f"{existing['evidence']}\n\n- 新证据：{lesson['evidence']}"
            if operation.get("promote_to_verified"):
                existing["status"] = "verified"
                promoted_path = safe_relative_path(board, operation["promoted_path"])
                changes[promoted_path] = render_lesson(existing)
                if promoted_path != target_path:
                    deletions.add(target_path)
            else:
                changes[target_path] = render_lesson(existing)
        elif action in {"new_verified", "new_candidate"}:
            changes[safe_relative_path(board, operation["new_path"])] = render_lesson(lesson)
        elif action in {"link", "conflict"}:
            target_path = safe_relative_path(board, operation["target_path"])
            existing = parse_lesson_text(target_path.read_text(encoding="utf-8"))
            existing["related_lessons"] = sorted(set(existing.get("related_lessons", []) + [lesson["lesson_id"]]))
            lesson["related_lessons"] = sorted(set(lesson.get("related_lessons", []) + [existing["lesson_id"]]))
            if action == "conflict":
                lesson["status"] = "candidate"
            if operation.get("supersedes"):
                lesson["supersedes"] = sorted(set(lesson.get("supersedes", []) + [existing["lesson_id"]]))
                existing["status"] = "superseded"
                superseded_path = safe_relative_path(board, operation["superseded_path"])
                changes[superseded_path] = render_lesson(existing)
                if superseded_path != target_path:
                    deletions.add(target_path)
            else:
                changes[target_path] = render_lesson(existing)
            changes[safe_relative_path(board, operation["new_path"])] = render_lesson(lesson)
    session_path = safe_relative_path(board, plan["session_path"])
    changes[session_path] = render_session(plan["draft"], operations)
    pending_path = safe_relative_path(board, "_meta/pending-plan.json")
    tracked_paths = set(changes) | deletions | {index_path, pending_path}
    originals = {path: path.read_bytes() if path.exists() else None for path in tracked_paths}
    backup_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = safe_relative_path(board, f"_meta/backups/{backup_stamp}-{plan['plan_hash'][:8]}")
    try:
        for path, original in originals.items():
            if original is not None and path not in {index_path, pending_path}:
                relative = path.relative_to(board)
                destination = backup_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
        for path, text in changes.items():
            atomic_write_text(path, text)
        for path in deletions:
            if path.exists():
                path.unlink()
        rebuilt = rebuild_index(vault)
        atomic_write_json(pending_path, {"status": "已写入", "plan_hash": plan["plan_hash"], "applied_at": utc_now()})
        validation = validate_board(vault)
    except Exception as exc:
        for path, content in originals.items():
            try:
                _atomic_restore(path, content)
            except OSError:
                pass
        raise RetrospectiveError(f"写入失败，已回滚：{exc}") from exc
    return {
        "status": "written",
        "plan_hash": plan["plan_hash"],
        "changed_files": [path.relative_to(board).as_posix() for path in changes],
        "lesson_count": len(rebuilt["lessons"]),
        "validation": validation,
    }


def validate_board(vault: str | Path) -> dict[str, Any]:
    board = board_path(vault)
    required = ("00-复盘导航.md", "经验规则", "待验证", "已废弃", "对话复盘", "_meta/index.json", "_meta/backups")
    missing = [relative for relative in required if not safe_relative_path(board, relative).exists()]
    if missing:
        raise ValidationError(f"复盘板块缺少：{', '.join(missing)}")
    index, _ = load_index(vault)
    seen: set[str] = set()
    lessons: dict[str, dict[str, Any]] = {}
    for record in index["lessons"]:
        identifier = record.get("lesson_id")
        if identifier in seen:
            raise ValidationError(f"索引中存在重复经验编号：{identifier}")
        seen.add(identifier)
        path = safe_relative_path(board, record["path"])
        if not path.exists() or file_hash(path) != record.get("file_hash"):
            raise ValidationError(f"索引与经验文件不一致：{record.get('path')}")
        lesson = _full_lesson(board, record)
        if lesson["lesson_id"] != identifier:
            raise ValidationError(f"经验编号与索引不一致：{record.get('path')}")
        lessons[identifier] = lesson
    for identifier, lesson in lessons.items():
        for related in lesson.get("related_lessons", []):
            if related not in lessons:
                raise ValidationError(f"经验 {identifier} 引用了不存在的关联经验 {related}")
    return {"status": "valid", "lesson_count": len(lessons), "board": str(board)}


def read_json_file(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"无法读取 JSON 文件：{source}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"JSON 顶层必须是对象：{source}")
    return value


def emit_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="复盘入库：比较、计划并安全写入 Obsidian 经验库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="初始化复盘板块")
    init_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")

    search_parser = subparsers.add_parser("search", help="查询既有经验")
    search_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")
    search_parser.add_argument("--query", required=True, help="任务、错误或场景描述")
    search_parser.add_argument("--limit", type=int, default=5, help="最多返回数量，默认 5")
    search_parser.add_argument("--include-candidates", action="store_true", help="补充待验证经验")

    compare_parser = subparsers.add_parser("compare", help="比较草稿与既有知识")
    compare_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")
    compare_parser.add_argument("--draft", required=True, help="复盘草稿 JSON")
    compare_parser.add_argument("--output", required=True, help="比较结果 JSON")

    plan_parser = subparsers.add_parser("plan", help="生成带哈希的写入计划")
    plan_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")
    plan_parser.add_argument("--draft", required=True, help="复盘草稿 JSON")
    plan_parser.add_argument("--comparison", required=True, help="含语义决定的比较结果 JSON")
    plan_parser.add_argument("--output", required=True, help="写入计划 JSON")

    apply_parser = subparsers.add_parser("apply", help="应用已确认的写入计划")
    apply_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")
    apply_parser.add_argument("--plan", required=True, help="写入计划 JSON")
    apply_parser.add_argument("--confirm-hash", required=True, help="用户确认的完整计划哈希")

    validate_parser = subparsers.add_parser("validate", help="校验复盘板块")
    validate_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")

    rebuild_parser = subparsers.add_parser("rebuild-index", help="从 Markdown 重建索引")
    rebuild_parser.add_argument("--vault", required=True, help="Obsidian 知识库根目录")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        result = init_board(args.vault)
    elif args.command == "search":
        result = search_lessons(args.vault, args.query, args.limit, args.include_candidates)
    elif args.command == "compare":
        result = compare_draft(args.vault, read_json_file(args.draft))
        atomic_write_json(Path(args.output).resolve(), result)
    elif args.command == "plan":
        result = build_plan(args.vault, read_json_file(args.draft), read_json_file(args.comparison))
        atomic_write_json(Path(args.output).resolve(), result)
    elif args.command == "apply":
        plan = read_json_file(args.plan)
        if args.confirm_hash != plan.get("plan_hash"):
            raise ValidationError("确认哈希与当前计划不一致")
        result = apply_plan(args.vault, confirm_plan(plan))
    elif args.command == "validate":
        result = validate_board(args.vault)
    elif args.command == "rebuild-index":
        result = rebuild_index(args.vault)
    else:
        raise ValidationError(f"未知命令：{args.command}")
    emit_json(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RetrospectiveError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2)
