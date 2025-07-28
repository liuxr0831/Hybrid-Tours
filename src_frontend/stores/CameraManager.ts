import { makeAutoObservable } from "mobx";
import { CameraState, cameraStateLoader } from "../api/cameraTrajectoryLoader";
import { clamp } from "@/utils/mathUtils";
import { Camera } from "@react-three/fiber";
import { PerspectiveCamera } from "three";
import { VideoStates } from "./VideoStates";
import { get_pos_and_rot_at_progress_percent } from "@/api/server";

export type WebglCanvasType = "cameraViewCanvas" | "ThirdPersonViewCanvas";
export class CameraManager {
  id: string;
  videoSlug: string;
  cameraTrajectory: CameraState[];
  currentProgress: number = 0; // a value from 0 to 1
  cur_original_progress: number = 0;
  isPlaying: boolean = false;
  animationFrameId: number | null = null;
  lastTimeStamp?: number;
  isUsingKeyboardControl: boolean = false;
  selectedCanvas: WebglCanvasType = "ThirdPersonViewCanvas";
  cameraViewCanvas: {
    showCameraTrajectory: boolean;
    camera: Camera;
    translationVelocity: number;
    rotationVelocity: number;
  } = {
    camera: new PerspectiveCamera(63.03712292, 16 / 9, 0.1, 100),
    showCameraTrajectory: false,
    translationVelocity: 1,
    rotationVelocity: 1,
  };
  thirdPersonViewCanvas: {
    showCameraTrajectory: boolean;
    camera: Camera;
    translationVelocity: number;
    rotationVelocity: number;
  } = {
    camera: new PerspectiveCamera(63.03712292, 16 / 9, 0.1, 100),
    showCameraTrajectory: true,
    translationVelocity: 0.5,
    rotationVelocity: 0.5,
  };
  cam_aspect_ratio: Number = 16/9;
  parent_video_state?: VideoStates;
  real_frames: Array<string> = [];
  current_real_frame: string = '';
  camera_trajectory_mesh_color_array: Array<number> = new Array(1).fill(0);

  setTimeOutHandle?: number;
  velocityEditorProgressShouldFollowMouse: boolean = true;
  allowKeyboardControl: boolean = true;
  isDraggingProgressBar: boolean = false;

  constructor(videoSlug: string, cameraTrajectory: CameraState[], cam_fov_y: number, cam_aspect_ratio: number) {
    makeAutoObservable(
      this,
      {
        // cameraViewCanvas: observable.ref,
        // thirdPersonViewCanvas: observable.ref,
      },
      { autoBind: true }
    );
    this.videoSlug = videoSlug;
    this.id = "cameraManager-" + videoSlug;
    this.cameraTrajectory = cameraTrajectory;
    this.cam_aspect_ratio = cam_aspect_ratio;
    this.cameraViewCanvas.camera = new PerspectiveCamera(cam_fov_y, cam_aspect_ratio, 0.1, 100);
    this.thirdPersonViewCanvas.camera = new PerspectiveCamera(cam_fov_y, cam_aspect_ratio, 0.1, 100);
  }

  set_parent_video_state(parent_video_state: VideoStates) {
    this.parent_video_state = parent_video_state;
    const color_array = hexToRgbArray(this.parent_video_state?.video_color);
    this.camera_trajectory_mesh_color_array = new Array(this.cameraTrajectory.length).fill(0).flatMap((_, i) => color_array);
  }

  set_current_progress_by_original_progress(original_progress: number, start_progress: number, end_progress: number) {
    if (original_progress >= start_progress && original_progress <= end_progress) {
      const original_ts_progress = (original_progress-start_progress)/(end_progress-start_progress);
      const current_progress = this.find_current_progress_by_original_progress(original_ts_progress, 0, 1, -1);
      this.setCurrentProgress(current_progress);
    } else {
      get_pos_and_rot_at_progress_percent(this.parent_video_state?.videoSlug, original_progress).then((res) => {
        this.setCameraState("cameraViewCanvas", cameraStateLoader(res.pos, res.rot));
      });
    }
  }

  find_current_progress_by_original_progress(goal_original_progress: number, current_guess_lower: number, current_guess_higher: number, last_index: number) {
    const current_guess = current_guess_lower/2 + current_guess_higher/2;
    const closestIndex = this.getClosestIndexByProgress(current_guess);
    if (closestIndex === last_index) {
      return closestIndex / this.cameraTrajectory.length;
    }
    const current_original_progress = this.cameraTrajectory[closestIndex].original_video_ts / this.cameraTrajectory[this.cameraTrajectory.length-1].original_video_ts;
    if (Math.abs((current_original_progress - goal_original_progress)) < 0.001) {
      return current_guess;
    } else if (current_original_progress > goal_original_progress) {
      return this.find_current_progress_by_original_progress(goal_original_progress, current_guess_lower, current_guess, closestIndex)
    } else {
      return this.find_current_progress_by_original_progress(goal_original_progress, current_guess, current_guess_higher, closestIndex)
    }
  }

