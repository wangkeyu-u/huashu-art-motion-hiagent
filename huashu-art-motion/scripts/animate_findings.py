#!/usr/bin/env python3
"""Render selected DB-GPT evidence and document excerpts on the Huashu timeline."""

import argparse
import json
import math
from pathlib import Path
import re
import tempfile

from analyze_input import atomic_text
from build_html import WEB, build, json_for_script, read_object

THEME = {"name": "paper", "accent": "#a3422d", "accent2": "#326751"}
STYLES = {"editorial": "纸本图解", "archive": "档案调查", "chalk": "黑板推导", "keynote": "发布会简报"}


def compact(value):
    return " ".join(str(value).split())


def label_source(source):
    return f"{source['file']} · {source['location']}"


def pool(stats, chart):
    if chart == "trend":
        items = [stats["time_series"], *stats.get("time_series_multi", [])]
        return {
            item["name"]: (item["dates"], item["values"], "有记录的各期均值")
            for item in items if item["name"] and len(item["values"]) >= 2
        }
    if chart == "groups":
        return {
            item["dimension"]: (
                [person["name"] for person in item["leaders"]],
                [person["sum"] for person in item["leaders"]],
                f"{item['metric']}分组求和",
            )
            for item in stats["segment_breakdown"] if item["leaders"]
        }
    if chart == "categories":
        return {
            name: (item["labels"], item["values"], "记录数")
            for name, item in stats["categories"].items()
        }
    if chart == "distribution":
        return {
            name: (item["bins"], item["counts"], "区间记录数")
            for name, item in stats["distributions"].items()
        }
    raise ValueError(f"未知图表类型：{chart}。可用 trend、groups、categories、distribution")


def chart_spec(shot, source, duration):
    if source["kind"] != "table":
        raise ValueError(f"{source['id']} 没有 DB-GPT 数值证据")
    chart = shot["chart"]
    stocks = pool(source["analysis"]["stats"], chart)
    column = shot.get("column") or next(iter(stocks), None)
    if column not in stocks:
        raise ValueError(f"{source['id']} 的 {chart} 没有该字段；可选：{', '.join(stocks)}")
    labels, values, unit = stocks[column]
    limit = shot.get("limit", 8)
    if type(limit) is not int or not 2 <= limit <= 12:
        raise ValueError("每镜 limit 请使用 2–12 的整数")
    if chart == "trend":
        labels, values = labels[-limit:], values[-limit:]
    elif chart == "distribution":
        if "limit" in shot and limit < len(values):
            raise ValueError("分布图应保留所有区间，请移除 limit 或提高上限")
    else:
        labels, values = labels[:limit], values[:limit]
    if not values or any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise ValueError(f"{source['id']} 的 {column} 没有可绘制的有限数值")
    title = compact(shot.get("title") or f"{column} · {unit}")
    kind = "line" if chart == "trend" else "bar"
    measurement = compact(shot.get("unit", ""))
    data = {
        "title": title, "unit": f"{unit}（{measurement}）" if measurement else unit,
        "source": f"来源：{label_source(source)}",
        "chart": kind, "decimals": 0 if chart in ("categories", "distribution") else 2,
        "series": [{"label": str(label), "value": value} for label, value in zip(labels, values)],
    }
    step = min(.65, duration * .58 / len(values))
    if kind == "line":
        cues = [{"at": .45, "kind": "line", "dur": round(duration * .52, 3)}]
    else:
        cues = [{"at": round(index * step, 3), "kind": "bar", "data": {"index": index}}
                for index in range(len(values))]
    return {"grammar": "t3_finance_chart", "theme": THEME, "duration": duration,
            "data": data, "cues": cues}


def text_spec(shot, source, duration):
    location = label_source(source)
    source_label = location if len(location) <= 23 else "…" + location[-22:]
    if "quote" in shot:
        quote = shot["quote"]
        if not isinstance(quote, str) or not 1 <= len(compact(quote)) <= 80:
            raise ValueError("摘句请使用 1–80 字的原文片段")
        quote = compact(quote)
        if quote not in compact(source.get("text", "")):
            raise ValueError(f"摘句与 {source['id']} 的原文不一致")
        cue = {
            "at": 0, "kind": "point", "text": compact(shot.get("title") or "关键摘录"), "sub": quote,
            "data": {"label": f"{source['id']} · {source_label}"},
        }
    else:
        if source["kind"] != "table":
            raise ValueError(f"{source['id']} 没有表格概况")
        overview = source["analysis"]["stats"]["overview"]
        cue = {
            "at": 0.7, "kind": "number",
            "text": f"数据规模 · {overview['cols']} 列",
            "data": {"value": overview["rows"], "suffix": " 行", "label": f"{source['id']} · {source_label}"},
        }
    return {"grammar": "y5_kinetic_type", "theme": THEME, "duration": duration, "cues": [cue]}


def suggest(evidence):
    scenes = []
    for file in dict.fromkeys(source["file"] for source in evidence):
        alternatives = [source for source in evidence if source["file"] == file]
        tables = [source for source in alternatives if source["kind"] == "table"]
        if tables:
            selected = None
            for chart in ("trend", "groups", "categories", "distribution"):
                selected = next(
                    ({"source": table["id"], "chart": chart} for table in tables
                     if pool(table["analysis"]["stats"], chart)), None
                )
                if selected:
                    break
            scenes.append(selected or {"source": tables[0]["id"], "overview": True})
            continue
        first = next((source for source in alternatives if source.get("text")), None)
        if first:
            text = compact(first["text"])
            sentence = re.split(r"(?<=[。！？；])\s*|(?<=[.!?;])\s+", text, maxsplit=1)[0]
            scenes.append({"source": first["id"], "quote": sentence[:70].rstrip()})
    return {"title": "文件分析 · 分镜预览", "shots": scenes[:4]}


