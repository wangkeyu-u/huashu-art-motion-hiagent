#!/usr/bin/env python3
"""Build a standalone Huashu animation using only the Python standard library."""

import argparse
import base64
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from engine.spec_assets import localize
from showcases import DEMO_NAMES, prepare

SKILL = Path(__file__).resolve().parents[1]
ENGINE = SKILL / "scripts/engine"
WEB = SKILL / "scripts/web"
EXAMPLES = SKILL / "examples"
IDENTIFIER = re.compile(r"[a-zA-Z0-9_]+")
FONT_FACES = re.compile(r"\{family:'(.*?)', url:'(.*?)'[^\n]*\},")
IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
}
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}
LIBRARIES = (
    "util", "paint", "brush", "render", "post", "rig", "rig_huashu", "kit", "medium",
    "palettes", "motion", "camera", "diagram", "typo", "chart", "ui", "collage",
    "media", "toon", "finish",
)


def read_object(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} 必须是 JSON 对象")
    return data


def json_for_script(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", r"\u003c")


def script(source):
    return "<script>\n" + re.sub(r"</script", r"<\\/script", source, flags=re.I) + "\n</script>"


def data_url(path, mime):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"文件不存在或为空：{path}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def media_url(path, types):
    mime = types.get(path.suffix.lower())
    if not mime:
        raise ValueError(f"素材格式不支持：{path.name}，允许 {'、'.join(types)}")
    return data_url(path, mime)


def project_path(base, raw, field):
    if not isinstance(raw, str) or not raw or "://" in raw or raw.startswith(("data:", "//")):
        raise ValueError(f"{field} 需要本地文件路径")
    return (base / raw).resolve()


def identifier(value, field):
    if not isinstance(value, str) or value == "__proto__" or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field} 只接受英文字母、数字和下划线")
    return value


def seconds(value, field):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} 必须是正数秒")
    return value


def dimensions(source):
    config = (source.get("width", 1920), source.get("height", 1080), source.get("fps", 30))
    width, height, fps = config
    if any(type(n) is not int or not 2 <= n <= 3840 for n in (width, height)):
        raise ValueError("宽高必须是 2–3840 的整数")
    if type(fps) is not int or not 1 <= fps <= 60:
        raise ValueError("fps 必须是 1–60 的整数")
    return config


def validate_clip(path, spec):
    grammar = identifier(spec.get("grammar"), "grammar")
    if not (ENGINE / "clips" / f"{grammar}.js").is_file():
        raise ValueError(f"未知的解说语法：{grammar}")
    seconds(spec.get("duration"), f"{path.name} 的 duration")
    if not isinstance(spec.get("data", {}), dict):
        raise ValueError(f"{path.name} 的 data 必须是对象")
    cues = spec.get("cues")
    if not isinstance(cues, list) or any(not isinstance(cue, dict) for cue in cues):
        raise ValueError(f"{path.name} 的 cues 必须是对象数组")
    for cue in cues:
        time = cue.get("at")
        if type(time) not in (int, float) or not math.isfinite(time) or time < 0:
            raise ValueError(f"{path.name} 的 cue.at 必须是非负秒数")
    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts/clip_lint.py"), str(path)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    if result.returncode:
        raise ValueError(f"{path.name} 校验失败\n{(result.stdout or result.stderr).strip()}")
    return result.stdout.splitlines() if "🟡" in result.stdout else []


def font_scripts(sources, extras):
    declarations = (ENGINE / "lib/fonts.js").read_text(encoding="utf-8")
    if not isinstance(extras, list) or any(not isinstance(name, str) for name in extras):
        raise ValueError("fonts 必须是包内字体名的数组")
    known = dict(FONT_FACES.findall(declarations))
    unknown = set(extras) - known.keys()
    if unknown:
        raise ValueError(f"找不到字体：{', '.join(sorted(unknown))}")
    samples = "\n".join(sources)
    faces = {
        family: url for family, url in known.items()
        if family in extras or family in samples
    }
    data = {name: data_url(ENGINE / name, "font/woff") for name in dict.fromkeys(faces.values())}
    return (
        declarations + "\n"
        f"const motionFontData = {json_for_script(data)};\n"
        "window.FONT_FACES = window.FONT_FACES.filter(face => Object.hasOwn(motionFontData, face.url));\n"
        "for (const face of window.FONT_FACES) face.url = motionFontData[face.url];"
    )