  set_real_frames(real_frames: Array<string>) {
    this.real_frames = real_frames;
    this.setCurrentProgress(0);
  }

  setIsUsingKeyboardControl(isUsingKeyboardControl: boolean) {
    this.isUsingKeyboardControl = isUsingKeyboardControl;
  }
  setIsDraggingProgressBar(isDraggingProgress: boolean) {
    this.isDraggingProgressBar = isDraggingProgress;
  }

  toggleVelocityEditorProgressShouldFollowMouse() {
    this.velocityEditorProgressShouldFollowMouse =
      !this.velocityEditorProgressShouldFollowMouse;
  }
  toggleAllowKeyboardControl() {
    this.allowKeyboardControl = !this.allowKeyboardControl;
  }
  getShouldShowCameraTrajectory(canvas: WebglCanvasType) {
    return canvas === "cameraViewCanvas"
      ? this.cameraViewCanvas.showCameraTrajectory
      : this.thirdPersonViewCanvas.showCameraTrajectory;
  }
  toggleShouldShowCameraTrajectory(canvas: WebglCanvasType) {
    if (canvas === "cameraViewCanvas") {
      this.cameraViewCanvas.showCameraTrajectory =
        !this.cameraViewCanvas.showCameraTrajectory;
    } else {
      this.thirdPersonViewCanvas.showCameraTrajectory =
        !this.thirdPersonViewCanvas.showCameraTrajectory;
    }
  }

  updateCameraTrajectory(cameraTrajectory: CameraState[]) {
    this.cameraTrajectory = cameraTrajectory;
    const color_array = hexToRgbArray(this.parent_video_state?.video_color);
    this.camera_trajectory_mesh_color_array = new Array(cameraTrajectory.length).fill(0).flatMap((_, i) => color_array);
  }

  get currentCameraState() {
    return this.getCameraStateByProgress(this.currentProgress);
  }

  getCurrentImgName() {
    return this.currentCameraState.imgName;
  }

  getVelocitySetting(canvas: WebglCanvasType): {
    translationVelocity: number;
    rotationVelocity: number;
  } {
    const { translationVelocity, rotationVelocity } =
      canvas === "cameraViewCanvas"
        ? this.cameraViewCanvas
        : this.thirdPersonViewCanvas;
    return { translationVelocity, rotationVelocity };
  }

  setTranslationVelocity(canvas: WebglCanvasType, velocity: number) {
    if (canvas === "cameraViewCanvas") {
      this.cameraViewCanvas.translationVelocity = velocity;
    } else {
      this.thirdPersonViewCanvas.translationVelocity = velocity;
    }
  }

  setRotationVelocity(canvas: WebglCanvasType, velocity: number) {
    if (canvas === "cameraViewCanvas") {
      this.cameraViewCanvas.rotationVelocity = velocity;
    } else {
      this.thirdPersonViewCanvas.rotationVelocity = velocity;
    }
  }

  setCameraState(canvas: WebglCanvasType, cameraState: CameraState) {
    const camera =
      canvas === "cameraViewCanvas"
        ? this.cameraViewCanvas.camera
        : this.thirdPersonViewCanvas.camera;
    if (!camera) {
      throw new Error("Camera not set");
    }
    syncCameraStateToCamera(cameraState, camera);
  }

  getCameraState(canvas: WebglCanvasType): CameraState {
    const cameraController =
      canvas === "cameraViewCanvas"
        ? this.cameraViewCanvas.camera
        : this.thirdPersonViewCanvas.camera;
    if (!cameraController) {
      throw new Error("Camera controller not set");
    }
    return getCameraStateFromCamera(cameraController);
  }

  setCameraForTheFirstTime(
    canvas: WebglCanvasType,
    camera: Camera,
    initialView?: CameraState
  ) {
    // if intial view specified, set it
    if (initialView) {
      syncCameraStateToCamera(initialView, camera);
    } else {
      // set intial view to be the first camera state
      syncCameraStateToCamera(this.currentCameraState, camera);
    }
    this.setCamera(canvas, camera);
  }

  setCamera(canvas: WebglCanvasType, camera: Camera) {
    if (canvas === "cameraViewCanvas") {
      this.cameraViewCanvas.camera = camera;
    } else {
      this.thirdPersonViewCanvas.camera = camera;
    }
  }

  selectCanvas(canvas: WebglCanvasType) {
    this.selectedCanvas = canvas;
  }

  getCameraControllerOfSelectedView(): Camera {
    return this.getCamera(this.selectedCanvas);
  }

  getCamera(canvas: WebglCanvasType): Camera {
    return canvas === "cameraViewCanvas"
      ? this.cameraViewCanvas.camera
      : this.thirdPersonViewCanvas.camera;
  }

