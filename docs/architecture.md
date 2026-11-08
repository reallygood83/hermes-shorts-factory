# 구조

이 저장소는 Hermes 프로필 배포물이다. 설치 대상은 `~/.hermes/profiles/shorts-factory` 하나다. 기본 홈(`~/.hermes/SOUL.md`, `config.yaml`, `.env`, `auth.json`)과 다른 프로필 디렉터리는 설치 대상이 아니다.

```text
distribution.yaml     배포 이름, 버전, 필요한 환경 변수
SOUL.md               이 프로필의 말투와 금지
config.yaml           tts.provider: xai 만 고정. 채팅 모델은 비워 둔다
profile.yaml          display_name
skills/shorts-factory 연출 절차
shorts_factory/       승인, 설치, 음성, 로컬 렌더
examples/smoke/       네트워크 없는 예시 프로젝트
```

공식 설치 명령은 Hermes 프로필 배포 문서의 것이다.

```text
hermes profile install <checkout> --name shorts-factory --alias -y
```

`scripts/install_profile.py`는 그 명령을 검토한 뒤 호출하거나, `hermes`가 없으면 같은 소유 파일을 프로필 디렉터리에 복사한다. 복사는 `config.yaml`, `SOUL.md`, `profile.yaml`이 있는 디렉터리만 프로필로 인정한다는 문서에 맞춘다. Desktop 내부 DB는 쓰지 않는다.

연출 에이전트는 스킬을 따른다. 렌더와 장면 준비는 `delegate_task`로 자식에게 넘긴다. 자식은 부모의 도구 집합을 물려받는다. 유료 내레이션은 승인 저장소를 통과하는 `shorts_factory.tts`만 호출할 수 있다.

로컬 파이프라인은 LLM이 아니다. 대본 초안, 승인 상태, ffmpeg 조립, 검증을 담당한다. 창작 문장은 Hermes가 `script.md`에 쓴다.

화면 기본값은 9:16 1080x1920이다. `aspect: "16:9"`이면 1920x1080만 허용한다.

## 출처

- https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions
- https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation
- https://hermes-agent.nousresearch.com/docs/user-guide/bot-mode
