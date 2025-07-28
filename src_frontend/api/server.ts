import axios from "axios";
import { ControlPoint } from "@/stores/VelocityEditorState";
const serverUrl = "http://127.0.0.1:3596/";

export async function POST<T>(endPoint: string, data: Object) {
  const response = await axios.post<any, { data: T }>(
    serverUrl + endPoint,
    data
  );
  return response.data;
}

export function getSettings() {
  const res = POST("get_settings", {});
  return res;
}

export function setSettings(repo_path: string, data_device: string, colmap_bin_path: string) {
  const res = POST("set_settings", {
    repo_path: repo_path,
    data_device: data_device,
    colmap_bin_path: colmap_bin_path,
  });
  return res;
}

export function openProject(project_name: string) {
  const res = POST("open_project", {
    project_name: project_name,
  });
  return res;
}

export function getMaxStabilizationStrength(videoSlug: string, start: number, end: number) {
  const res = POST(
    "get_maximum_stabilization_strength",
    {
      video_name: videoSlug,
      start_percent: start,
      end_percent: end,
    }
  );
  return res;
}

export function concatVideos(pickedVideosOrder: string[]) {
  const concatVideoOrder = pickedVideosOrder.map(
    (videoName) => videoName
  );
  return POST("concatenate_video", {
    concatenation_order: concatVideoOrder,
    final_video_name: ".temp_final_video",
  });
}

export function render_video(pickedVideosOrder: string[]) {
  const final_video_name = prompt("Please enter the video's name: ");
  const concatVideoOrder = pickedVideosOrder.map(
    (videoName) => videoName
  );
  return POST("render_final_video", {
    concatenation_order: concatVideoOrder,
    final_video_name: final_video_name,
  });
}

export function cancel_stabilization(videoSlug: string) {
  return POST("cancel_stabilization", {video_name: videoSlug});
}

export function get_pos_and_rot_at_progress_percent(videoSlug: string, progress: number) {
  return POST("get_pos_and_rot_at_progress_percent", {video_name: videoSlug, percent: progress});
}

export function stabilizeVideo(
  videoName: string,
  stabilizationStrength: number = 1,
  localVelocityAdjustmentCurve: ControlPoint[] = [
    { x: 0, y: 1 },
    { x: 1, y: 1 },
  ],
  start_percent: number, end_percent: number
) {
  const local_velocity_adjustment_curve_x = localVelocityAdjustmentCurve.map(
    (point) => point.x
  );

  const local_velocity_adjustment_curve_y = localVelocityAdjustmentCurve.map(
    (point) => point.y
  );

  return POST("stabilize_video", {
    video_name: videoName,
    start_percent: start_percent,
    end_percent: end_percent,
    stabilization_strength: stabilizationStrength,
    local_velocity_adjustment_curve_x,
    local_velocity_adjustment_curve_y,
  });
}


export function load_video(video_name: string) {
  return POST("load_video", {
    video_name: video_name,
  });
}

export function suggest_clips(picked_videos: Array<string>) {
  return POST("suggest_clips", {picked_videos: picked_videos});
}

export function upload_file(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  return axios.post(serverUrl + "upload_file", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}

export function remove_file(fileName: string) {
  return POST("remove_file", {
    file_name: fileName,
  });
}

export function create_project(project_data: any) {
  return POST("create_project", project_data);
}