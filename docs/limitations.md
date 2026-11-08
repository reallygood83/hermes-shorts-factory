# 한계

## 프로필과 Desktop 봇

설치 결과는 Hermes 프로필이다. CLI에서는 아래가 그 에이전트다.

```text
hermes -p shorts-factory chat
```

Bot Mode 문서는 봇이 프로필이라고 말한다. 동시에, canonical Bot Chat이 되려면 세션 제목이 정확히 `Bot Chat`이고, 설치 안 어떤 프로필엔가 `profile.yaml`의 `ui_meta.hermes-bots` 블록이 있어야 한다. 그 블록을 쓰는 CLI 명령은 없다고 같은 문서가 말한다. 빈 블록도 설치 전체를 Bot-Mode-managed로 표시해서 `message_agent` 게이트에 영향을 준다.

그래서 이 설치기는 `ui_meta`를 쓰지 않고, `hermes -p shorts-factory chat -c "Bot Chat" --create-if-missing`도 실행하지 않는다. 그 명령은 사용자가 Bot Chat을 원할 때 직접 연다. Desktop에서 New Agent로 봇을 만드는 동작은 Desktop UI이며, 이 저장소가 원격으로 실행 중인 Desktop 봇을 만들지 않는다.

`--alias`는 `hermes profile install`이 만든다. 파일 복사 방식은 별칭 스크립트를 만들지 않으므로 `hermes -p shorts-factory chat`을 쓴다.

`config.yaml`은 첫 설치 뒤에 유지된다. 채팅 모델은 일부러 비워 두었다. 프로필 안에서 `hermes -p shorts-factory model`로 고른다. 기본 프로필의 모델을 복사하지 않는다.

OAuth는 프로필에 복제하지 않는다. Hermes 문서도 Anthropic, Codex, xAI OAuth 갱신 토큰은 복제하면 한쪽 갱신이 다른 쪽을 취소할 수 있다고 한다. 음성은 별도 `XAI_API_KEY`다.

## Hermes 0.23.0에서 확인한 것

공식 설치 스크립트 `install.sh --non-interactive --skip-browser --skip-computer-use`로 CLI v0.23.0 (2026.9.24)을 이 VM에 설치했다. 임시 `HERMES_HOME`에서 다음이 통과했다.

- dry-run은 프로필 디렉터리를 만들지 않는다.
- `hermes profile install <체크아웃> --name shorts-factory --alias -y`가 프로필을 만든다.
- `hermes profile list`에 `Shorts Factory (shorts-factory)`와 배포 `shorts-factory@1.0.0`이 보이고, ◆default는 기본 프로필에 남는다.
- `hermes -p shorts-factory profile`의 Active profile이 shorts-factory다.
- 다시 적용하면 `hermes profile update shorts-factory -y`가 되고, 기본 SOUL과 다른 프로필, 프로필 `.env`는 유지된다.
- `profile.yaml`은 `display_name`만 있고 `ui_meta`는 없다.

`hermes gateway ensure`는 로컬 `127.0.0.1` 런타임을 ready로 만들었고 메시징 플랫폼은 없었다. 그 다음에도 아래는 실패했다.

```text
hermes -p shorts-factory chat --cli -c "Bot Chat" --create-if-missing
No session found matching 'Bot Chat' and a new titled session could not be created.
```

게이트웨이 로그는 `invalid policy` (`gateway/session_policy.py`의 `policy.model`이 비어 있음)를 `storage_unavailable`로 감싼다. Desktop 플러그인 `notifyBotOpenFailure`는 그 문자열을 `Could not open Shorts Factory’s chat`의 detail로 보여 주고, 버튼은 항상 Open Gateways다. 빈 모델이 유일한 sqlite 고장은 아니다. 모델이 이미 있는데도 같은 코드가 나오면 `hermes gateway ensure` 이후에도 남는지 본다.

수리는 `python3 scripts/repair_chat.py`다. 질문은 기본 Hermes `config.yaml`의 대화 모델을 쓸지, 다른 대화 모델 이름을 입력할지다. `api_key`와 `.env`, `auth.json`은 기본 프로필에서 복사하지 않는다. 세션 DB는 지우지 않는다. 이 클라우드 VM은 사용자 Mac의 Desktop을 열 수 없으므로, 수리 명령은 그 컴퓨터에서 실행해야 한다.

Desktop 로스터의 아바타와 `ui_meta.hermes-bots`는 이 수리가 만들지 않는다.

배포 `config.yaml`에는 `_config_version`을 넣지 않았다. 공식 예제는 Hermes가 그 키를 관리하므로 다른 설정으로 복사하지 말라고 한다. 0.23.0은 이 파일에 대해 버전 12 이전이라는 마이그레이션 경고를 낸 뒤에도 프로필 설치 자체는 끝냈다.

## 아직 호출하지 않은 것

- xAI, OpenAI, Anthropic 유료 또는 로그인 호출. 한국어 발음도 듣지 않았다.
- Manim. `python3 -c "import manim"`은 `ModuleNotFoundError`다. 큰 의존성을 설치하지 않았고 장면 렌더는 없다. `python3 scripts/doctor.py`가 선택 설치 안내만 한다.
- rea-video. `breakdown.json`이 있을 때만 요약하고, 실행했다고 적지 않는다.

## 안전

게시 승인은 로컬 JSON 묶음만 허용한다. 업로드 함수는 없다. 도구 권한을 열어 주는 설정 키는 쓰지 않는다.