def build(project, base, title, audio):
    width, height, fps = dimensions(project)
    title = title or project.get("title", "艺术动画")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title 必须是非空字符串")
    shots = project.get("shots")
    if not isinstance(shots, list) or not shots or any(not isinstance(shot, dict) for shot in shots):
        raise ValueError("shots 必须是非空的镜头对象数组")
    transparent = project.get("alpha", False)
    if type(transparent) is not bool:
        raise ValueError("alpha 必须是布尔值")
    asset_urls, image_paths = {}, {}

    def encode_image(path):
        if path not in image_paths:
            key = f"asset_{len(image_paths)}"
            asset_urls[key] = media_url(path, IMAGE_TYPES)
            image_paths[path] = key
        return image_paths[path]

    named_assets = project.get("assets", {})
    if not isinstance(named_assets, dict):
        raise ValueError("assets 必须是 {素材名: 本地图片路径}")
    for key, raw in named_assets.items():
        identifier(key, "素材名")
        if key.startswith("asset_"):
            raise ValueError(f"素材名 {key} 请换一个非 asset_ 开头的名称")
        asset_urls[key] = media_url(project_path(base, raw, key), IMAGE_TYPES)

    transition_source = (ENGINE / "transitions.js").read_text(encoding="utf-8")
    transition_names = set(re.findall(r"^  ([a-zA-Z0-9_]+)\(", transition_source, re.M))
    eras, clip_sources, scene_sources, warnings = [], [], {}, []
    for index, shot in enumerate(shots):
        if ("spec" in shot) == ("scene" in shot):
            raise ValueError(f"第 {index + 1} 镜必须填写一个 spec 或 scene")
        era = {"id": f"shot_{index + 1}"}
        if shot.get("chapter"):
            if not isinstance(shot["chapter"], str):
                raise ValueError(f"第 {index + 1} 镜的 chapter 必须是字符串")
            era["chapter"] = shot["chapter"]
        transition = shot.get("transition")
        if transition is not None:
            if not isinstance(transition, dict):
                raise ValueError("transition 必须是包含 type 和 dur 的对象")
            transition_name = identifier(transition.get("type"), "transition.type")
            if transition_name not in transition_names:
                raise ValueError(f"转场未注册：{transition_name}")
            seconds(transition.get("dur"), "transition.dur")
            delay = transition.get("delay", 0)
            if type(delay) not in (int, float) or not math.isfinite(delay) or delay < 0:
                raise ValueError("transition.delay 必须是非负秒数")
            era["transition"] = transition
        if "spec" in shot:
            path = project_path(base, shot["spec"], "spec")
            spec = read_object(path)
            if type(spec.get("alpha", False)) is not bool:
                raise ValueError(f"{path.name} 的 alpha 必须是布尔值")
            if spec.get("alpha", transparent) != transparent:
                raise ValueError(f"{path.name} 的 alpha 与项目设置不同")
            spec = {**spec, "width": width, "height": height, "fps": fps, "alpha": transparent}
            warnings.extend(f"{path.name}：{line}" for line in validate_clip(path, spec))
            localize(spec, path.parent, encode_image)
            grammar_path = ENGINE / "clips" / f"{spec['grammar']}.js"
            era.update(dur=spec["duration"], motionSpec=spec)
            clip_sources.append(
                grammar_path.read_text(encoding="utf-8")
                + f"\nwindow.MOTION_GRAMMARS[{json_for_script(era['id'])}] = "
                + f"window.CLIPS[{json_for_script(spec['grammar'])}];"
            )
        else:
            scene = identifier(shot["scene"], "scene")
            if not shot.get("script"):
                raise ValueError(f"场景 {scene} 需要在 script 中指定本地 .js 文件")
            source = project_path(base, shot["script"], "script")
            if source.suffix.lower() != ".js":
                raise ValueError("script 必须是本地 .js 文件")
            if not source.is_file():
                raise ValueError(f"场景 {scene} 找不到脚本：{source.name}")
            if scene in scene_sources and scene_sources[scene] != source:
                raise ValueError(f"同名场景 {scene} 指向了不同脚本")
            scene_sources[scene] = source
            era.update(
                dur=seconds(shot.get("duration"), "scene.duration"),
                motionScene=scene, assets=list(named_assets),
            )
        if transition and transition["dur"] + transition.get("delay", 0) > era["dur"]:
            raise ValueError(f"第 {index + 1} 镜的转场超过镜长")
        eras.append(era)

    if not math.isfinite(sum(era["dur"] for era in eras)):
        raise ValueError("总时长必须有限")
    audio = audio or (project_path(base, project["audio"], "audio") if project.get("audio") else None)
    config = {"title": title, "fps": fps, "alpha": transparent, "audio": media_url(audio, AUDIO_TYPES) if audio else None}
    variables = {
        "MOTION_CONFIG": config, "MOTION_ASSETS": asset_urls,
        "FILM_SIZE": [width, height], "ERAS": eras,
        "SCENES": {}, "MOTION_GRAMMARS": {},
    }
    sources = ["\n".join(f"window.{key} = {json_for_script(data)};" for key, data in variables.items())]
    sources.extend((ENGINE / f"lib/{name}.js").read_text(encoding="utf-8") for name in LIBRARIES)
    sources.extend([
        transition_source,
        (ENGINE / "clip.js").read_text(encoding="utf-8"),
        *clip_sources,
        *(path.read_text(encoding="utf-8") for path in sorted(set(scene_sources.values()))),
        (WEB / "timeline.js").read_text(encoding="utf-8"),
        (ENGINE / "engine.js").read_text(encoding="utf-8"),
        (WEB / "player.js").read_text(encoding="utf-8"),
    ])
    return compose_page(title, sources, project.get("fonts", [])), sum(era["dur"] for era in eras), warnings


