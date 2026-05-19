from __future__ import annotations

from app.domain.models import CompiledOverlayClip, CompiledTextClip, RenderPlan, TimelineScene


class FfmpegCommandBuilder:
    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def build(self, plan: RenderPlan) -> list[str]:
        command: list[str] = [self.ffmpeg_path, "-y", "-hide_banner"]

        command.extend(self._build_inputs(plan))
        filter_complex, final_label = self._build_filter_complex(plan.timeline_scene)

        command.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                f"[{final_label}]",
                "-r",
                str(plan.timeline_scene.fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-an",
                plan.outputs.scene_output_path,
            ]
        )
        return command

    def _build_inputs(self, plan: RenderPlan) -> list[str]:
        args: list[str] = []
        scene = plan.timeline_scene
        duration_sec = self._seconds(scene.duration_ms)

        background = scene.background_clip
        if background.asset_kind.value == "image":
            args.extend(["-loop", "1", "-t", duration_sec, "-i", background.absolute_path])
        else:
            args.extend(
                [
                    "-ss",
                    self._seconds(background.trim_in_ms),
                    "-t",
                    duration_sec,
                    "-i",
                    background.absolute_path,
                ]
            )

        for overlay in scene.overlay_clips:
            overlay_duration = self._seconds(overlay.end_ms - overlay.start_ms)
            if overlay.asset_kind.value == "image":
                args.extend(["-loop", "1", "-t", overlay_duration, "-i", overlay.absolute_path])
            else:
                args.extend(["-t", overlay_duration, "-i", overlay.absolute_path])
        return args

    def _build_filter_complex(self, scene: TimelineScene) -> tuple[str, str]:
        parts: list[str] = []
        current_label = "bg0"

        bg_chain = (
            f"[0:v]scale={scene.width}:{scene.height}:force_original_aspect_ratio=increase,"
            f"crop={scene.width}:{scene.height},setsar=1"
        )
        zoom_fragment = self._build_zoom_fragment(scene)
        if zoom_fragment:
            bg_chain += f",{zoom_fragment}"
        bg_chain += f"[{current_label}]"
        parts.append(bg_chain)

        for index, overlay in enumerate(scene.overlay_clips, start=1):
            overlay_label = f"ov{index}"
            next_label = f"mix{index}"
            parts.append(self._build_overlay_prep(index=index, overlay=overlay, out_label=overlay_label))
            parts.append(
                self._build_overlay_mix(
                    input_label=current_label,
                    overlay_label=overlay_label,
                    out_label=next_label,
                    overlay=overlay,
                )
            )
            current_label = next_label

        for index, text in enumerate(scene.text_clips, start=1):
            next_label = f"text{index}"
            parts.append(self._build_drawtext(input_label=current_label, out_label=next_label, text=text))
            current_label = next_label

        if scene.subtitle_ass_path:
            next_label = "subs0"
            subtitle_path = self._escape_filter_value(scene.subtitle_ass_path)
            parts.append(
                f"[{current_label}]subtitles=filename='{subtitle_path}'[{next_label}]"
            )
            current_label = next_label

        return ";".join(parts), current_label

    def _build_overlay_prep(self, *, index: int, overlay: CompiledOverlayClip, out_label: str) -> str:
        input_ref = f"[{index}:v]"
        opacity = f"{overlay.opacity:.3f}"
        return (
            f"{input_ref}scale={overlay.width_px}:{overlay.height_px},format=rgba,"
            f"colorchannelmixer=aa={opacity}[{out_label}]"
        )

    def _build_overlay_mix(
        self,
        *,
        input_label: str,
        overlay_label: str,
        out_label: str,
        overlay: CompiledOverlayClip,
    ) -> str:
        x_expr = str(overlay.x_px)
        y_expr = self._overlay_y_expr(overlay)
        enable_expr = self._between_expr(overlay.start_ms, overlay.end_ms)
        return (
            f"[{input_label}][{overlay_label}]overlay="
            f"x='{x_expr}':y='{y_expr}':enable='{enable_expr}'[{out_label}]"
        )

    def _build_drawtext(self, *, input_label: str, out_label: str, text: CompiledTextClip) -> str:
        style = text.style
        font_file = self._escape_filter_value(style.font_file)
        content = self._escape_filter_value(text.content)
        params = [
            f"fontfile='{font_file}'",
            f"text='{content}'",
            f"x={text.x_px}",
            f"y={text.y_px}",
            f"fontsize={style.font_size_px}",
            f"fontcolor={style.color_rgba}",
            f"enable='{self._between_expr(text.start_ms, text.end_ms)}'",
        ]
        if style.stroke_rgba and style.stroke_width_px > 0:
            params.append(f"bordercolor={style.stroke_rgba}")
            params.append(f"borderw={style.stroke_width_px}")
        if style.bg_rgba:
            params.append("box=1")
            params.append(f"boxcolor={style.bg_rgba}")
            params.append(f"boxborderw={style.padding_px}")
        return f"[{input_label}]drawtext={':'.join(params)}[{out_label}]"

    def _build_zoom_fragment(self, scene: TimelineScene) -> str:
        zoom = scene.zoom
        if zoom.mode == "none":
            return ""

        start_sec = zoom.start_ms / 1000
        duration_sec = max((zoom.end_ms - zoom.start_ms) / 1000, 0.001)
        delta = zoom.end_scale - zoom.start_scale
        progress = f"(min(max(t-{start_sec:.3f},0),{duration_sec:.3f})/{duration_sec:.3f})"
        scale_expr = f"({zoom.start_scale:.4f}+({delta:.4f}*{progress}))"
        return (
            f"scale=w='iw*{scale_expr}':h='ih*{scale_expr}':eval=frame,"
            f"crop={scene.width}:{scene.height}:(in_w-{scene.width})/2:(in_h-{scene.height})/2"
        )

    def _overlay_y_expr(self, overlay: CompiledOverlayClip) -> str:
        if overlay.enter_anim != "slide_up":
            return str(overlay.y_px)
        anim_duration = 0.25
        start_sec = overlay.start_ms / 1000
        delta = 24
        return (
            "if(lt(t,"
            f"{start_sec + anim_duration:.3f}),"
            f"{overlay.y_px}+({delta}*(1-((t-{start_sec:.3f})/{anim_duration:.3f}))),"
            f"{overlay.y_px})"
        )

    def _between_expr(self, start_ms: int, end_ms: int) -> str:
        return f"between(t,{start_ms / 1000:.3f},{end_ms / 1000:.3f})"

    def _seconds(self, milliseconds: int) -> str:
        return f"{milliseconds / 1000:.3f}"

    def _escape_filter_value(self, value: str) -> str:
        escaped = value.replace("\\", "/")
        escaped = escaped.replace(":", "\\:")
        escaped = escaped.replace("'", r"\'")
        escaped = escaped.replace(",", r"\,")
        escaped = escaped.replace("[", r"\[")
        escaped = escaped.replace("]", r"\]")
        return escaped
