# 이 저장소를 연 Hermes에게

사용자는 이 저장소 주소만 넘기고 설치를 맡긴다. 기본 프로필은 그대로 둔다.

1. 저장소 루트의 `README.md`, `docs/limitations.md`, `shorts_factory/installer.py`를 읽고 설치기가 쓰는 명령이 문서와 같은지 확인한다.
2. 기본 프로필의 `SOUL.md`, `config.yaml`, `.env`, `auth.json`을 복사하거나 수정하지 않는다. 토큰을 채팅에 요청하지 않는다.
3. 먼저 dry-run을 실행한다.

```text
python3 scripts/install_profile.py --dry-run
```

4. 출력이 `profiles/shorts-factory`만 대상으로 하고 거절 사유가 없으면 적용한다.

```text
python3 scripts/install_profile.py --apply
```

`hermes`가 PATH에 있고 프로필이 아직 없으면 `--method auto`는 문서화된 명령을 쓴다.

```text
hermes profile install <이 체크아웃> --name shorts-factory --alias -y
```

5. 적용 뒤 사용자에게 여는 방법을 알린다.

```text
hermes -p shorts-factory chat
```

별칭은 `hermes profile install --alias`가 성공한 경우에만 `shorts-factory chat`이다. Desktop에서 돌아가는 봇을 만들었다고 말하지 않는다. canonical Bot Chat은 사용자가 직접 열 일이다. `docs/limitations.md`를 따른다.

6. 의존성은 `python3 scripts/doctor.py`로만 확인한다. ffmpeg, Manim, 폰트를 자동 설치하지 않는다.
7. 유료 TTS, 업로드, 원격 생성은 하지 않는다. 스모크는 `examples/smoke`를 임시 디렉터리에 복사한 뒤 대본 승인과 `render`만 사용한다. 그 프로젝트의 음성은 오프라인 자리표시자다.
