# 数据与命令规范

## 草稿 `draft.json`

顶层字段：

- `schema_version`：固定为 `1`。
- `task_id`、`topic`、`project`、`summary`：字符串。
- `outcome`：`completed`、`partial` 或 `failed`。
- `tags`、`detours`、`lessons`、`unresolved`：数组。
- `lessons` 最多 5 条。

每条经验包含：`title`、`domain`、`scenario`、`trigger`、`wrong_path`、`wrong_assumption`、`root_cause`、`rule`、`evidence`、`verification`、`scope`、`invalid_when`、`confidence`、`impact`、`project`、`tags`、`status`。若判断没有复用价值，可写 `valuable: false`，脚本会跳过并返回“本次无需入库”。

## 写前比较 `comparison.json`

`compare` 生成草稿哈希、索引哈希、每条经验的候选全文、相关背景笔记和搜索覆盖缺口。模型完成全文比较后，在 `decisions` 中为每条经验填写：

```json
{
  "lesson_id": "草稿经验编号",
  "action": "new_verified",
  "reason": "已比较触发信号、错误假设、根因和行动规则，未发现重复。"
}
```

动作含义：

- `new_verified`：证据充分，新增到“经验规则”。
- `new_candidate`：有复用价值但证据不足，新增到“待验证”。
- `merge`：与候选属于同一错误模式，增加证据。目标写入 `target_lesson_id`。
- `link`：错误或场景不同，分别保留并双向关联。
- `conflict`：新证据与旧规则冲突，保留双方，新条目进入“待验证”。
- `skip`：不值得入库或已被完整覆盖。

`merge` 可显式增加 `promote_to_verified: true`。`link` 可显式增加 `supersedes: true`；只有证据和用户确认都充分时使用。

## 证据待补草稿包

当复盘跨天、多系统或依赖完整主会话时，工作目录还应包含以下独立 Markdown 文件：

```text
00_MOC/MOC-主题-日期.md
01_Evidence/证据账本-主题-日期.md
02_Atomic/原子笔记.md
03_Issues/未决问题跟踪.md
```

所有文件使用：

```yaml
status: draft
confidence: medium
verification: partial
review_stage: evidence-pending
last_reviewed: YYYY-MM-DD
next_review: 待定
source: 已脱敏来源说明
```

每条证据至少要能通过下列组合之一回查：

- `jsonl_line` 加 `message_id`、`timestamp`、内容摘要或哈希之一；
- `file_path` 加采集时间、字段名、日志行号或文件哈希之一。

记录 `collected_at`、`redaction`、`reproducibility` 与结论边界。内容摘要或哈希用于抵抗 JSONL 行号漂移；不得只存行号。

原子笔记固定包含“用户已确认、客观观察、已验证事实、候选规则、待验证假设、去重与关联”。去重与关联至少写明比较范围、比较时间、比较方式、未覆盖范围、新增、重复、合并到、冲突和关联。

未决问题表必须包含复测触发条件。草稿包的写入计划必须逐个列出目标文件、状态和哈希；没有进入计划的文件不得写入。

## 写入计划 `plan.json`

计划包含 `draft_hash`、`comparison_hash`、`index_hash`、每个目标文件的 `target_hash`、计划动作和 `plan_hash`。任何输入或目标变化都会使计划失效。

草稿与计划只能写到配置中的工作目录。只有用户在看到计划后说“写入”，才能把完整 `plan_hash` 传给 `apply --confirm-hash`。

## 命令

在 Skill 目录运行：

```text
python -X utf8 scripts/retrospective_store.py init --vault <知识库>
python -X utf8 scripts/retrospective_store.py compare --vault <知识库> --draft <草稿> --output <比较结果>
python -X utf8 scripts/retrospective_store.py plan --vault <知识库> --draft <草稿> --comparison <比较结果> --output <计划>
python -X utf8 scripts/retrospective_store.py apply --vault <知识库> --plan <计划> --confirm-hash <完整哈希>
python -X utf8 scripts/retrospective_store.py search --vault <知识库> --query <任务描述> --limit 5
python -X utf8 scripts/retrospective_store.py validate --vault <知识库>
python -X utf8 scripts/retrospective_store.py rebuild-index --vault <知识库>
```

所有命令以 JSON 输出结果，以中文输出错误。`plan` 不写 Obsidian；`apply` 才执行备份、原子替换、索引更新和写后验证。
