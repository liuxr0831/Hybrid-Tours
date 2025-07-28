import { makeAutoObservable, action } from "mobx";
import { CameraManager } from "./CameraManager";
import { stabilizeVideo, getMaxStabilizationStrength } from "@/api/server";
import { VelocityEditorState, ControlPoint } from "./VelocityEditorState";

export class VideoStates {
  videoSlug: string;
  videoUrl: string;
  cameraManager?: CameraManager;
  velocityEditorState: VelocityEditorState;
  stabilizationStrength: number = 1;
  maxStabilizationStrength: number = 2;
  is_stabilized: boolean = false;
  is_stabilizable: boolean = true;
  is_before_other_video_ok: boolean = true;
  is_after_other_video_ok: boolean = true;
  sampled_percents: Array<number> = [];
  cur_trim_start: number = 0;
  cur_trim_end: number = 1;
  stabilized_trim_start: number = 0;
  stabilized_trim_end: number = 1;
  velocity_smoothing_strength: number = 0;
  velocity_smoothing_percents: Array<number> = [];
  velocity_smoothing_multipliers: Array<number> = [];
  is_forced_to_be_stabilized_by_mega_video: boolean = false;
  video_color: string = "#AAAAAA";
  is_edited_by_user: boolean = false;
  suggestion_for_next_clip: Array<string> = [];
  trim_for_suggested_clips: { [key: string]: Array<number> } = {};
  is_suggested_as_next_clip: boolean = false;
  is_suggested_to_be_stabilized: boolean = false;
  note: string = "";

  constructor(videoSlug: string, videoUrl: string, is_stabilizable: boolean, is_before_other_video_ok: boolean, is_after_other_video_ok: boolean, sampled_percents: Array<number>) {
    makeAutoObservable(this, {set_is_stabilized: action}, { autoBind: true });
    this.videoSlug = videoSlug;
    this.videoUrl = videoUrl;
    this.cameraManager = undefined;
    this.velocityEditorState = new VelocityEditorState(this); // Here, velocity adjustment curve samples should be from trimmed start to trimmed end
    this.is_stabilizable = is_stabilizable;
    this.is_stabilized = false;
    this.is_before_other_video_ok = is_before_other_video_ok;
    this.is_after_other_video_ok = is_after_other_video_ok;
    if (this.is_stabilizable) {
      this.sampled_percents = sampled_percents;
    } else {
      this.sampled_percents = [0,1]
    }
    this.cur_trim_start = 0;
    this.cur_trim_end = this.sampled_percents.length-1;
    this.stabilizationStrength = 1;
    this.maxStabilizationStrength = 2;
    this.stabilized_trim_start = 0;
    this.stabilized_trim_end = this.sampled_percents.length-1;
    this.note = videoSlug;
  }

  set_is_suggested_to_be_stabilized(is_suggested_to_be_stabilized: boolean) {
    this.is_suggested_to_be_stabilized = is_suggested_to_be_stabilized;
  }

  set_is_suggested_as_next_clip(is_suggested_as_next_clip: boolean){
    this.is_suggested_as_next_clip = is_suggested_as_next_clip;
  }

  set_suggestion_for_next_clip(suggestion_for_next_clip: Array<string>) {
    this.suggestion_for_next_clip = suggestion_for_next_clip
  }

  set_trim_for_suggested_clips(trim_for_suggested_clips: { [key: string]: Array<number> }) {
    this.trim_for_suggested_clips = trim_for_suggested_clips;
  }

  reset_stabilization_settings() {
    this.velocity_smoothing_strength = 0.0
    this.velocityEditorState = new VelocityEditorState(this);
    this.stabilizationStrength = 1;
    this.cur_trim_start = 0;
    this.cur_trim_end = this.sampled_percents.length-1;
    this.stabilized_trim_start = 0;
    this.stabilized_trim_end = this.sampled_percents.length-1;
  }

  setCameraManager(cameraTrajectoryManager: CameraManager) {
    this.cameraManager = cameraTrajectoryManager;
  }

  setStabilizationStrength(stabilizationStrength: number) {
    this.stabilizationStrength = stabilizationStrength;
  }

  set_max_stabilization_strength(max_stabilization_strength: number) {
    this.maxStabilizationStrength = max_stabilization_strength;
    if (this.stabilizationStrength > max_stabilization_strength) {
      this.stabilizationStrength = max_stabilization_strength;
    }
  }

  set_is_forced_to_be_stabilized_by_mega_video(tf: boolean) {
    this.is_forced_to_be_stabilized_by_mega_video = tf;
  }

