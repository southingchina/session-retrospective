# Session Retrospective

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Português (Brasil)](README.pt-BR.md)

AI 협업에서 얻은 증거를 검색 가능한 로컬 경험 라이브러리로 정리합니다. Codex Skill과 Python 표준 라이브러리 도구는 초안, 검증된 교훈, 연결, 충돌을 구분합니다. 기존 노트를 비교한 뒤 해시가 연결된 쓰기 계획을 제시하고 확인 후 저장합니다. 읽기 전용 검색, 색인 재구축, 백업 및 증거 템플릿도 제공합니다.

## 필요 환경

Python 3.10+

## 설정 및 진입점

`assets/config.json: vault_root, work_root`, `SKILL.md`, `$session-retrospective`

## 설치 및 사용

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


## 공개 범위와 제한

Skill 설치 전에 assets/config.json의 vault_root와 work_root를 자신의 절대 경로로 설정하세요. 포함된 상대 경로는 데모용입니다. $session-retrospective를 명시적으로 호출하며 모든 작업 종료 시 자동 실행되지 않습니다. 의미 판단은 호출하는 AI가 수행합니다. 모델 서비스나 근본 원인 판단의 정확성을 보장하는 기능은 포함되지 않습니다. 실제 대화와 개인 Obsidian 보관함은 공개 패키지에 없습니다.

## 검증 기록

2026-10-24 · Python: 40 ✓ / 1 skip

## 라이선스 및 출처

[MIT](LICENSE)

프로젝트 문서의 언어별 버전입니다. 앱 화면, CLI 출력과 실행 파일은 현재 구현을 따릅니다.

[중국어 상세 참고 문서](README.zh-CN.md) · [언어 문서 유지 관리 정책](docs/LOCALIZATION.md)

[Issues](https://github.com/southingchina/session-retrospective/issues) — 재현 가능한 문제는 합성 데이터로 보고하고 로그의 자격 증명과 개인 정보를 제거하세요.
