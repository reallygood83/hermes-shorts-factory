"""Ask-style onboarding for the shorts-factory chat model and speech keys.

The first question is a choice, not a hidden default: use the default Hermes
chat model, type a different chat model, or cancel. Keys are masked and are
never placed on the command line.
"""

from __future__ import annotations

import getpass
import os
import sys
from collections.abc import Callable

from shorts_factory.repair import OnboardRequest, OnboardResult, RepairError
from shorts_factory.tts import GEMINI_TTS_DEFAULT, GEMINI_TTS_MODELS, GEMINI_TTS_VOICE

InputFn = Callable[[str], str]
SecretFn = Callable[[str], str]


def decide_chat_model(
    choice: str,
    request: OnboardRequest,
    typed_provider: str = "",
    typed_model: str = "",
) -> tuple[str, str]:
    if choice == "cancel":
        raise RepairError("cancelled")
    if choice == "default":
        if not request.default_model:
            raise RepairError("기본 Hermes 대화 모델이 없어 그 선택을 쓸 수 없습니다.")
        return request.default_provider, request.default_model
    if choice == "custom":
        if not typed_model.strip():
            raise RepairError("직접 입력에는 대화 모델 이름이 필요합니다.")
        return typed_provider.strip(), typed_model.strip()
    raise RepairError("채팅 모델 질문은 default, custom, cancel 중 하나여야 합니다.")


def headless_prompt(
    request: OnboardRequest,
    input_fn: InputFn | None = None,
    secret_fn: SecretFn | None = None,
) -> OnboardResult:
    ask = input_fn or input
    secret = secret_fn or getpass.getpass
    print("쇼츠 공장 온보딩")
    print("채팅 모델과 음성 키는 별개입니다. 효과음·BGM은 Gemini로 만들지 않고 로컬 원본 톤만 씁니다.")
    if request.default_model:
        label = f"{request.default_provider} {request.default_model}".strip()
        print(f"기본 Hermes 채팅 모델: {label}")
        print("1) 이 기본 모델을 shorts-factory 채팅에 사용")
        print("2) 다른 대화 모델 입력")
        print("3) 취소")
        picked = ask("선택 [1/2/3]: ").strip()
        mapping = {"1": "default", "2": "custom", "3": "cancel"}
    else:
        print("기본 Hermes config.yaml에 대화 모델이 없습니다.")
        print("1) 대화 모델 직접 입력")
        print("2) 취소")
        picked = ask("선택 [1/2]: ").strip()
        mapping = {"1": "custom", "2": "cancel"}
    choice = mapping.get(picked, "")
    if choice == "cancel" or not choice:
        return OnboardResult(cancelled=True)
    typed_provider = ""
    typed_model = ""
    if choice == "custom":
        typed_provider = ask("채팅 provider (비우면 모델 이름만 저장): ").strip()
        typed_model = ask("대화 모델 이름: ").strip()
    try:
        provider, model = decide_chat_model(choice, request, typed_provider, typed_model)
    except RepairError as exc:
        if str(exc) == "cancelled":
            return OnboardResult(cancelled=True)
        raise
    print("내레이션은 무엇을 쓸까요? 효과음 API는 선택지에 없습니다.")
    print("1) xAI Grok TTS 유지")
    print("2) Gemini 음성 추가")
    print("3) 음성 설정은 바꾸지 않음")
    speech_pick = ask("선택 [1/2/3]: ").strip()
    tts_provider = {"1": "xai", "2": "gemini"}.get(speech_pick, "")
    tts_model = ""
    tts_voice = ""
    gemini_key: str | None = None
    xai_key: str | None = None
    if tts_provider == "gemini":
        tts_model = GEMINI_TTS_DEFAULT
        tts_voice = GEMINI_TTS_VOICE
        print(f"Gemini 음성 모델 {tts_model}, 보이스 {tts_voice}. 다른 음성 모델로 바꾸지 않습니다.")
        entered = secret("Gemini API 키 (빈 입력은 기존 값 유지): ")
        gemini_key = entered.strip() or None
    elif tts_provider == "xai":
        tts_model = "grok-tts"
        tts_voice = "eve"
        entered = secret("xAI API 키 (빈 입력은 기존 값 유지): ")
        xai_key = entered.strip() or None
    open_answer = ask("프로필 config.yaml을 편집기로 열까요? [y/N]: ").strip().lower()
    return OnboardResult(
        cancelled=False,
        chat_provider=provider,
        chat_model=model,
        tts_provider=tts_provider,
        tts_model=tts_model,
        tts_voice=tts_voice,
        gemini_api_key=gemini_key,
        xai_api_key=xai_key,
        open_config=open_answer in {"y", "yes"},
        local_tone=True,
    )