def compose_page(title, sources, fonts):
    sources.insert(1, font_scripts(sources, fonts))
    licenses = [SKILL / "LICENSE", ENGINE / "lib/fonts/OFL.txt", ENGINE / "lib/fonts/LICENSES.md"]
    notices = "\n\n".join(path.read_text(encoding="utf-8") for path in licenses)
    page = (WEB / "player.html").read_text(encoding="utf-8")
    page = page.replace("<!--TITLE-->", html.escape(title))
    page = page.replace("<!--LICENSES-->", "<!--\n" + notices.replace("-->", "-- >") + "\n-->")
    page = page.replace("<!--SCRIPTS-->", "\n".join(map(script, sources)))
    return page



def build_showcase(name, title, audio):
    title = title or DEMO_NAMES[name]
    motion, paths = prepare(ENGINE, name)
    assets = {key: media_url(path, IMAGE_TYPES) for key, path in paths.items()}
    config = {"title": title, "fps": 30, "alpha": False, "audio": media_url(audio, AUDIO_TYPES) if audio else None}
    variables = {
        "MOTION_CONFIG": config, "MOTION_ASSETS": assets, "FILM_SIZE": [1920, 1080],
        "SCENES": {},
    }
    sources = ["\n".join(f"window.{key} = {json_for_script(data)};" for key, data in variables.items())]
    sources.extend((ENGINE / f"lib/{library}.js").read_text(encoding="utf-8") for library in LIBRARIES)
    sources.extend([
        (ENGINE / "transitions.js").read_text(encoding="utf-8"),
        *motion,
        (WEB / "timeline.js").read_text(encoding="utf-8"),
        (ENGINE / "engine.js").read_text(encoding="utf-8"),
        (WEB / "player.js").read_text(encoding="utf-8"),
    ])
    return compose_page(title, sources, [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--spec", action="append", type=Path, help="可重复传入，同画幅依次硬切")
    mode.add_argument("--project", type=Path, help="混合分镜、转场及素材的 JSON 项目")
    mode.add_argument("--demo", choices=("chart",), help="用内置示例验证环境")
    mode.add_argument("--showcase", choices=list(DEMO_NAMES), help="原版离线解说示范")
    parser.add_argument("--out", type=Path, required=True, help="成品 .html 文件路径")
    parser.add_argument("--title")
    parser.add_argument("--audio", type=Path, help="可选的一条本地 WAV、MP3、M4A 或 Ogg")
    args = parser.parse_args()

    try:
        out = args.out.resolve()
        if out.suffix.lower() != ".html":
            raise ValueError("--out 请以 .html 结尾")
        path = EXAMPLES / f"{args.demo}.json" if args.demo else args.project
        if args.showcase:
            page = build_showcase(args.showcase, args.title, args.audio)
            result = {"showcase": args.showcase}
        elif path:
            path = path.resolve()
            project, base = read_object(path), path.parent
        else:
            spec_paths = [path.resolve() for path in args.spec]
            first = read_object(spec_paths[0])
            width, height, fps = dimensions(first)
            for path in spec_paths[1:]:
                if dimensions(read_object(path)) != (width, height, fps):
                    raise ValueError("--spec 多镜必须同宽、同高、同帧率")
            project = {
                "title": spec_paths[0].stem, "width": width, "height": height, "fps": fps,
                "alpha": first.get("alpha", False), "shots": [{"spec": str(path)} for path in spec_paths],
            }
            base = Path.cwd()
        if not args.showcase:
            page, duration, warnings = build(project, base, args.title, args.audio)
            result = {"duration_s": duration, "shots": len(project["shots"]), "warnings": warnings}
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out.parent, delete=False) as handle:
                tmp = Path(handle.name)
                handle.write(page)
            tmp.replace(out)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        print(json.dumps({
            "html": str(out), **result, "bytes": out.stat().st_size,
        }, ensure_ascii=False))
    except (OSError, ValueError, TypeError, OverflowError) as error:
        parser.exit(1, f"构建失败：{error}\n")


if __name__ == "__main__":
    main()
