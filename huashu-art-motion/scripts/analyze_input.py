#!/usr/bin/env python3
"""Extract traceable evidence from local files and run DB-GPT on tabular data."""

import argparse
from collections import Counter
import codecs
from contextlib import redirect_stdout
import io
import json
import re
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

VENDOR = Path(__file__).resolve().parent / "analysis/vendor"
sys.path.insert(0, str(VENDOR))
pdf_library = VENDOR / "pypdf.zip"
if pdf_library.is_file():
    sys.path.insert(0, str(pdf_library))
WORKBOOKS = {".xlsx", ".xlsm", ".xls"}
DELIMITED = {".csv", ".tsv"}
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
START = "###CHART_DATA_JSON_START###"
END = "###CHART_DATA_JSON_END###"


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent) as temp:
        draft = Path(temp) / path.name
        draft.write_text(text, encoding="utf-8")
        draft.replace(path)


def dependency_state():
    statuses = {}
    for name in ("numpy", "pandas", "openpyxl", "xlrd", "pypdf"):
        try:
            module = __import__(name)
            statuses[name] = {"available": True, "version": module.__version__}
        except (ImportError, OSError, ValueError) as error:
            statuses[name] = {"available": False, "message": str(error)}
    return statuses


def pandas_module():
    try:
        import numpy
        import pandas
        return pandas
    except (ImportError, OSError, ValueError) as error:
        raise ValueError(f"DB-GPT 需要可用的 numpy 和 pandas。请先运行 --check 并加载离线依赖。{error}") from error


def db_gpt(frame, name):
    pd = pandas_module()
    from analysis.dbgpt import analyze_csv

    frame.columns = [str(column) for column in frame]
    if not frame.columns.is_unique:
        raise ValueError("列名转成文本后有重名，请调整表头")
    if not len(frame) or not len(frame.columns) or frame.isna().all().all():
        raise ValueError("所选表中没有可分析的数据行，请检查表头行或工作表")
    nonfinite = [float("inf"), float("-inf")]
    invalid = int(frame.isin(nonfinite).sum().sum())
    if invalid:
        frame = frame.replace(nonfinite, float("nan"))
        if frame.isna().all().all():
            raise ValueError("表中只有空值或非有限数值")

    buf = io.StringIO()
    with redirect_stdout(buf):
        analyze_csv(name, frame=frame)
    raw = json.loads(buf.getvalue())["chunks"][0]["content"]
    before, marker, rest = raw.partition(f"\n{START}\n")
    encoded, close, _ = rest.partition(f"\n{END}")
    if not marker or not close:
        raise ValueError(raw.splitlines()[0] if raw else "DB-GPT 未返回分析结果")
    charts = json.loads(encoded, parse_constant=lambda _: None)
    summary = before.rsplit("==================================================", 1)[0].strip()
    summary = re.sub(r"(?<=[= ])nan(?=[%,，)\s]|$)", "未定义", summary)
    warnings = [f"{invalid} 个无穷值按缺失值统计"] if invalid else []
    return {"engine": "DB-GPT csv-data-analysis", "stats": charts, "summary": summary, "warnings": warnings}


def file_encoding(path, explicit):
    if explicit:
        codecs.lookup(explicit)
        return explicit
    with path.open("rb") as source:
        prefix = source.read(4)
    if prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    return "utf-8-sig"


def text_file(path, encoding):
    try:
        return path.read_text(encoding=file_encoding(path, encoding))
    except UnicodeError as error:
        raise ValueError("文本解码失败，可用 --encoding 指定文件的实际编码") from error


def read_delimited(path, options):
    pd = pandas_module()
    sep = options.delimiter or ("\t" if path.suffix.lower() == ".tsv" else ",")
    encoding = file_encoding(path, options.encoding)
    try:
        return pd.read_csv(path, header=options.header_row - 1, sep=sep, encoding=encoding)
    except UnicodeError as error:
        if options.encoding or encoding == "utf-16":
            raise ValueError("表格解码失败，请用 --encoding 指定实际编码") from error
        return pd.read_csv(path, header=options.header_row - 1, sep=sep, encoding="gb18030")


def table_source(location, frame, path, **metadata):
    return {
        "kind": "table", "location": location, **metadata,
        "analysis": db_gpt(frame, path.name),
    }


