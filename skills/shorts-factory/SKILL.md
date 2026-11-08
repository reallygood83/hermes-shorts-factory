---
name: shorts-factory
description: 일반 시청자용 한국어 숏폼을 주제에서 로컬 final.mp4까지 만든다. 대본 승인, 유료 TTS 승인, 게시 승인을 따로 지키고 xAI Grok TTS만 기본 음성으로 쓴다.
version: 1.0.0
platforms: [macos, linux, windows]
hermes:
  tags: [video, shorts, korean, tts]
  category: creative
  requires_toolsets: [terminal]
---

# Shorts Factory

이 스킬은 `shorts-factory` 프로필의 연출 절차다. 기본 프로필의 SOUL과 설정을 바꾸지 않는다.

## 산출물

주제 또는 참고 URL 하나에서 로컬 `final.mp4` 하나. 기본 화면은 9:16 1080x1920이다. 프로젝트의 `aspect`가 `16:9`이면 1920x1080이다.

## 절대 규칙

- 참고 영상에서는 구조만 적는다. 화면, 음악, 대사를 재사용하지 않는다.
- `real_person_likeness`는 false다. 실존 인물의 입모양이나 목소리로 하지 않은 말을 만들지 않는다.
- 학생이나 개인 정보를 넣지 않는다.
- 대본 승인, 유료 음성 승인, 게시 승인은 서로 대체되지 않는다.
- 승인된 provider, model, voice_id, language가 바뀌면 다시 승인받는다. 실패했다고 다른 음성으로 넘기지 않는다.
- 기본 음성은 xAI `grok-tts` (`POST https://api.x.ai/v1/tts`, 언어 `ko`, 공개 보이스 `eve`)다. `XAI_API_KEY`가 있고 두 승인과 `SHORTS_FACTORY_ALLOW_PAID_TTS=1`이 있을 때만 호출한다.
- Claude와 Codex에는 음성 API가 없다. ElevenLabs는 쓰지 않는다. OpenAI `gpt-4o-mini-tts`는 프로젝트에 명시된 경우에만 쓴다.
- 오프라인 톤은 프로젝트가 `offline`일 때만 쓴다. xAI 실패의 대체재가 아니다.
- 게시는 로컬 묶음 파일만 만든다. 업로드하지 않는다.
- ffmpeg와 Manim을 자동으로 설치하지 않는다. `python3 scripts/doctor.py`만 실행한다.

## 절차

1. 프로젝트 디렉터리를 만든다. `python3 -m shorts_factory.pipeline init <dir> --topic "..."` 또는 기존 `project.json`.
2. 참고 URL이 있으면 구조 메모만 `analysis.json`에 남긴다. `python3 -m shorts_factory.pipeline analyze <dir>`. rea-video는 `rea_video_breakdown` 경로의 JSON이 있을 때만 요약한다. 바이너리가 있다고 가정하지 않는다.
3. `script.md`에 `# 훅`, `# 내레이션`, `# 샷`을 쓴다. 훅은 첫 3초다.
4. 사용자에게 대본 전문을 보여주고, 그 한 번만 `python3 -m shorts_factory.pipeline approve-script <dir>`.
5. 유료 음성이면 견적 성격(xAI 공개 단가 $15 / 1M chars)을 말하고, 따로 `approve-paid`를 받은 뒤에만 `narrate`.
6. 장면 렌더는 `delegate_task`로 넘긴다. 자식은 부모 도구 권한을 그대로 물려받으며, 호출로 권한을 넓힐 수 없다. goal과 context에 경로, 화면 크기, 대본 해시, 로컬 명령만 적는다. SendToAgent나 미리 아는 봇 ID는 쓰지 않는다.
7. `python3 -m shorts_factory.pipeline render <dir>` 다음 `validate`.
8. 게시 승인이 있고 검증이 통과했을 때만 `publish`. 결과의 `uploaded`는 false다.

## delegate_task

문서화된 형태만 쓴다.

```text
delegate_task(goal="...", context="...")
```

병렬이면 `delegate_task(tasks=[...])`. 자식은 대화 기록을 모른다. 필요한 경로와 제약을 context에 전부 적는다. 유료 `narrate`는 자식에게 맡기지 않고, 승인을 본 뒤 이 프로필에서 실행한다.

## 음성 인증

SuperGrok / xAI OAuth, Codex OAuth, Claude OAuth를 음성 자격으로 읽지 않는다. Hermes 문서에도 구독 베어러가 종량 TTS에서 403이 될 수 있다고 되어 있다. 키는 프로필 `.env`의 `XAI_API_KEY`다. 키 값을 채팅이나 저장소에 쓰지 않는다.

보이스를 바꾸려면 프로젝트 `tts.voice_id`를 고치고 대본 승인을 다시 한다. 환경 변수는 프로젝트에 voice_id가 비어 있을 때만 채운다.

## 열기와 한계

설치가 만드는 것은 `~/.hermes/profiles/shorts-factory` 프로필이다.

```text
hermes -p shorts-factory chat
```

`hermes profile install ... --alias -y`로 설치한 경우에만 `shorts-factory chat` 별칭이 생긴다. Desktop의 canonical Bot Chat과 `ui_meta.hermes-bots`는 Desktop이 쓰며, 빈 마커 하나가 설치 전체의 `message_agent` 게이트를 연다. 이 스킬은 그 마커를 쓰지 않는다. 헤드리스에서 Bot Chat이 필요할 때만 사용자가 문서대로 직접 한다.

```text
hermes -p shorts-factory chat -c "Bot Chat" --create-if-missing
```

이 명령은 Hermes 세션을 연다. 설치기가 대신 실행하지 않는다.
