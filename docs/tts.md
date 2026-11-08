# 음성 제공자

조사일 기준 문서만 적는다. 개발 중 유료 호출은 하지 않았다. 발음 품질은 확인하지 않았다.

내레이션 기본값은 여전히 **xAI Grok TTS**입니다. 온보딩에서 Gemini 음성을 고르면 `gemini-3.8-flash-tts` (`POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash-tts:generateContent`, 보이스 `Kore`)만 사용합니다. 이 모델의 공식 언어 표에 Korean이 있습니다. Hermes 0.23의 내장 기본값 `gemini-2.5-flash-preview-tts`와 `gemini-3.1-flash-tts-preview`는 이름을 직접 고른 경우에만 허용하고, 실패해도 다른 모델로 바꾸지 않습니다. Gemini 음성 API는 대사를 읽습니다. 효과음·음악 엔드포인트는 없어 그 선택은 막히고, 배경은 로컬 원본 톤입니다.

채팅 모델은 음성 모델과 다릅니다. 비어 있으면 Desktop이 `storage_unavailable`를 냅니다. 수리 질문이 기본 Hermes `config.yaml`의 대화 모델을 쓰게 하거나, 사용자가 대화 모델 이름을 입력하게 합니다. `api_key`는 복사하지 않습니다.

## 능력 표

| 제품 | 채팅/코딩과 음성의 관계 | 실제 음성 API | 이 패키지 |
| --- | --- | --- | --- |
| xAI Grok TTS | 채팅 모델과 별도. 제품명 `grok-tts`. 요청 본문에 채팅 모델 필드는 없다. | `POST https://api.x.ai/v1/tts`. 인증 `Authorization: Bearer $XAI_API_KEY`. 언어 `ko` 포함. 기본 보이스 `eve`. | 기본값. 승인 전에는 호출하지 않는다. |
| xAI OAuth (SuperGrok / X Premium+) | Hermes 채팅 제공자 `xai-oauth`. 모델 예 `grok-4.6`. | Hermes는 같은 베어러를 직접 xAI 도구에 재사용한다고 적는다. 스트리밍 TTS 문서는 구독 베어러가 종량 TTS에서 HTTP 403이 될 수 있다고 적는다. | OAuth 토큰을 읽지 않는다. `XAI_API_KEY`가 없으면 실패한다. |
| OpenAI speech | `gpt-4o-mini-tts`는 음성 모델이다. Chat Completions용이 아니다. | `POST https://api.openai.com/v1/audio/speech`. 문서된 모델 `gpt-4o-mini-tts`, 스냅샷 `gpt-4o-mini-tts-2025-12-15`. | 프로젝트에 `openai`라고 적힌 경우에만. `tts-1`, `tts-1-hd`로는 바꾸지 않는다. |
| OpenAI Codex / ChatGPT OAuth | 코딩·채팅 구독이다. | Platform speech를 승인하지 않는다. Hermes OpenAI TTS 키는 `VOICE_TOOLS_OPENAI_KEY` 또는 API 키다. | 토큰을 읽지 않는다. 실패로 닫는다. |
| Anthropic Claude | Messages API `POST /v1/messages`는 텍스트다. | 공식 API 목록에 speech가 없다. 쿡북의 음성 예시는 외부 TTS다. | 실패로 닫는다. URL을 만들지 않는다. |
| ElevenLabs | 해당 없음 | 이 패키지에서 제거했다. | 선택하면 실패한다. |
| 오프라인 톤 | 음성이 아니다. | 로컬 WAV. | 프로젝트가 `offline`일 때만. 장애 대체재가 아니다. |
| Nous Portal TTS | Hermes Tool Gateway의 TTS는 OpenAI TTS다. Grok TTS가 아니다. | 포털 구독. | 선택하지 않는다. |

## xAI에서 확인한 값

- 엔드포인트: `POST https://api.x.ai/v1/tts`
- 필수 필드: `text`, `language`
- `voice_id` 기본값: `eve`
- 문서 예시로 확인한 내장 보이스 ID: `eve`, `ara`, `leo`, `rex`, `sal`. 전체 목록은 `GET /v1/tts/voices`이며 이 저장소를 만드는 동안 호출하지 않았다.
- 언어 열거(REST reference): `auto`, `en`, `ar-EG`, `ar-SA`, `ar-AE`, `bn`, `zh`, `fr`, `de`, `hi`, `id`, `it`, `ja`, `ko`, `pt-BR`, `pt-PT`, `ru`, `es-MX`, `es-ES`, `tr`, `vi`
- 한국어: `ko`가 그 목록에 있다. 샘플을 듣지 못했으므로 발음 품질은 미검증이다.
- 기본 출력: MP3, 24000 Hz, 128000 bps
- 공개 가격(Voice overview): $15.00 / 1M characters
- 커스텀 보이스: xAI 콘솔에서 만든 ID를 프로필 `.env` 또는 프로젝트에만 둔다. 저장소에 적지 않는다.

Hermes 설정 키는 음성 문서의 `tts.xai` 블록만 쓴다. `voice_id`, `language`, `speed`, `auto_speech_tags`, `text_normalization`, `optimize_streaming_latency`, `sample_rate`, `bit_rate`. `auto_speech_tags`는 false다. true면 태그 삽입용 추가 모델 호출이 난다.

## OpenAI speech에서 확인한 값

- 모델 ID `gpt-4o-mini-tts`는 2026년 문서에서 deprecated이며 2027-01-06에 종료된다고 되어 있다. 후속은 Realtime 쪽 `gpt-realtime-2.1-mini`이고, 그 모델은 `/v1/audio/speech`용이 아니라고 같은 페이지가 말한다.
- 그래서 OpenAI는 대체가 아니라, 사용자가 명시할 때만 쓰는 현재 Speech API다.
- 한국어: TTS 가이드는 Whisper 언어 목록을 따르며 그 목록에 Korean이 있다. 목소리는 영어에 최적화되어 있다고 적혀 있다. 품질은 미검증이다.
- Hermes `tts.openai.model` 예시 값은 `gpt-4o-mini-tts`다.

## 승인 없이 막히는 것

`shorts_factory.tts`는 아래가 모두 있기 전에 소켓을 열지 않는다.

1. 대본 승인의 해시와 provider, model, voice_id, language가 현재 프로젝트와 같다.
2. 유료 제공자면 별도의 paid_credits 승인이 같은 음성 선택과 같다.
3. `SHORTS_FACTORY_ALLOW_PAID_TTS=1`
4. 해당 제공자의 API 키

하나라도 없으면 실패한다. xAI 오류를 OpenAI로 넘기지 않는다.

## 출처

- https://docs.x.ai/developers/model-capabilities/audio/text-to-speech
- https://docs.x.ai/developers/rest-api-reference/inference/voice
- https://docs.x.ai/developers/models/grok-tts
- https://docs.x.ai/developers/model-capabilities/audio/voice
- https://hermes-agent.nousresearch.com/docs/user-guide/features/tts
- https://hermes-agent.nousresearch.com/docs/developer-guide/streaming-tts
- https://hermes-agent.nousresearch.com/docs/guides/xai-grok-oauth
- https://platform.openai.com/docs/guides/text-to-speech
- https://developers.openai.com/api/docs/models/gpt-4o-mini-tts
- https://platform.claude.com/docs/en/api/overview
