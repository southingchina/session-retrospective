# Session Retrospective · AI 协作复盘

把一次 AI 协作中的错误、证据和改进整理成可检索的本地经验库。提供 Codex Skill 和纯 Python 存储工具：**先生成草稿与比较结果，再展示带哈希的写入计划，确认后写入 Obsidian**。

## 能做什么

- 区分已验证经验、候选经验、关联、冲突及失效条件。
- 比较已有内容，生成明确的新增/合并/关联计划；相似度不直接决定合并。
- 使用完整计划哈希确认写入，并检测过期计划、路径越界与内容变化。
- 只读检索、索引重建、写入后校验及备份。
- 提供 MOC、证据账本、原子草稿和未决问题模板。

## 要求与快速开始

Python 3.10+，仅标准库；Markdown 目录即可使用，Obsidian 是可选的阅读界面。以下命令从仓库根目录执行，只创建示例库：

```shell
git clone https://github.com/southingchina/session-retrospective.git
cd session-retrospective
python scripts/retrospective_store.py init --vault ./example-vault
python scripts/retrospective_store.py search --vault ./example-vault --query "浏览器连接失败"
python scripts/retrospective_store.py --help
```

### 在 Codex 中使用

将本仓库复制到你的 Codex skills 目录下的 `session-retrospective/`。使用前将 `assets/config.json` 的 `vault_root`、`work_root` 改为你自己的绝对路径；随仓库的相对路径只用于演示。当前 Skill 默认手动调用，可说“复盘一下”“总结弯路”“查经验：浏览器连接”，也可点名 `$session-retrospective`。

主要命令：`init`、`search`、`compare`、`plan`、`apply`、`validate`、`rebuild-index`。每条命令的参数见 `--help`。`apply` 必须给出已展示计划的完整 `--confirm-hash`；示例库、草稿和真实知识库请分开放置。

## 项目结构

`SKILL.md` 为助手工作流；`scripts/retrospective_store.py` 为确定性存储层；`assets/` 为模板与示例配置；`references/` 定义数据协议；`tests/` 使用临时目录验证行为。

## 验证与限制

```shell
python -m unittest discover -s tests -v
```

公开版包含脱敏测试和空白模板，不含真实对话、用户经验库或交接快照。草稿提炼和灰区语义判断由调用它的助手完成，本项目不包含模型服务，也不保证自动判断根因正确。敏感字段清理是辅助保护，公开任何真实材料前仍需检查具体内容。

## 来源与许可证

从作者日常 AI 协作流程中提取的独立工具与 Skill，公开版做了路径配置与示例数据隔离。MIT；详见 LICENSE。欢迎通过 GitHub Issues 提交可复现问题，请只附合成数据。
