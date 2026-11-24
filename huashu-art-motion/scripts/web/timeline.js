window.attachMotionShots = async function () {
  const shotCanvas = document.createElement('canvas');
  [shotCanvas.width, shotCanvas.height] = window.FILM_SIZE;
  for (const era of window.ERAS) {
    if (era.transition && !Object.hasOwn(window.TRANSITIONS, era.transition.type)) {
      throw new Error(`转场未注册：${era.transition.type}`);
    }
    if (era.motionSpec) {
      const draw = await window.createMotionClip(
        era.motionSpec, window.MOTION_GRAMMARS[era.id], shotCanvas
      );
      const last = Math.max(0, era.dur - 1 / era.motionSpec.fps);
      era.draw = (context, time) => {
        draw(Math.max(0, Math.min(time, last)));
        context.drawImage(shotCanvas, 0, 0);
      };
    } else if (!era.draw) {
      const sceneId = era.motionScene || era.id;
      const scene = Object.hasOwn(window.SCENES, sceneId) && window.SCENES[sceneId];
      if (!scene || typeof scene.draw !== 'function') {
        throw new Error(`未注册场景 SCENES.${sceneId}`);
      }
      era.draw = scene.draw;
      era.init = scene.init;
    }
  }
};