  set_is_stabilized(is_stabilized: boolean) {
    this.is_stabilized = is_stabilized;
  }

  set_is_stabilizable(is_stabilizable: boolean) {
    this.is_stabilizable = is_stabilizable;
  }

  set_video_color(video_color: string) {
    this.video_color = video_color;
  }

  set_is_edited_by_user(is_edited_by_user: boolean) {
    this.is_edited_by_user = is_edited_by_user;
  }

  set_note(note: string) {
    this.note = note;
  }


  set_sampled_percents(sampled_percents: Array<number>) {
    this.sampled_percents = sampled_percents;
    this.stabilized_trim_start = 0;
    this.stabilized_trim_end = this.sampled_percents.length-1;
    this.cur_trim_start = 0;
    this.cur_trim_end = this.sampled_percents.length-1;
  }

  set_velocity_smoothing_percent_and_multipliers(percents: Array<number>, multipliers: Array<number>) {
    this.velocity_smoothing_percents = percents;
    this.velocity_smoothing_multipliers = multipliers;
  }

  set_velocity_smoothing_strength(smoothing_strength: number) {
    this.velocity_smoothing_strength = smoothing_strength;
    const global_multiplier = 1.4;
    const max_adjustment_value = 4.0;
    const control_points: ControlPoint[] = [];
    if (smoothing_strength > 0) {
      if (this.sampled_percents[this.stabilized_trim_start] > 0.0) {
        control_points.push({ x: 0, y: 1 });
      }
      for (let percent_i = 0; percent_i < this.velocity_smoothing_percents.length; percent_i++) {
        control_points.push({ x: this.velocity_smoothing_percents[percent_i] * (this.sampled_percents[this.stabilized_trim_end]-this.sampled_percents[this.stabilized_trim_start]) + this.sampled_percents[this.stabilized_trim_start], y: Math.min(1/global_multiplier * (1-smoothing_strength) + this.velocity_smoothing_multipliers[percent_i]/global_multiplier * smoothing_strength, max_adjustment_value/global_multiplier) });
      }
      if (this.sampled_percents[this.stabilized_trim_end] < 1.0) {
        control_points.push({ x: 1, y: 1 });
      }
      this.velocityEditorState.setGlobalVelocityMultiplier(global_multiplier);
    } else {
      control_points.push({ x: 0, y: 1 });
      control_points.push({ x: 1, y: 1 });
      this.velocityEditorState.setGlobalVelocityMultiplier(1.0);
    }
    
    this.velocityEditorState.setControlPoints(control_points);
  }

  async set_cur_trim_start_end(min_value: number, max_value: number) {
    if (min_value === this.cur_trim_start && max_value === this.cur_trim_end) {
      return;
    }
    this.cameraManager?.setIsDraggingProgressBar(true);
    if (max_value-min_value >= 4) {
      if (min_value === this.cur_trim_start) {
        this.cameraManager?.set_current_progress_by_original_progress(this.sampled_percents[max_value], this.sampled_percents[this.stabilized_trim_start], this.sampled_percents[this.stabilized_trim_end]);
        this.cur_trim_end = max_value;
      } else if (max_value === this.cur_trim_end) {
        this.cameraManager?.set_current_progress_by_original_progress(this.sampled_percents[min_value], this.sampled_percents[this.stabilized_trim_start], this.sampled_percents[this.stabilized_trim_end]);
        this.cur_trim_start = min_value;
      }
    } else if (min_value === this.cur_trim_start) {
      this.cur_trim_end = this.cur_trim_start + 4;
    } else if (max_value === this.cur_trim_end) {
      this.cur_trim_start = this.cur_trim_end - 4;
    }
    const res = await getMaxStabilizationStrength(this.videoSlug, this.sampled_percents[this.cur_trim_start], this.sampled_percents[this.cur_trim_end])
    this.set_max_stabilization_strength(res.maximum_stabilization_strength);
  }

  get totalTime() {
    return this.cameraManager?.totalTime;
  }

  sentStabilizeVideoRequest(is_using_current: boolean = true) {
    if (is_using_current) {
      this.stabilized_trim_start = this.cur_trim_start;
      this.stabilized_trim_end = this.cur_trim_end;
    }
    const curveSamples = this.velocityEditorState.getSamples(1000, this.sampled_percents[this.stabilized_trim_start], this.sampled_percents[this.stabilized_trim_end]);
    return stabilizeVideo(
      this.videoSlug,
      this.stabilizationStrength,
      curveSamples,
      this.sampled_percents[this.stabilized_trim_start],
      this.sampled_percents[this.stabilized_trim_end]
    );
  }
}
