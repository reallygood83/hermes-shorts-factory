# Hermes 쇼츠 공장

한국어 숏폼 연출용 Hermes 프로필이다. 이미 동작하는 Hermes에 이 저장소를 맡기면, 기본 페르소나는 둔 채 `shorts-factory` 프로필만 만든다.

음성은 ElevenLabs가 아니다. 기본값은 xAI Grok TTS(`grok-tts`, `POST https://api.x.ai/v1/tts`)다. Claude와 Codex에는 음성 API가 없고, 채팅 로그인으로 음성을 호출하지 않는다. 비교는 [docs/tts.md](docs/tts.md)에 있다.

## Hermes에 붙여넣을 문장

```text
이 비공개 저장소를 읽고 shorts-factory 프로필만 설치해 줘. 기본 프로필의 SOUL.md, config.yaml, .env, auth.json은 읽어서 복사하거나 수정하지 마.
저장소: https://github.com/reallygood83/hermes-shorts-factory
이 호스트에 저장소를 받을 git 인증이 이미 있어야 한다. 토큰이나 키를 채팅에 붙이지 마.
clone한 뒤 설치기를 검토하고 먼저 dry-run을 실행해.
python3 scripts/install_profile.py --dry-run
출력이 기본 프로필을 건드리지 않으면 적용해.
python3 scripts/install_profile.py --apply
연다.
hermes -p shorts-factory chat
```

비공개 저장소다. Hermes가 돌아가는 컴퓨터에 GitHub 인증이 이미 있어야 한다. SSH 키, `gh auth`, 또는 자격 증명 헬퍼 중 하나면 된다. 인증이 없으면 clone이 실패하고, 설치기는 그 실패를 키 입력으로 우회하지 않는다.

직접 설치할 때는 체크아웃 안에서 같은 두 명령을 쓴다. `hermes`가 PATH에 있고 프로필이 아직 없으면 적용 단계가 아래 공식 명령을 호출한다. 그 명령이 실패하면 `python3 scripts/install_profile.py --apply --method file`로 같은 소유 파일만 복사한다.

```text
hermes profile install <체크아웃 경로> --name shorts-factory --alias -y
```

그때만 셸 별칭 `shorts-factory chat`이 생긴다. 공식 갱신은 `hermes profile update shorts-factory`다.

## 프로필을 여는 방법

```text
hermes profile list
hermes -p shorts-factory chat
```

채팅 모델은 이 프로필 안에서 고른다. 설치기는 기본 프로필의 모델을 복사하지 않는다.

```text
hermes -p shorts-factory model
```

Desktop Bot Mode의 실행 중인 봇을 원격으로 만들지 않는다. 설치 결과는 `~/.hermes/profiles/shorts-factory` 프로필이다. canonical Bot Chat과 `ui_meta.hermes-bots`는 Desktop이 관리하고, 빈 마커만 넣어도 설치 전체의 `message_agent` 조건이 바뀐다. 그 마커는 쓰지 않는다. 헤드리스에서 Bot Chat이 필요할 때 사용자가 직접 연다.

```text
hermes -p shorts-factory chat -c "Bot Chat" --create-if-missing
```

이 명령은 Hermes 세션을 시작한다. 자세한 한계는 [docs/limitations.md](docs/limitations.md).

## 빠른 시작

네트워크와 결제 없이 예시 영상을 만들 수 있다. 예시의 음성은 자리표시 톤이며 Grok 음성이 아니다.

```text
python3 scripts/doctor.py
cp -a examples/smoke /tmp/shorts-smoke
python3 scripts/pipeline.py approve-script /tmp/shorts-smoke
python3 scripts/pipeline.py render /tmp/shorts-smoke
python3 scripts/pipeline.py validate /tmp/shorts-smoke
```

`/tmp/shorts-smoke/output/final.mp4`가 9:16 1080x1920, 6초짜리다. 첫 3초는 훅 자막이다.

새 작품은 기본 음성이 xAI다.

```text
python3 scripts/pipeline.py init ~/shorts/one --topic "주제"
```

대본 `script.md`를 고친 뒤 사용자에게 한 번만 보여주고 `approve-script`를 받는다. 유료 내레이션은 추가로 `approve-paid`, 프로필 `.env`의 `XAI_API_KEY`, 그리고 `SHORTS_FACTORY_ALLOW_PAID_TTS=1`이 있어야 한다. 하나라도 없으면 호출하지 않는다. 게시는 `approve-publish` 뒤에도 업로드하지 않고 로컬 묶음만 만든다.

## 의존성

`python3 scripts/doctor.py`는 ffmpeg, ffprobe, 한글 폰트, Manim, API 키를 검사만 한다. `python`만 있는 환경이면 그 이름으로 같은 스크립트를 실행한다.

- Debian/Ubuntu: `sudo apt-get install ffmpeg`. 한글 폰트가 없으면 Noto Sans CJK를 직접 설치한다.
- macOS: `brew install ffmpeg`
- Windows: `winget install Gyan.FFmpeg`

Manim은 선택이다. 자동으로 설치하지 않는다. 장면 초안은 `examples/manim/hook_card.py`다. Manim Community quickstart의 실행 형태는 `manim -ql hook_card.py HookCard`이고, 이 저장소는 그 명령을 실행하지 않는다. rea-video도 번들하지 않는다. 프로젝트에 `breakdown.json` 경로가 있을 때만 구조 요약에 넣는다.

## 테스트

```text
python3 -m unittest discover -s tests -v
```

테스트는 소켓을 열지 않는다. ffmpeg가 없으면 MP4 테스트만 건너뛴다.

## 문서

- [docs/architecture.md](docs/architecture.md)
- [docs/tts.md](docs/tts.md)
- [docs/limitations.md](docs/limitations.md)
- [skills/shorts-factory/SKILL.md](skills/shorts-factory/SKILL.md)