def _display_available() -> bool:
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def gui_prompt(request: OnboardRequest) -> OnboardResult:
    """Optional Tk window. tkinter is not required; callers fall back to questions."""

    # Optional GUI toolkit. Headless hosts and the test suite use headless_prompt.
    import tkinter as tk
    from tkinter import ttk

    outcome: dict[str, OnboardResult] = {}
    root = tk.Tk()
    root.title("쇼츠 공장 온보딩")
    frame = ttk.Frame(root, padding=12)
    frame.grid()
    ttk.Label(
        frame,
        text="채팅 모델을 고르세요. 음성 키와 효과음은 이 질문과 따로입니다.",
    ).grid(row=0, column=0, columnspan=2, sticky="w")
    mode = tk.StringVar(value="default" if request.default_model else "custom")
    if request.default_model:
        ttk.Radiobutton(
            frame,
            text=f"기본 Hermes 모델 사용 ({request.default_provider} {request.default_model})".strip(),
            variable=mode,
            value="default",
        ).grid(row=1, column=0, columnspan=2, sticky="w")
    ttk.Radiobutton(frame, text="다른 대화 모델 입력", variable=mode, value="custom").grid(
        row=2, column=0, columnspan=2, sticky="w"
    )
    provider_var = tk.StringVar()
    model_var = tk.StringVar()
    ttk.Label(frame, text="provider").grid(row=3, column=0, sticky="w")
    ttk.Entry(frame, textvariable=provider_var, width=40).grid(row=3, column=1)
    ttk.Label(frame, text="대화 모델").grid(row=4, column=0, sticky="w")
    ttk.Entry(frame, textvariable=model_var, width=40).grid(row=4, column=1)
    speech = tk.StringVar(value="keep")
    ttk.Label(frame, text="내레이션").grid(row=5, column=0, sticky="w")
    speech_box = ttk.Combobox(frame, textvariable=speech, values=("keep", "xai", "gemini"), state="readonly")
    speech_box.grid(row=5, column=1, sticky="w")
    ttk.Label(
        frame,
        text="Gemini 효과음은 없습니다. BGM은 로컬 원본 톤입니다.",
    ).grid(row=6, column=0, columnspan=2, sticky="w")
    gemini_var = tk.StringVar()
    xai_var = tk.StringVar()
    ttk.Label(frame, text="Gemini API 키").grid(row=7, column=0, sticky="w")
    ttk.Entry(frame, textvariable=gemini_var, show="*", width=40).grid(row=7, column=1)
    ttk.Label(frame, text="xAI API 키").grid(row=8, column=0, sticky="w")
    ttk.Entry(frame, textvariable=xai_var, show="*", width=40).grid(row=8, column=1)
    open_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text="저장 후 config.yaml 열기", variable=open_var).grid(
        row=9, column=0, columnspan=2, sticky="w"
    )

    def cancel() -> None:
        outcome["value"] = OnboardResult(cancelled=True)
        root.destroy()

    def save() -> None:
        try:
            provider, model = decide_chat_model(
                mode.get(),
                request,
                provider_var.get(),
                model_var.get(),
            )
        except RepairError as exc:
            ttk.Label(frame, text=str(exc)).grid(row=11, column=0, columnspan=2, sticky="w")
            return
        picked = speech.get()
        tts_provider = picked if picked in {"xai", "gemini"} else ""
        outcome["value"] = OnboardResult(
            cancelled=False,
            chat_provider=provider,
            chat_model=model,
            tts_provider=tts_provider,
            tts_model=GEMINI_TTS_DEFAULT if tts_provider == "gemini" else ("grok-tts" if tts_provider == "xai" else ""),
            tts_voice=GEMINI_TTS_VOICE if tts_provider == "gemini" else ("eve" if tts_provider == "xai" else ""),
            gemini_api_key=gemini_var.get().strip() or None,
            xai_api_key=xai_var.get().strip() or None,
            open_config=bool(open_var.get()),
            local_tone=True,
        )
        root.destroy()

    ttk.Button(frame, text="저장", command=save).grid(row=10, column=0, sticky="w")
    ttk.Button(frame, text="취소", command=cancel).grid(row=10, column=1, sticky="e")
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return outcome.get("value", OnboardResult(cancelled=True))


def prompt_for_environment(force_headless: bool = False):
    def prompt(request: OnboardRequest) -> OnboardResult:
        if force_headless or not _display_available():
            return headless_prompt(request)
        try:
            return gui_prompt(request)
        except Exception:
            print("그래픽 창을 열 수 없어 질문으로 진행합니다.")
            return headless_prompt(request)

    return prompt


def supported_speech_models() -> list[str]:
    return sorted(GEMINI_TTS_MODELS)