def read_workbook(path, options):
    pd = pandas_module()
    backend = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
    try:
        with pd.ExcelFile(path, engine=backend) as book:
            selection = options.sheet or book.sheet_names
            for name in dict.fromkeys(selection):
                location = f"工作表「{name}」"
                try:
                    frame = book.parse(sheet_name=name, header=options.header_row - 1)
                    yield table_source(location, frame, path, sheet=name, header_row=options.header_row)
                except (ValueError, TypeError, IndexError, KeyError, OverflowError) as error:
                    yield {"kind": "error", "location": location, "message": str(error)}
    except ImportError as error:
        raise ValueError(f"读取 {path.suffix} 需要 {backend}。请先运行 --check。{error}") from error


def paragraph_text(element):
    parts = []
    for node in element.iter():
        if node.tag == WORD_NS + "t" and node.text:
            parts.append(node.text)
        elif node.tag == WORD_NS + "tab":
            parts.append("\t")
        elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
            parts.append("\n")
    return "".join(parts).strip()


def word_table(element, index, path):
    location = f"表格 {index}"
    rows = [
        ["\n".join(filter(None, map(paragraph_text, cell.findall(WORD_NS + "p"))))
         for cell in row.findall(WORD_NS + "tc")]
        for row in element.findall(WORD_NS + "tr")
    ]
    if not any(any(row) for row in rows):
        return None
    text = "\n".join("\t".join(row) for row in rows)
    source = {"kind": "text", "location": location, "text": text, "rows": rows}
    merged = any(next(element.iter(WORD_NS + name), None) is not None for name in ("gridSpan", "vMerge"))
    header = [value.strip() for value in rows[0]]
    if merged or len(rows) <= 1 or any(len(row) != len(header) for row in rows):
        return source
    if not all(header) or len(header) != len(set(header)):
        return source
    try:
        pd = pandas_module()
        frame = pd.DataFrame(rows[1:], columns=header).replace("", None)
        for name in frame:
            cleaned = frame[name].dropna().astype(str).str.strip()
            if cleaned.empty or cleaned.str.fullmatch(r"[+-]?0[0-9]+").any():
                continue
            converted = pd.to_numeric(cleaned, errors="coerce")
            if converted.notna().all():
                frame[name] = converted.reindex(frame.index)
        if len(frame.select_dtypes(include="number").columns):
            return table_source(location, frame, path, text=text, rows=rows, header_row=1)
    except (ValueError, TypeError, ImportError, OverflowError) as error:
        source["warning"] = f"表格原文已提取，DB-GPT 统计未生成：{error}"
    return source


def read_word(path):
    with ZipFile(path) as package:
        root = ElementTree.fromstring(package.read("word/document.xml"))
    body = root.find(WORD_NS + "body")
    if body is None:
        raise ValueError("找不到 DOCX 正文")
    paragraphs = tables = 0
    for element in body:
        if element.tag == WORD_NS + "p":
            paragraphs += 1
            text = paragraph_text(element)
            if text:
                yield {"kind": "text", "location": f"正文段落 {paragraphs}", "text": text}
        elif element.tag == WORD_NS + "tbl":
            tables += 1
            source = word_table(element, tables, path)
            if source:
                yield source


