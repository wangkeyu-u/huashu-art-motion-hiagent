# 解说样片

在断网沙箱里用 `build_html.py --showcase` 生成可单独打开的 HTML。制作新内容时从样片选择适合的解说构图和动作，再替换成用户的主题和材料。

```bash
python3 "<skill>/scripts/build_html.py" --showcase y1_kurzgesagt --out "<产物目录>/science.html"
```

| 入口 | 内容 |
|---|---|
| `y1_kurzgesagt` | 科普图解 |
| `y2_vox` | 剪报拼贴 |
| `y3_whiteboard` | 白板手绘 |
| `y5_kinetic_type` | 动态文字 |
| `t1_3b1b` | 数学图解 |
| `t2_keynote_ui` | 发布会 |
| `t3_finance_chart` | 财经图表 |

样片可在支持的浏览器编码为视频。另附讲解员参考工程 `scripts/engine/reference_films/spacex/`，使用时需补齐素材和音轨。

## 选画法

- 概念关系和先后顺序适合过程图解。让节点随讲解出现，关键转折靠元素运动表现。数据或证据多时，文件分析流程提供档案拼贴、黑板推导、发布会大数字和纸本图解。
- 有截图、原文或真实图片时，可以用原材料做画面主体，再用画笔、箭头或遮罩引导。避免把每镜的资料都塞成整页文字。
- 保持片内连续性。需要换风格时，用段落转折或世界迁移给出理由。用户比较风格时可以用同一组材料做多个版本，让构图和运动也能对比。

代码和字体的授权见各自许可证。[花叔原项目](https://github.com/alchaincyf/huashu-art-motion)