def default_style(shots):
    if any(shot.get("beats") for shot in shots):
        return "chalk"
    has_chart = any("chart" in shot or "overview" in shot for shot in shots)
    has_quote = any("quote" in shot for shot in shots)
    if has_chart:
        return "archive" if has_quote else "keynote"
    return "chalk"


def scene_data(shot, source, spec):
    if "chart" in shot:
        return {**spec["data"], "kind": "chart"}
    cue = spec["cues"][0]
    where = f"{source['id']} · {label_source(source)}"
    if "quote" not in shot:
        return {
            "kind": "quote", "title": compact(shot.get("title") or "数据规模"),
            "text": f"{cue['data']['value']} 行 · {source['analysis']['stats']['overview']['cols']} 列",
            "source": where,
        }
    beats = shot.get("beats", [])
    if not isinstance(beats, list) or len(beats) > 4 or any(not isinstance(b, str) for b in beats):
        raise ValueError("beats 请填写最多 4 个原文短语")
    phrases = [compact(beat) for beat in beats]
    if any(not 1 <= len(phrase) <= 16 for phrase in phrases):
        raise ValueError("beats 每项请使用 1–16 个字的原文短语")
    tail = cue["sub"]
    for phrase in phrases:
        _, matched, tail = tail.partition(phrase)
        if not matched:
            raise ValueError("beats 须按顺序出现在该镜的原文摘句中")
    return {"kind": "quote", "title": cue["text"], "text": cue["sub"], "source": where, "beats": phrases}


def project_for(plan, sources, scratch, style_override=None):
    by_id = {source["id"]: source for source in sources}
    project = {
        "title": plan.get("title", "文件分析动画"), "width": plan.get("width", 1280),
        "height": plan.get("height", 720), "fps": plan.get("fps", 30), "shots": [],
    }
    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots or any(not isinstance(shot, dict) for shot in shots):
        raise ValueError("需要至少一个引用证据的镜头")
    preferred = style_override or plan.get("style", "auto")
    main_style = default_style(shots) if preferred == "auto" else preferred
    styled = []
    for index, shot in enumerate(shots, start=1):
        source_id = shot.get("source")
        if not isinstance(source_id, str) or source_id not in by_id:
            raise ValueError(f"第 {index} 镜找不到证据 {source_id}")
        source = by_id[source_id]
        duration = shot.get("duration", 6)
        if type(duration) not in (int, float) or not math.isfinite(duration) or not 2 <= duration <= 12:
            raise ValueError(f"第 {index} 镜的时长请使用 2–12 秒")
        if sum(key in shot for key in ("chart", "quote", "overview")) != 1:
            raise ValueError(f"第 {index} 镜需要一个 chart、quote 或 overview")
        style = main_style if style_override is not None else shot.get("style", main_style)
        if not isinstance(style, str) or style not in STYLES:
            raise ValueError(f"风格 {style} 无效，可用：{', '.join(STYLES)}")
        spec = chart_spec(shot, source, duration) if "chart" in shot else text_spec(shot, source, duration)
        title = spec["data"]["title"] if "chart" in shot else (shot.get("title") or "文档摘录" if "quote" in shot else "数据规模")
        if style == "editorial":
            path = scratch / f"shot-{index}.json"
            path.write_text(json.dumps(spec, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            era = {"spec": path.name}
        else:
            scene = f"finding_{index}"
            data = scene_data(shot, source, spec)
            styled.append(f"window.SCENES.{scene} = window.makeFindingScene({json_for_script(style)}, {json_for_script(data)});")
            era = {"scene": scene, "script": "findings.js", "duration": duration}
        era["chapter"] = f"{STYLES[style]} · {compact(title)}"
        if index > 1:
            era["transition"] = {"type": "crossfade", "dur": .22, "punch": False}
        project["shots"].append(era)
    if styled:
        runtime = (WEB / "finding_scenes.js").read_text(encoding="utf-8")
        (scratch / "findings.js").write_text(runtime + "\n" + "\n".join(styled), encoding="utf-8")
    return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path, help="analyze_input.py 生成的 analysis.json")
    parser.add_argument("--plan", type=Path, help="指定要展示的证据和编排顺序")
    parser.add_argument("--style", choices=["auto", *STYLES], help="选择整片风格，覆盖逐镜设置")
    parser.add_argument("--audio", type=Path, help="可选的本地音轨")
    parser.add_argument("--out", type=Path, required=True, help="自包含 HTML 文件")
    args = parser.parse_args()
    try:
        out = args.out.resolve()
        if out.suffix.lower() != ".html":
            raise ValueError("--out 请以 .html 结尾")
        evidence = read_object(args.analysis)
        sources = evidence.get("sources")
        if evidence.get("schema") != 1 or not isinstance(sources, list) or not sources:
            raise ValueError("需要含有成功证据的 analysis.json")
        plan = read_object(args.plan) if args.plan else suggest(sources)
        with tempfile.TemporaryDirectory() as folder:
            scratch = Path(folder)
            project = project_for(plan, sources, scratch, args.style)
            page, duration, warnings = build(project, scratch, None, args.audio)
            atomic_text(out, page)
        print(json.dumps({
            "html": str(out), "duration_s": duration, "shots": len(project["shots"]), "warnings": warnings,
            "sources": [shot["source"] for shot in plan["shots"]],
        }, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        parser.exit(1, f"构建失败：{error}\n")


if __name__ == "__main__":
    main()
