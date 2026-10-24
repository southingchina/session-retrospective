# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

AI との共同作業で得た証拠を、検索できるローカルな経験ライブラリに整理します。Codex Skill と Python 標準ライブラリのツールが、草稿、検証済みの知見、関連、矛盾を区別します。既存ノートとの比較後にハッシュ付き書き込み計画を提示し、確認後に書き込みます。読み取り専用検索、索引の再構築、バックアップ、証拠テンプレートも含みます。

## 必要な環境

Python 3.10+

## 設定とエントリーポイント

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## 導入と使用方法

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


## 公開範囲と制限

Skill を導入する前に、assets/config.json の vault_root と work_root を自分の絶対パスに変更してください。同梱の相対パスはデモ用です。$session-retrospective を明示的に呼び出します。各タスクの終了時には自動実行されません。意味の判断は呼び出す AI が担当し、原因推定の正しさを保証するモデルサービスは含まれません。実際の会話や個人の Obsidian 保管庫は公開していません。

## 検証記録

2026-10-24 · Python: 40 ✓ / 1 skip

## ライセンスと出典

[MIT](LICENSE)

これらは文書の言語版です。アプリ画面、CLI 出力、実行ファイルは現在の実装に従います。

[中国語の詳細リファレンス](README.zh-CN.md) · [言語版の保守方針](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — 再現できる問題は合成データで報告し、ログの認証情報や個人情報を除いてください。
