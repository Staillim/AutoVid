from __future__ import annotations

from app.domain.models import SubtitleCue, TimelineScene


class SubtitleAssBuilder:
    def build(self, timeline_scene: TimelineScene) -> str:
        if not timeline_scene.subtitle_ass_path:
            return ""

        header = "\n".join(
            [
                "[Script Info]",
                "ScriptType: v4.00+",
                "PlayResX: 1920",
                "PlayResY: 1080",
                "",
                "[V4+ Styles]",
                (
                    "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
                    "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,"
                    "ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
                    "MarginR,MarginV,Encoding"
                ),
                (
                    "Style: Default,Arial,56,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,"
                    "-1,0,0,0,100,100,0,0,1,2,0,2,80,80,60,1"
                ),
                "",
                "[Events]",
                "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
            ]
        )
        return "\n".join([header, *[self._cue_to_dialogue(cue) for cue in timeline_scene.subtitle_cues]]) + "\n"

    def _cue_to_dialogue(self, cue: SubtitleCue) -> str:
        start = self._format_ass_time(cue.start_ms)
        end = self._format_ass_time(cue.end_ms)
        text = self._escape_ass_text(cue.text)
        return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"

    def _format_ass_time(self, milliseconds: int) -> str:
        total_centiseconds = milliseconds // 10
        cs = total_centiseconds % 100
        total_seconds = total_centiseconds // 100
        seconds = total_seconds % 60
        total_minutes = total_seconds // 60
        minutes = total_minutes % 60
        hours = total_minutes // 60
        return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"

    def _escape_ass_text(self, value: str) -> str:
        return (
            value.replace("\\", r"\\")
            .replace("{", r"\{")
            .replace("}", r"\}")
            .replace("\n", r"\N")
        )
