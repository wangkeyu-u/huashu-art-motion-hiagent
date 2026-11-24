"""Stage local images used by the upstream clip JSON contract."""

from pathlib import Path

FRAME_EXT = (".png", ".jpg", ".jpeg", ".webp")


def image(value, base, encode, field):
    if not isinstance(value, str) or not value or value.startswith(("data:", "http:", "https:", "//")):
        raise ValueError(f"{field} 需要已保存到工作目录的图片路径")
    return encode((base / value).resolve())


def directory(value, base, field):
    if value.startswith(("data:", "http:", "https:", "//")):
        raise ValueError(f"{field} 需要已保存到工作目录的图片目录")
    path = (base / value).resolve()
    if not path.is_dir():
        raise ValueError(f"{field} 目录不存在：{path}")
    files = sorted(file.resolve() for file in path.iterdir() if file.is_file() and file.suffix.lower() in FRAME_EXT)
    if not files:
        raise ValueError(f"{field} 目录没有 PNG、JPEG 或 WebP：{path}")
    return files


def localize(spec, base, encode):
    """Replace image paths in a clip spec with references to the packaged assets."""
    base = Path(base)
    for cue in spec["cues"]:
        if "image" in cue:
            cue["image"] = image(cue["image"], base, encode, "cue.image")
        if "frames" not in cue:
            continue
        values = cue["frames"]
        if isinstance(values, str):
            cue["frames"] = [encode(file) for file in directory(values, base, "cue.frames")]
        elif isinstance(values, list) and values:
            cue["frames"] = [image(value, base, encode, "cue.frames") for value in values]
        else:
            raise ValueError("cue.frames 需要图片目录或非空文件路径数组")

    data = spec.get("data", {})
    if "image" in data:
        data["image"] = image(data["image"], base, encode, "data.image")
