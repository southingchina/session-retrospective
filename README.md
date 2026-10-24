# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

Turn evidence from AI collaboration into a searchable local experience library. The Codex Skill and standard-library Python tool separate drafts, verified lessons, links and conflicts; compare existing notes, present a hash-bound write plan, and write only after confirmation. Read-only search, index rebuilding, backups and evidence templates are included.

## Requirements

Python 3.10+

## Configuration and entry points

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## Installation and usage

```shell
git clone https://github.com/southingchina/session-retrospective.git
cd session-retrospective
python scripts/retrospective_store.py init --vault ./example-vault
python scripts/retrospective_store.py search --vault ./example-vault --query "浏览器连接失败"
python scripts/retrospective_store.py --help
```


```shell
python -m unittest discover -s tests -v
```


## Scope and limitations

Set vault_root and work_root in assets/config.json to your own absolute paths before installing the Skill. The bundled relative paths are demonstration settings. Invoke $session-retrospective explicitly; it does not start after every task. An assistant performs the semantic review: this repository contains no model service and cannot establish that a proposed root cause is correct. The public package contains templates and synthetic tests, not actual conversations or a private Obsidian vault.

## Validation record

2026-10-24 · Python: 40 ✓ / 1 skip

## License and attribution

[MIT](LICENSE)

These are documentation editions. Application interfaces, CLI output and executable releases retain the behavior of the current implementation.

[Complete Chinese reference](README.zh-CN.md) · [Language maintenance policy](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — Report a reproducible issue with synthetic data. Remove credentials and private information from logs.