  getClosestIndexByProgress(progress: number) {
    return clamp(
      Math.round(progress * this.cameraTrajectory.length),
      0,
      this.cameraTrajectory.length - 1
    );
  }

  getCameraStateByProgress(progress: number): CameraState {
    const closestIndex = this.getClosestIndexByProgress(progress);
    const cameraState = this.cameraTrajectory[closestIndex];
    this.cur_original_progress = this.parent_video_state?.sampled_percents[this.parent_video_state.stabilized_trim_start] + (cameraState.original_video_ts / this.cameraTrajectory[this.cameraTrajectory.length-1].original_video_ts) * (this.parent_video_state?.sampled_percents[this.parent_video_state.stabilized_trim_end] - this.parent_video_state?.sampled_percents[this.parent_video_state.stabilized_trim_start]);
    return cameraState;
  }

  setCurrentProgressByFrameIndex(index: number) {
    const progress = index / this.cameraTrajectory.length;
    this.setCurrentProgress(progress);
  }

  setCurrentProgress(progress: number) {
    this.currentProgress = progress;
    this.setCameraState("cameraViewCanvas", this.currentCameraState);
    if (this.is_using_real_footage) {
      this.current_real_frame = this.real_frames[this.getClosestIndexByProgress(progress)];
    }
  }

  get is_using_real_footage() {
    const frame_i = this.getClosestIndexByProgress(this.currentProgress);
    return this.parent_video_state && !(this.parent_video_state.is_stabilized) && (!!this.real_frames[frame_i]) && ((frame_i-1 >= 0 && !!this.real_frames[frame_i-1]) || (frame_i+1 < this.real_frames.length && !!this.real_frames[frame_i+1]));
  }

  startPlaying() {
    if (!this.isPlaying) {
      this.isPlaying = true;
      this.animationFrameId = requestAnimationFrame(this.updateProgress);
      // setTimeout(this.updateProgress, FRAME_TIME);
    }
  }

  stopPlaying() {
    if (this.isPlaying) {
      this.isPlaying = false;
      if (this.animationFrameId) {
        cancelAnimationFrame(this.animationFrameId);
        this.animationFrameId = null;
      }
      this.lastTimeStamp = undefined;
      // if (this.setTimeOutHandle) {
      //   clearTimeout(this.setTimeOutHandle);
      //   this.setTimeOutHandle = undefined;
      // }
    }
  }

  // totaltime in milliseconds
  get totalTime() {
    const lastCameraState = this.cameraTrajectory[this.cameraTrajectory.length - 1];
    const firstCameraState = this.cameraTrajectory[0];
    if (lastCameraState.ts === undefined || firstCameraState.ts === undefined) {
      return null;
    }
    return (lastCameraState.ts - firstCameraState.ts) * 1000;
  }

  updateProgress = (timestamp: number) => {
    const lastTimeStamp = this.lastTimeStamp || timestamp;
    const timeElapsed = timestamp - lastTimeStamp;
    this.lastTimeStamp = timestamp;
    let nextProgress = 0; // initialize next progress
    if (!this.totalTime) {
      nextProgress = this.currentProgress + 0.01;
    } else {
      const currentTime = this.currentProgress * this.totalTime;
      const nextTime = currentTime + timeElapsed;
      nextProgress = nextTime / this.totalTime;
    }
    if (nextProgress > 1) {
      this.setCurrentProgress(0);
    } else {
      this.setCurrentProgress(nextProgress);
    }
    this.animationFrameId = requestAnimationFrame(this.updateProgress);
    // this.setTimeOutHandle = setTimeout(this.updateProgress, FRAME_TIME);
  };

  togglePlaying() {
    if (this.isPlaying) {
      this.stopPlaying();
    } else {
      this.startPlaying();
    }
  }
}

export function syncCameraStateToCamera(
  cameraState: CameraState,
  camera: Camera
) {
  if (cameraState.position !== undefined) {
    camera.position.copy(cameraState.position);
    camera.rotation.copy(cameraState.rotation);
  }
}

export function syncCamera(from: Camera, to: Camera) {
  to.position.copy(from.position.clone());
  to.rotation.copy(from.rotation.clone());
}

export function getCameraStateFromCamera(camera: Camera) {
  return {
    position: camera.position.clone(),
    rotation: camera.rotation.clone(),
  };
}

export function canvasTypeFormatter(canvasType: WebglCanvasType) {
  return canvasType === "cameraViewCanvas" ? "Camera View" : "Scene View";
}


function hexToRgbArray(hex: string): [number, number, number] {
  // Remove the "#" if it exists
  hex = hex.replace(/^#/, '');

  // Parse the hex string into red, green, and blue components
  const r = parseInt(hex.slice(0, 2), 16) / 255;
  const g = parseInt(hex.slice(2, 4), 16) / 255;
  const b = parseInt(hex.slice(4, 6), 16) / 255;

  return [r, g, b];
}