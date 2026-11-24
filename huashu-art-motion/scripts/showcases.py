"""Resolve the bundled upstream demonstrations into offline script and image resources."""

import re

DEMO_NAMES = {
    "y1_kurzgesagt": "科普图解",
    "y2_vox": "剪报拼贴",
    "y3_whiteboard": "白板手绘",
    "y5_kinetic_type": "动态文字",
    "t1_3b1b": "数学图解",
    "t2_keynote_ui": "发布会",
    "t3_finance_chart": "财经图表",
}

ERA_IDS = re.compile(r"\{\s*id\s*:\s*['\"]([a-zA-Z0-9_]+)['\"]")
SCRIPT_LIST = re.compile(r"window\.SCENE_LIBS\s*=\s*\[([^\]]*)\]")
SCENE_DIR = re.compile(r"window\.SCENE_DIR\s*=\s*['\"]([^'\"]+)['\"]")
IMAGES = {".png", ".jpg", ".jpeg", ".webp"}


def read(path):
    return path.read_text(encoding="utf-8")


def folder_assets(engine, folder):
    return {
        image.relative_to(engine).as_posix(): image
        for image in sorted(folder.rglob("*")) if image.suffix.lower() in IMAGES
    }


def prepare(engine, name):
    folder = engine / "demos" / name
    eras = read(folder / "eras.js")
    scripts = [eras]
    mapping = SCENE_DIR.search(eras)
    scene_dir = engine / mapping.group(1) if mapping else folder
    libraries = SCRIPT_LIST.search(eras)
    if libraries:
        for library in re.findall(r"""['"]([^'"]+)['"]""", libraries.group(1)):
            scripts.append(read(engine / library))
    for scene_id in dict.fromkeys(ERA_IDS.findall(eras)):
        code = scene_dir / f"{scene_id}.js"
        if code.is_file():
            scripts.append(read(code))

    assets = folder_assets(engine, folder)
    assets.update(folder_assets(engine, engine / "demos/_shared/hero"))
    return scripts, assets
