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

## 하지 않은 검증

- 이 VM에 `hermes` CLI가 없어 `hermes profile install`의 실제 바이너리는 실행하지 않았다. 인자 목록은 문서와 스텁으로 검사했다.
- xAI, OpenAI, Anthropic에 유료 또는 인증 호출을 하지 않았다.
- 한국어 음성 품질은 듣지 않았다. `ko`는 xAI REST 언어 열거에 있다.
- Manim은 설치되어 있지 않다. 장면 파일만 있고 실행하지 않는다.
- rea-video 실행 파일은 번들하지 않는다. `breakdown.json`이 있을 때만 키 개수를 요약하고, 실행했다고 적지 않는다.
- Desktop 로스터에 줄이 바로 나타나는지는 이 환경에서 확인하지 못했다.

## 안전

게시 승인은 로컬 JSON 묶음만 허용한다. 업로드 함수는 없다. 도구 권한을 열어 주는 설정 키는 쓰지 않는다.
