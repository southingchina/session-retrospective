# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

Ordnet Belege aus der Zusammenarbeit mit KI in einer durchsuchbaren lokalen Erfahrungsbibliothek. Der Codex-Skill und das Python-Werkzeug auf Basis der Standardbibliothek unterscheiden Entwürfe, geprüfte Erkenntnisse, Verknüpfungen und Konflikte. Vor dem Schreiben werden vorhandene Notizen verglichen und ein an einen Hash gebundener Schreibplan bestätigt. Enthalten sind reine Leseabfragen, Index-Neuaufbau, Sicherungen und Belegvorlagen.

## Voraussetzungen

Python 3.10+

## Konfiguration und Einstiegspunkte

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## Installation und Verwendung

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


## Umfang und Einschränkungen

Setzen Sie vor der Skill-Installation vault_root und work_root in assets/config.json auf eigene absolute Pfade. Die mitgelieferten relativen Pfade dienen nur als Beispiel. Rufen Sie $session-retrospective ausdrücklich auf; der Skill startet nicht nach jeder Aufgabe. Die semantische Prüfung übernimmt der aufrufende Assistent. Das Repository enthält keinen Modelldienst und garantiert keine korrekte Ursachenanalyse. Veröffentlicht werden Vorlagen und synthetische Tests, keine echten Gespräche oder privaten Obsidian-Daten.

## Prüfstand

2026-10-24 · Python: 40 ✓ / 1 skip

## Lizenz und Herkunft

[MIT](LICENSE)

Dies sind Sprachfassungen der Dokumentation. Oberflächen, CLI-Ausgaben und ausführbare Pakete folgen weiterhin der aktuellen Implementierung.

[Vollständige chinesische Referenz](README.zh-CN.md) · [Pflege der Sprachfassungen](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — Reproduzierbare Probleme mit synthetischen Daten melden. Zugangsdaten und private Informationen aus Protokollen entfernen.
