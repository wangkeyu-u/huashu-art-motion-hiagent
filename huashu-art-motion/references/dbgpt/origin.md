# DB-GPT csv-data-analysis

- 上游 [eosphoros-ai/DB-GPT](https://github.com/eosphoros-ai/DB-GPT/tree/c7a8def445d5c76b01eb0651c085eb9c7133892e/skills/csv-data-analysis)，提交 `c7a8def445d5c76b01eb0651c085eb9c7133892e`。MIT 许可见同目录 `LICENSE`。
- `scripts/analysis/dbgpt.py` 来自上游的 `scripts/csv_analyzer.py`。可由外层传入指定工作表的 DataFrame，适配 pandas 2/3 字符串与日期类型、月末频率、常数列和未定义的相关系数。保留统计摘要及 `CHART_DATA_JSON` 数据契约。
- 本地适配器保存原分析指标，使用 huashu-art-motion 渲染选中的折线、柱形和证据分镜。上游的 ECharts 报告界面和宿主专用渲染工具不参与这个流程。
- PDF 使用随包 pypdf 6.11.0，按 [Adobe CMap 定义](https://github.com/adobe-type-tools/cmap-resources/blob/master/README.md#the-adobe-gb1-6-character-collection)使用 UTF-16BE 解码 UniGB-UTF16。旧版 Excel 使用随包 xlrd 2.0.2。Python 3.9/3.10 的兼容层使用 typing_extensions 4.16.0。各自许可证位于 `scripts/analysis/vendor/`。
