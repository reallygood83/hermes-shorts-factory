"""Optional Manim scene. Importing it needs Manim, which this package does not install.

Run it yourself from this directory only after `manim` is on PATH.
Manim Community's quickstart form is: manim -ql hook_card.py HookCard
https://docs.manim.community/en/stable/tutorials/quickstart.html
"""

from manim import Scene, Text, WHITE


class HookCard(Scene):
    def construct(self) -> None:
        self.camera.background_color = "#111827"
        self.add(Text("3초 훅", color=WHITE))
