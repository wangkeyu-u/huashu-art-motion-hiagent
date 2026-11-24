(() => {
  const config = window.MOTION_CONFIG;
  const canvas = document.getElementById('c');
  const play = document.getElementById('play');
  const scrub = document.getElementById('scrub');
  const position = document.getElementById('position');
  const chapter = document.getElementById('chapter');
  const chapters = window.ERAS;
  const hasChapters = chapters.length > 1 && chapters.some(era => era.chapter || era.name);
  const record = document.getElementById('record');
  const png = document.getElementById('png');
  const download = document.getElementById('download');
  const status = document.getElementById('status');
  const duration = window.__total;
  const fps = config.fps;
  const lastFrameTime = Math.max(0, duration - 1 / fps);
  const fileName = config.title.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim().slice(0, 100) || 'animation';
  let cursor = 0;
  let playback = 0;
  let sequence = 0;
  let audioContext;
  let audioBuffer;
  let voice;
  let videoUrl;
  let exporting = false;

  const message = value => { status.textContent = value; };
  const failure = error => message(error instanceof Error ? error.message : String(error));
  const formats = config.audio
    ? ['video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm']
    : ['video/mp4;codecs=avc1', 'video/mp4', 'video/webm;codecs=vp9', 'video/webm'];
  const candidates = !config.alpha && typeof canvas.captureStream === 'function' && window.MediaRecorder
    ? formats.filter(type => MediaRecorder.isTypeSupported(type)) : [];
  const mp4Supported = candidates.some(type => type.startsWith('video/mp4'));

  function showFrame(time) {
    cursor = Math.min(time, duration);
    const scene = window.renderFrame(Math.min(cursor, lastFrameTime));
    if (hasChapters && chapter.selectedIndex !== scene) chapter.selectedIndex = scene;
    scrub.value = cursor;
    position.value = `${cursor.toFixed(2)} / ${duration.toFixed(2)} 秒`;
  }

  function stopPreview() {
    sequence++;
    cancelAnimationFrame(playback);
    playback = 0;
    if (voice) {
      voice.stop();
      voice = null;
    }
    play.textContent = '播放';
  }

  async function prepareAudio() {
    if (!config.audio) return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) throw new Error('当前浏览器无法播放内嵌音轨。');
    audioContext ??= new Audio();
    await audioContext.resume();
    if (!audioBuffer) {
      try {
        const response = await fetch(config.audio);
        audioBuffer = await audioContext.decodeAudioData(await response.arrayBuffer());
      } catch {
        throw new Error('音频解码失败，请使用浏览器可播放的 WAV、MP3 或 M4A 文件重建。');
      }
    }
  }

  function audioFrom(offset, destination = audioContext?.destination) {
    if (!audioBuffer || offset >= audioBuffer.duration) return null;
    const source = audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(destination);
    source.start(0, offset);
    return source;
  }

  async function togglePreview() {
    if (play.textContent === '暂停') {
      stopPreview();
      return;
    }
    const run = ++sequence;
    play.textContent = '暂停';
    try {
      await prepareAudio();
      if (sequence !== run) return;
      const startAt = cursor >= duration ? 0 : cursor;
      voice = audioFrom(startAt);
      const began = performance.now();
      const tick = now => {
        try {
          const elapsed = startAt + (now - began) / 1000;
          showFrame(elapsed);
          if (elapsed < duration) playback = requestAnimationFrame(tick);
          else stopPreview();
        } catch (error) {
          stopPreview();
          failure(error);
        }
      };
      playback = requestAnimationFrame(tick);
    } catch (error) {
      stopPreview();
      failure(error);
    }
  }

  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  function beginRecording(stream) {
    for (const mimeType of candidates) {
      try {
        const recorder = new MediaRecorder(stream, {mimeType, videoBitsPerSecond: 8_000_000});
        const chunks = [];
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
        const done = new Promise((resolve, reject) => {
          recorder.onstop = () => resolve(new Blob(chunks, {type: recorder.mimeType || mimeType}));
          recorder.onerror = event => reject(event.error || new Error('浏览器录像失败。'));
        });
        recorder.start();
        return {recorder, done};
      } catch {
        // Codec capability checks can succeed even when the encoder cannot start.
      }
    }
    throw new Error('浏览器的编码器无法启动。可换一个浏览器打开 HTML。');
  }

  async function exportVideo() {
    if (exporting) return;
    stopPreview();
    exporting = true;
    const buttons = [play, scrub, record, png, chapter];
    buttons.forEach(control => { control.disabled = true; });
    const previousTime = cursor;
    let stream, recorder, source, destination, frameRequest, visibilityHandler;
    try {
      message('正在准备导出…');
      await prepareAudio();
      const output = document.createElement('canvas');
      const scale = Math.min(1, 1920 / Math.max(canvas.width, canvas.height));
      output.width = Math.max(2, Math.floor(canvas.width * scale / 2) * 2);
      output.height = Math.max(2, Math.floor(canvas.height * scale / 2) * 2);
      const target = output.getContext('2d', {alpha: false});
      const frame = time => {
        showFrame(time);
        target.fillStyle = '#000';
        target.fillRect(0, 0, output.width, output.height);
        target.drawImage(canvas, 0, 0, output.width, output.height);
      };
      frame(0);
      stream = output.captureStream(fps);
      if (audioBuffer) {
        destination = audioContext.createMediaStreamDestination();
        destination.stream.getAudioTracks().forEach(track => stream.addTrack(track));
      }
      const run = beginRecording(stream);
      recorder = run.recorder;
      let finishFrames;
      const frames = new Promise((resolve, reject) => {
        finishFrames = resolve;
        const began = performance.now();
        visibilityHandler = () => {
          if (document.hidden) reject(new Error('导出中页面离开前台。回到页面后可重新导出。'));
        };
        document.addEventListener('visibilitychange', visibilityHandler);
        source = destination ? audioFrom(0, destination) : null;
        const tick = now => {
          try {
            const elapsed = (now - began) / 1000;
            frame(elapsed);
            message(`正在导出 ${Math.min(duration, elapsed).toFixed(1)} / ${duration.toFixed(1)} 秒，请保持页面在前台。`);
            if (elapsed < duration) frameRequest = requestAnimationFrame(tick);
            else {
              if (recorder.state !== 'inactive') recorder.stop();
              resolve();
            }
          } catch (error) { reject(error); }
        };
        frameRequest = requestAnimationFrame(tick);
      });
      const [blob] = await Promise.all([run.done.then(result => {
        finishFrames();
        return result;
      }), frames]);
      if (!blob.size || cursor < duration) throw new Error('浏览器提前结束录像，请重试。');
      const extension = blob.type.startsWith('video/mp4') ? 'mp4' : 'webm';
      if (videoUrl) URL.revokeObjectURL(videoUrl);
      videoUrl = URL.createObjectURL(blob);
      download.href = videoUrl;
      download.download = `${fileName}.${extension}`;
      download.textContent = `下载 ${extension.toUpperCase()}`;
      download.hidden = false;
      message(`视频已生成（${output.width} × ${output.height}）。`);
    } catch (error) {
      failure(error);
    } finally {
      document.removeEventListener('visibilitychange', visibilityHandler);
      cancelAnimationFrame(frameRequest);
      if (recorder && recorder.state !== 'inactive') recorder.stop();
      stream?.getTracks().forEach(track => track.stop());
      if (source) source.stop();
      exporting = false;
      buttons.forEach(control => { control.disabled = false; });
      try { showFrame(previousTime); } catch (error) { failure(error); }
    }
  }

  play.onclick = togglePreview;
  scrub.oninput = () => {
    stopPreview();
    try { showFrame(+scrub.value); } catch (error) { failure(error); }
  };
  chapter.onchange = () => {
    stopPreview();
    const era = chapters[chapter.selectedIndex];
    const view = era.transition ? era.transition.dur + (era.transition.delay || 0) + 0.015 : 0;
    try { showFrame(era.t0 + view); } catch (error) { failure(error); }
  };
  png.onclick = () => {
    const shot = cursor.toFixed(2);
    canvas.toBlob(blob => {
      if (blob) downloadBlob(blob, `${fileName}-${shot}s.png`);
      else message('浏览器无法编码当前帧。');
    }, 'image/png');
  };
  record.onclick = exportVideo;
  window.motionReady.then(() => {
    document.body.classList.toggle('alpha', config.alpha);
    document.getElementById('meta').textContent = `${canvas.width} × ${canvas.height}`;
    scrub.max = duration;
    if (hasChapters) {
      chapters.forEach((era, index) => {
        chapter.append(new Option(era.chapter || era.name || `分镜 ${index + 1}`, String(index)));
      });
      chapter.hidden = false;
    }
    showFrame(0);
    [play, scrub, png].forEach(control => { control.disabled = false; });
    record.disabled = candidates.length === 0;
    record.textContent = mp4Supported ? '导出视频' : '导出 WebM';
    message(config.alpha ? '透明画面可保存为 PNG。' : candidates.length
      ? '' : '当前浏览器支持预览与 PNG，视频编码不可用。');
  }).catch(failure);
})();
