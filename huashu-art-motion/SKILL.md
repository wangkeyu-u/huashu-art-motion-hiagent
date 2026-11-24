---
name: huashu-art-motion
description: 在 HiAgent 用代码制作产品演示、口播解说、动态图表和文件分析动画。使用 DB-GPT 分析 Excel、CSV，读取 PDF 与 Word 的内容和出处，并将主题、讲稿、文件证据、图片或录音转成可离线播放和导出视频的动画 HTML。
metadata:
  author: 花叔
  version: "1.3.1-hiagent.5"
  upstream: "https://github.com/alchaincyf/huashu-art-motion"
  upstream-revision: "a97c45018d46e950d56d61981138e08f4e092909"
---

# 花叔艺术动画 · HiAgent 版

用解说模板、自定义 Canvas 场景和转场表达一个具体动作或观点。HiAgent 生成单文件 HTML。动画构建在断网沙箱中执行，只依赖 Python 3.9+ 标准库。引擎、字体和素材全部内嵌，HTML 可离线播放、拖动时间轴、保存 PNG 或通过浏览器编码器导出视频。

## 用户上传 Excel、CSV、PDF 或 Word

先按[离线文件分析](references/file-analysis.md)运行 `scripts/analyze_input.py`，读取统计摘要和证据。如果用户只要分析，就按问题解释结论并列出对应的工作表、页码或段落。如果用户要动画，先核对数据口径和原文，再用 `scripts/animate_findings.py` 将选中的图表和摘录送进时间轴。两条路径都用本地附件。

按主题选择画面结构。档案调查适合原文与数据并排，黑板推导适合流程和机制，发布会简报适合关键数字，纸本图解适合传统统计解说。文件分析的分镜可以选择整片风格和单镜风格。做解说片时可用下方示范选择构图、动作和转场。

Excel/CSV 使用内嵌 DB-GPT `csv-data-analysis` 的统计引擎，依赖可用的离线 NumPy 和 pandas。PDF 的文本和 Word 的段落、表格可用随包解析器读取。文档数据与内容分析分开，图上数字来自结果，原文引用保留出处。

## 执行

1. 确认画幅、时长、风格和素材。用[镜头表](references/镜头表模板.md)记下时间段、画面里的物、发生的动作、镜头和屏上字。先让主体有动作，再决定是否运镜。解说片优先用一个例子贯穿，统一色板，按讲稿或录音的实际时间放 cue。
2. 选择下面的路线。参考原版的构图、运动和节奏，按当前内容创作画面。参考中出现的桌面命令、在线更新和本机配音步骤由本页流程替代。
3. 用本次任务已上传或已生成的本地文件。只有素材网址时，请用户上传原文件。根据平台工具返回值找到 Skill 目录和输出目录，用现有 Python 3 解释器运行构建脚本。使用随包引擎和字体，无需安装依赖。
4. 检查构建返回的 `html`、`duration_s` 和 `warnings`。修复构建错误。已有画面预览能力时，检查开头、关键动作、转场和末镜中的构图及文字。明确区分结构校验和浏览器审片。
5. 把 HTML 写到平台的文件产物目录，用平台自带的文件交付能力返回实际附件或下载地址。把“打开 HTML 后点导出视频”作为视频获取方式。浏览器支持 MP4 时优先 MP4，其他支持的环境用 WebM。用户需要在 HiAgent 中直接获得 MP4 时，只有可用的视频渲染工具实际返回 MP4 后，才能把它当作已生成的文件交付。

## 解说样片

[解说示范入口](references/offline-showcases.md)列有七种样片。用 `--showcase` 加示范名生成可离线播放的 HTML。

## 选制作路线

- **解说、图表、产品演示**。读[解说语法](references/09-视频动画语法.md)的选型表和对应的[语法卡](references/动画语法/)。七种原版 `clips` 可执行，示例在 `scripts/engine/examples/`。复制 JSON 结构，用用户的内容重写画面和数据。
- **自定义动作**。用[场景脚本与混合分镜](references/hiagent-runtime.md)编写项目专用场景。
- **看视频做分镜**。有实际可用的视频理解工具时，用用户提供的影片定位切点、主体运动和转场，再用新构图表达相关机制。口播用已有音频或平台已有语音能力，把结果保存为本地音轨。需要生图时用当前可用能力，把图保存成文件再引入。

单个或多个参数化片段按顺序硬切（同宽高、同帧率）：

```bash
python3 "<skill>/scripts/build_html.py" --spec "shot-01.json" --spec "shot-02.json" --out "animation.html"
```

混用参数化片段、场景、自定义脚本、转场或图片时，读[HiAgent 运行说明](references/hiagent-runtime.md)，构建项目：

```bash
python3 "<skill>/scripts/build_html.py" --project "project.json" --out "animation.html"
```

首次导入调试可运行 `--demo chart`，确认平台执行脚本和返回文件的能力，再用用户主题生成作品。