def read_pdf(path):
    from pypdf import PdfReader
    with path.open("rb") as stream:
        reader = PdfReader(stream, strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("PDF 已加密，请上传可读取的版本")
        for index, page in enumerate(reader.pages, start=1):
            location = f"第 {index} 页"
            try:
                content = (page.extract_text() or "").strip()
            except Exception as error:
                yield {"kind": "error", "location": location, "message": f"该页提取失败：{error}"}
                continue
            if re.search(r"[\x00-\x08\x0e-\x1f]", content):
                yield {"kind": "error", "location": location, "message": "文本层含无法解码的字符，请确认原文或提供转写。"}
            elif content:
                yield {"kind": "text", "location": location, "page": index, "text": content}
            else:
                yield {"kind": "error", "location": location, "message": "没有可提取的文本层。扫描页需要 OCR 或已有转写。"}


def sources_from(path, options):
    suffix = path.suffix.lower()
    if suffix in WORKBOOKS:
        yield from read_workbook(path, options)
    elif suffix in DELIMITED:
        yield table_source("数据表", read_delimited(path, options), path, header_row=options.header_row)
    elif suffix == ".docx":
        yield from read_word(path)
    elif suffix == ".pdf":
        yield from read_pdf(path)
    elif suffix in {".txt", ".md"}:
        for index, paragraph in enumerate(text_file(path, options.encoding).split("\n\n"), 1):
            if paragraph.strip():
                yield {"kind": "text", "location": f"第 {index} 段", "text": paragraph.strip()}
    else:
        raise ValueError("支持 XLSX、XLSM、XLS、CSV、TSV、PDF、DOCX、TXT、MD。旧版 DOC 请另存为 DOCX。")


def analyze(paths, options):
    evidence = {"schema": 1, "sources": [], "errors": []}
    counts = Counter(path.name for path in paths)
    for index, path in enumerate(paths, start=1):
        name = path.name if counts[path.name] == 1 else f"{path.name}（附件 {index}）"
        before = len(evidence["sources"]) + len(evidence["errors"])
        try:
            for source in sources_from(path, options):
                source["file"] = name
                if source["kind"] == "error":
                    evidence["errors"].append(source)
                else:
                    source["id"] = f"S{len(evidence['sources']) + 1}"
                    evidence["sources"].append(source)
            if len(evidence["sources"]) + len(evidence["errors"]) == before:
                raise ValueError("文件中没有可分析的内容")
        except (OSError, ValueError, TypeError, ImportError, OverflowError, LookupError, BadZipFile, ElementTree.ParseError) as error:
            evidence["errors"].append({"file": name, "location": "文件", "message": str(error)})
        except Exception as error:
            # PDF parser errors can also come from malformed pages or container structures.
            evidence["errors"].append({"file": name, "location": "文件", "message": f"{type(error).__name__}: {error}"})
    return evidence


def synopsis(evidence):
    lines = ["# 文件分析证据", ""]
    for source in evidence["sources"]:
        lines.extend([f"## {source['id']} · {source['file']} · {source['location']}", ""])
        if source["kind"] == "table":
            analysis = source["analysis"]
            lines.extend(analysis["warnings"])
            lines.extend([analysis["summary"], ""])
        else:
            text = " ".join(source["text"].split())
            if len(text) > 200:
                text = text[:200].rstrip() + "…（全文见证据 JSON）"
            lines.extend([text, ""])
            if "warning" in source:
                lines.extend([source["warning"], ""])
    if evidence["errors"]:
        lines.extend(["## 未提取的内容", ""])
        lines.extend(f"- {item['file']} · {item['location']} · {item['message']}" for item in evidence["errors"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--out-dir", type=Path, help="保存 analysis.json 和 analysis.md")
    parser.add_argument("--sheet", action="append", help="可重复指定工作表，默认逐张分析")
    parser.add_argument("--header-row", type=int, default=1, help="从 1 开始；默认首行表头")
    parser.add_argument("--encoding", help="CSV/TSV/TXT/MD 的实际文本编码")
    parser.add_argument("--delimiter", help="CSV/TSV 分隔字符，默认按扩展名选取")
    parser.add_argument("--check", action="store_true", help="检查本机的离线文件分析能力")
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"python": sys.version.split()[0], "packages": dependency_state()}, ensure_ascii=False, indent=2))
        return 0
    if not args.files or not args.out_dir:
        parser.error("需要至少一个输入文件和 --out-dir")
    if args.header_row < 1 or (args.delimiter is not None and len(args.delimiter) != 1):
        parser.error("--header-row 必须为正整数，--delimiter 必须是一个字符")

    evidence = analyze(args.files, args)
    json_path, md_path = (args.out_dir.resolve() / f"analysis.{ext}" for ext in ("json", "md"))
    atomic_text(json_path, json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False))
    atomic_text(md_path, synopsis(evidence))
    print(json.dumps({
        "evidence": str(json_path), "summary": str(md_path),
        "tables": sum(item["kind"] == "table" for item in evidence["sources"]),
        "text_blocks": sum(item["kind"] == "text" for item in evidence["sources"]),
        "errors": evidence["errors"],
    }, ensure_ascii=False))
    return 0 if evidence["sources"] else 1


if __name__ == "__main__":
    sys.exit(main())
