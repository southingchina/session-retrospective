# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

Transforma evidências da colaboração com IA em uma biblioteca local de experiências pesquisável. O Skill do Codex e a ferramenta Python, baseada na biblioteca padrão, distinguem rascunhos, lições verificadas, relações e conflitos. Comparam notas existentes, apresentam um plano de gravação vinculado a um hash e gravam após a confirmação. Incluem busca somente leitura, reconstrução do índice, backups e modelos de evidências.

## Requisitos

Python 3.10+

## Configuração e pontos de entrada

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## Instalação e uso

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


## Escopo e limitações

Antes de instalar o Skill, defina vault_root e work_root em assets/config.json com seus próprios caminhos absolutos. Os caminhos relativos incluídos são exemplos. Invoque $session-retrospective explicitamente; ele não inicia ao fim de toda tarefa. A análise semântica é feita pelo assistente: este repositório não inclui serviço de modelos nem garante que a causa sugerida esteja correta. O pacote público contém modelos e testes sintéticos, sem conversas reais ou cofre privado do Obsidian.

## Registro de validação

2026-10-24 · Python: 40 ✓ / 1 skip

## Licença e créditos

[MIT](LICENSE)

São versões da documentação. Interfaces, saídas CLI e executáveis mantêm o comportamento da implementação atual.

[Referência completa em chinês](README.zh-CN.md) · [Política de manutenção dos idiomas](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — Relate problemas reproduzíveis com dados sintéticos. Remova credenciais e informações privadas dos logs.
