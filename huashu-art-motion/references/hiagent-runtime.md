# 在 HiAgent 生成和交付动画

兼容版以花叔 huashu-art-motion 1.3.1 为基础。包内提供七种解说模板、绘图库和转场。包内保留原版字体及字重。浏览器也会为超出子集的字使用系统字体。原版的桌面渲染、语音复刻、批量参考片分析和示范影片需另用具备相应能力的工具。样片入口见[解说示范](offline-showcases.md)。

## 构建与交付

- 把 Skill ZIP 导入 HiAgent，添加到要使用的智能体。运行路径需要能读取 Skill 目录、执行 Python 脚本并交付生成的 HTML。
- 用 `python3 "<skill>/scripts/build_html.py" --demo chart --out "<工作目录>/chart.html"` 验证文件链路。构建命令也可直接在 Python 沙箱用系统解释器调用。构建只使用 Python 3.9+ 标准库。断网沙箱从 Skill 读取随包脚本、字体和示例，成品也可离线打开。
- 构建前把上传素材、截图、角色帧和录音保存为本地文件。只有网页或媒体链接时，先请用户上传文件。JSON 中的相对路径以各自文件所在目录为基准，绝对路径也可用。
- HTML 内嵌字体、脚本和素材。若平台预览不执行 JavaScript，下载 HTML 后在 Chrome 或 Edge 里打开。导出是实时编码，保持页面在前台。生成后点击下载 MP4 或 WebM。透明画面可保存带 alpha 的 PNG。
- 录音支持浏览器能解码的 WAV、MP3、M4A、Ogg。音轨从时间轴零点开始，导出随画面时长结束，短音频结束后续画面保持静音。先在浏览器播放检查同步。
- 带视频素材的分镜，可把已提取的 PNG、JPEG、WebP 帧写进原版 `cues[].frames`，目录或文件列表均可。目录按文件名排序。这里的原生视频导出使用客户端编码，实际帧率取决于浏览器和设备。最长边超过 1920 的画面会按比例缩小为视频，PNG 保存原尺寸。
- 源码与素材可留在任务目录供修订。发布仅用已配置的文件产物工具。

## 混合分镜

项目时钟和画幅由项目级 `width`、`height`、`fps` 决定。解说片段 JSON 的 `duration` 算作镜长。自定义场景的秒数写在 `duration`。场景镜头需要填写 `scene` 与本地 `script`。参数化解说支持竖屏。

```json
{
  "title": "产品动画",
  "width": 1280,
  "height": 720,
  "fps": 30,
  "audio": "narration.mp3",
  "assets": {"photo": "product.png"},
  "shots": [
    {"scene": "opening", "script": "opening.js", "duration": 2.5},
    {"spec": "chart.json", "transition": {"type": "ripple", "dur": 0.45, "punch": false}}
  ]
}
```

`transition` 写在进入的镜头上。名称见 `scripts/engine/transitions.js`，不写时硬切，另可设置 `delay` 和 `punch`。转场在进入镜内发生，不增加总时长。统一画幅后再按留白与字幕区调整片段中的像素参数。

自定义 `opening.js` 的最小结构：

```js
window.SCENES.opening = {
  draw(context, localTime, filmTime, images) {
    const { W, H } = window.STAGE;
    context.fillStyle = "#efe3c7";
    context.fillRect(0, 0, W, H);
    const progress = window.U.ss(0, 1.2, localTime);
    const image = images.photo;
    const scale = Math.min(W * 0.55 / image.width, H * 0.72 / image.height);
    const width = image.width * scale;
    const height = image.height * scale;
    context.drawImage(image, W * (0.15 + 0.07 * progress), (H - height) / 2, width, height);
  }
};
```

- `localTime` 是镜内时间，上一镜在转场中会继续得到新的时间。用有种子的 `U.rng`，同一时刻应得到同一画面。
- `images` 是项目级素材表，只有实际保存到本地的图片会被内嵌。需要布局框、图文、曲线或材质时，可复用 `scripts/engine/lib/` 中已有函数。
- 如果场景代码运行时才拼出字体名，在项目的 `"fonts"` 数组明确列出这些字体名。随包字体名见 `scripts/engine/lib/fonts.js`。

- `--spec` 可重复。若启用透明项目，写 `"alpha": true`，片段显式声明的 alpha 要一致。批量混合前逐镜确认文字与方向。
- 可用 `python3 "<skill>/scripts/storyboard_lint.py" "镜头表.md"` 辅助检查镜头表，口播稿用 `--script "文稿.txt"`。构建已调用原版片段 lint。浏览器可用时，还要实际拉动时间轴并播放，检查标签、转场、缺帧和空白。

上游出处：[alchaincyf/huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion)。代码沿用 MIT，随包字体保留各自许可。随包工程可以生成离线示范 HTML。
