# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

Transformez les preuves issues d'une collaboration avec l'IA en une bibliothèque locale d'expériences consultable. Le Skill Codex et l'outil Python utilisant la bibliothèque standard distinguent brouillons, enseignements vérifiés, liens et conflits. Ils comparent les notes existantes, présentent un plan d'écriture lié à un hachage et écrivent après confirmation. Recherche en lecture seule, reconstruction de l'index, sauvegardes et modèles de preuves sont inclus.

## Prérequis

Python 3.10+

## Configuration et points d’entrée

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## Installation et utilisation

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


## Périmètre et limites

Avant d'installer le Skill, configurez vault_root et work_root dans assets/config.json avec vos propres chemins absolus. Les chemins relatifs fournis servent à la démonstration. Appelez explicitement $session-retrospective ; il ne se lance pas à la fin de chaque tâche. L'analyse sémantique dépend de l'assistant : ce dépôt ne contient aucun service de modèle et ne garantit pas la justesse d'une cause proposée. Le paquet public ne contient ni conversations réelles ni coffre Obsidian privé.

## Historique de validation

2026-10-24 · Python: 40 ✓ / 1 skip

## Licence et attribution

[MIT](LICENSE)

Il s’agit de versions de la documentation. Interfaces, sorties CLI et exécutables conservent le comportement de l’implémentation actuelle.

[Référence complète en chinois](README.zh-CN.md) · [Politique de maintenance des langues](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — Signalez les problèmes reproductibles avec des données synthétiques. Retirez identifiants secrets et informations privées des journaux.
