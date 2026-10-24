# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

Convierte las evidencias de colaboración con IA en una biblioteca local de experiencias que se puede consultar. El Skill de Codex y la herramienta Python, basada en la biblioteca estándar, distinguen borradores, lecciones verificadas, relaciones y conflictos. Comparan las notas existentes, presentan un plan de escritura vinculado a un hash y escriben tras su confirmación. Incluyen búsquedas de solo lectura, reconstrucción del índice, copias de seguridad y plantillas de evidencias.

## Requisitos

Python 3.10+

## Configuración y puntos de entrada

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## Instalación y uso

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


## Alcance y limitaciones

Antes de instalar el Skill, configura vault_root y work_root en assets/config.json con tus propias rutas absolutas. Las rutas relativas incluidas son de demostración. Invoca $session-retrospective explícitamente; no se ejecuta al finalizar cada tarea. La revisión semántica depende del asistente: el repositorio no incluye un servicio de modelos ni garantiza que la causa propuesta sea correcta. El paquete público contiene plantillas y pruebas sintéticas, sin conversaciones reales ni una bóveda privada de Obsidian.

## Registro de validación

2026-10-24 · Python: 40 ✓ / 1 skip

## Licencia y atribución

[MIT](LICENSE)

Son versiones de la documentación. Las interfaces, salidas CLI y ejecutables mantienen el comportamiento de la implementación actual.

[Referencia completa en chino](README.zh-CN.md) · [Política de mantenimiento de idiomas](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — Comunica problemas reproducibles con datos sintéticos. Elimina credenciales e información privada de los registros.
