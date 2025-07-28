import { makeAutoObservable, action } from "mobx";
import { createContext } from "react";
import { VideoStates } from "./VideoStates";
import { arrayMove } from "@dnd-kit/sortable";
import { arrayInsert } from "../utils/sortutils";
import {
  loadEnvironmentExplorerCameraTrajectory,
  convert_to_cameraTrajectory,
  CameraState
} from "@/api/cameraTrajectoryLoader";
import {
  CameraManager,
} from "./CameraManager";
import { concatVideos, openProject, render_video, suggest_clips } from "@/api/server";
import ConcatVideoPage from "@/pages/ConcatVideoPage";

export class GlobalState {
  project_name: string = "";

  // an array storing all to be concatenated video slugs
  // e.g. [1.mp4, 2.mp4, 3.mp4, 4.mp4, 5.mp4]
  currentPage: PageType = "OpenCreateProject";
  allVideosOrder: string[] = [];
  videoStatesStore: { [key: string]: VideoStates } = {};
  pickedVideosOrder: string[] = [];
  pickedVideosContainerIsHavingValidDragOverItem?: boolean = undefined; // true/false/undefined
  selectedVideoSlug: string = "";
  prev_selectedVideoSlug: string = "";
  cam_fov_y: number = 63;
  cam_aspect_ratio: number = 16 / 9;
  envExplorerCameraManager?: CameraManager;
  concatenatedVideoCameraManager?: CameraManager;
  displayed_image: string = '';
  is_concat_changed: boolean = true;

  constructor() {
    makeAutoObservable(this, {set_all_video_order: action}, { autoBind: true });
  }

  async open_project(project_name: string) {
    this.init(project_name);
    this.load_cam_params();
    this.initEnvExplorerCameraManager();
    const open_project_response = await openProject(project_name);
    const all_videos = Object.keys(open_project_response);
    for (let video_i = 0; video_i < all_videos.length; video_i++) {
      const cur_video_name = all_videos[video_i];
      const videoUrl = "../../data/" + this.project_name + "/to_be_concatenated/" + cur_video_name;
      this.videoStatesStore[cur_video_name] = new VideoStates(cur_video_name, videoUrl, open_project_response[cur_video_name].is_stabilizable, open_project_response[cur_video_name].is_before_other_video_ok, open_project_response[cur_video_name].is_after_other_video_ok, open_project_response[cur_video_name].sampled_percents);
      this.videoStatesStore[cur_video_name].setCameraManager(new CameraManager(cur_video_name, convert_to_cameraTrajectory(open_project_response[cur_video_name].pos, open_project_response[cur_video_name].rot, open_project_response[cur_video_name].ts, open_project_response[cur_video_name].ts), this.cam_fov_y, this.cam_aspect_ratio))
      this.videoStatesStore[cur_video_name].set_video_color(hslToHex(360/all_videos.length*video_i, 100, 50));
      this.videoStatesStore[cur_video_name].cameraManager.set_parent_video_state(this.videoStatesStore[cur_video_name]);
      this.videoStatesStore[cur_video_name].cameraManager.set_real_frames(open_project_response[cur_video_name].frames);
      this.videoStatesStore[cur_video_name].set_suggestion_for_next_clip(open_project_response[cur_video_name].suggestion_for_next_clip);
      this.videoStatesStore[cur_video_name].set_trim_for_suggested_clips(open_project_response[cur_video_name].trim_for_suggested_clips);
    }
    this.videoStatesStore[".temp_final_video"] = new VideoStates(".temp_final_video", "", false, false, false, [0.0, 1.0]);
    this.videoStatesStore[".temp_final_video"].setCameraManager(new CameraManager(".temp_final_video", convert_to_cameraTrajectory([[0,0,0]], [[[1,0,0],[0,1,0],[0,0,1]]], [0], [0]), this.cam_fov_y, this.cam_aspect_ratio))
    this.videoStatesStore[".temp_final_video"].cameraManager.set_parent_video_state(this.videoStatesStore[".temp_final_video"]);
    this.videoStatesStore[".temp_final_video"].cameraManager.set_real_frames([open_project_response[all_videos[0]].frames[0]]);
    this.selectedVideoSlug = all_videos[0];
    this.prev_selectedVideoSlug = this.selectedVideoSlug;
    this.set_all_video_order(all_videos);
  }

  update_suggestions() {
    for (let video_i = 0; video_i < this.allVideosOrder.length; video_i++) {
      this.videoStatesStore[this.allVideosOrder[video_i]].set_is_suggested_as_next_clip(false);
    }
    for (let video_i = 0; video_i < this.pickedVideosOrder.length; video_i++) {
      let cur_video_name = this.pickedVideosOrder[video_i];
      // Last picked video
      if (video_i==this.pickedVideosOrder.length-1) {
        // to suggest following clips, this video must be able to stay ahead of other clips
        if (this.videoStatesStore[cur_video_name].is_before_other_video_ok) {
          for (let suggest_clip_i = 0; suggest_clip_i < this.videoStatesStore[cur_video_name].suggestion_for_next_clip.length; suggest_clip_i++) {
            let cur_suggested_clip_name = this.videoStatesStore[cur_video_name].suggestion_for_next_clip[suggest_clip_i]
            // if the current suggested clip does not over-trim the current clip, is not edited by user, and is not already picked
            if (!this.videoStatesStore[cur_suggested_clip_name].is_edited_by_user && this.videoStatesStore[cur_video_name].trim_for_suggested_clips[cur_suggested_clip_name][0] > this.videoStatesStore[cur_video_name].stabilized_trim_start + 5 && !this.pickedVideosOrder.includes(cur_suggested_clip_name)) {
              this.videoStatesStore[cur_suggested_clip_name].set_is_suggested_as_next_clip(true);
            }
          }
        }
      } 
      // Not last picekd video
      else {
        let next_video_name = this.pickedVideosOrder[video_i+1];
        // current video or next video edited by user
        if (this.videoStatesStore[cur_video_name].is_edited_by_user || this.videoStatesStore[next_video_name].is_edited_by_user) {
          // then don't automatically change both current and next yet
          this.videoStatesStore[cur_video_name].set_is_suggested_to_be_stabilized(false);
          this.videoStatesStore[next_video_name].set_is_suggested_to_be_stabilized(false);
        } 
        // current video not edited by user
        else {
          // and next one is also suggested
          if (this.videoStatesStore[cur_video_name].suggestion_for_next_clip.includes(next_video_name)) {
            // so if current video can be stabilized and trimming does not make the current video too short
            if (this.videoStatesStore[cur_video_name].is_stabilizable && this.videoStatesStore[cur_video_name].trim_for_suggested_clips[next_video_name][0]-5 > this.videoStatesStore[cur_video_name].stabilized_trim_start) {
              // we trim the current video
              this.videoStatesStore[cur_video_name].set_is_suggested_to_be_stabilized(true);
              this.videoStatesStore[cur_video_name].stabilized_trim_end = this.videoStatesStore[cur_video_name].trim_for_suggested_clips[next_video_name][0];
              // and if the next video is also stabilizable, we trim the next video
              if (this.videoStatesStore[next_video_name].is_stabilizable) {
                this.videoStatesStore[next_video_name].set_is_suggested_to_be_stabilized(true);
                this.videoStatesStore[next_video_name].stabilized_trim_start = this.videoStatesStore[cur_video_name].trim_for_suggested_clips[next_video_name][1];
              }
            }
            // so if current video cannot be stabilized or trimming makes the current video too short
            else {
              // then don't automatically change next yet
              // this.videoStatesStore[cur_video_name].set_is_suggested_to_be_stabilized(false);
              this.videoStatesStore[next_video_name].set_is_suggested_to_be_stabilized(false);
            }
          }
          // and next one is not suggested
          else {
            // then don't automatically change next yet
            // this.videoStatesStore[cur_video_name].set_is_suggested_to_be_stabilized(false);
            this.videoStatesStore[next_video_name].set_is_suggested_to_be_stabilized(false);
          }
        }
      }
    }
  }

  async suggest_clips() {
    const res = await suggest_clips(this.pickedVideosOrder);
    this.pickedVideosOrder = res.picked_videos;
    this.update_suggestions()
  }

  set_all_video_order(all_video_order: string[]) {
    this.allVideosOrder = all_video_order;
  }

  async initEnvExplorerCameraManager() {
    this.envExplorerCameraManager = new CameraManager(
      "envExplorer",
      await loadEnvironmentExplorerCameraTrajectory(this.project_name),
      this.cam_fov_y,
      this.cam_aspect_ratio
    );
    this.envExplorerCameraManager.selectCanvas("cameraViewCanvas");
  }

  async load_cam_params() {
    const tbc_video_info_raw = await fetch(`../../data/${this.project_name}/gaussian_splatting_reconstruction/cameras.json`);
    const tbc_video_info = await tbc_video_info_raw.json();
    const cam_params_raw = [tbc_video_info[0]['fx'], tbc_video_info[0]['fy'], tbc_video_info[0]['width'], tbc_video_info[0]['height']];
    this.cam_fov_y = (2*Math.atan2(cam_params_raw[3]/2, cam_params_raw[1])) * 180 / Math.PI;
    this.cam_aspect_ratio = cam_params_raw[2] / cam_params_raw[3];
  }

  init(project_name: string) {
    this.allVideosOrder = [];
    this.videoStatesStore = {};
    this.pickedVideosOrder = [];
    this.pickedVideosContainerIsHavingValidDragOverItem = undefined; // true/false/undefined
    this.selectedVideoSlug = "";
    this.project_name = project_name;
  }

  setFakeConcatVideoCameraManager() {
    this.concatenatedVideoCameraManager = this.currentVideoState.cameraManager;
  }

  setConcatVideoFromServerResponse(pos: [], rot: [], ts: [], frames: []) {
    const cameraTrajectory = convert_to_cameraTrajectory(pos, rot, ts, ts);
    if (!this.concatenatedVideoCameraManager) {
      this.concatenatedVideoCameraManager = new CameraManager(
        "ConcatenatedVideo",
        cameraTrajectory,
        this.cam_fov_y,
        this.cam_aspect_ratio
      );
      this.concatenatedVideoCameraManager.set_real_frames(frames);
    } else {
      this.concatenatedVideoCameraManager.updateCameraTrajectory(
        cameraTrajectory
      );
      this.concatenatedVideoCameraManager.set_real_frames(frames);
    }
  }

  get currentVideoState() {
    return this.videoStatesStore[this.selectedVideoSlug];
  }
  get currentCameraManager() {
    switch (this.currentPage) {
      case "EnvironmentExplorer":
        return this.envExplorerCameraManager;
      case "SingleVideoEditor":
        return this.currentVideoState.cameraManager;
      case "ConcatenatedVideo":
        return this.currentVideoState.cameraManager;
    }
  }

  get all_camera_trajectories() {
    let all_camera_trajectories = [];
    for (let i=0; i<this.allVideosOrder.length; i++) {
      all_camera_trajectories = all_camera_trajectories.concat(this.videoStatesStore[this.allVideosOrder[i]].cameraManager?.cameraTrajectory)
    }
    all_camera_trajectories = all_camera_trajectories.concat(this.videoStatesStore[".temp_final_video"].cameraManager?.cameraTrajectory)
    return all_camera_trajectories
  }

  get camera_trajectory_mesh_color_array() {
    let camera_trajectory_mesh_color_array = [];
    for (let i=0; i<this.allVideosOrder.length; i++) {
      camera_trajectory_mesh_color_array = camera_trajectory_mesh_color_array.concat(this.videoStatesStore[this.allVideosOrder[i]].cameraManager?.camera_trajectory_mesh_color_array)
    }
    camera_trajectory_mesh_color_array = camera_trajectory_mesh_color_array.concat(this.videoStatesStore[".temp_final_video"].cameraManager?.camera_trajectory_mesh_color_array)
    return camera_trajectory_mesh_color_array
  }

  is_video_before_other_ok(videoSlug: string) {
    return this.videoStatesStore[videoSlug].is_stabilized || this.videoStatesStore[videoSlug].is_before_other_video_ok
  }

  is_video_after_other_ok(videoSlug: string) {
    return this.videoStatesStore[videoSlug].is_stabilized || this.videoStatesStore[videoSlug].is_after_other_video_ok 
  }

  setCurrentPage(page: PageType) {
    this.currentPage = page;
    if (page==="ConcatenatedVideo") {
      this.selectedVideoSlug = ".temp_final_video";
    } else if (page==="SingleVideoEditor") {
      this.selectedVideoSlug = this.prev_selectedVideoSlug;
    }
  }

  setPickedVideosContainerIsHavingValidDragOverItem(value?: boolean) {
    this.pickedVideosContainerIsHavingValidDragOverItem = value;
  }

  videoUrlGetter(slug: string) {
    return this.videoStatesStore[slug].videoUrl;
  }

  remove_selected_video(slug: string) {
    if (!this.videoStatesStore[slug].is_edited_by_user) {
      this.videoStatesStore[slug].stabilized_trim_start = 0;
      this.videoStatesStore[slug].stabilized_trim_end = this.videoStatesStore[slug].sampled_percents.length-1;
    }
    this.pickedVideosOrder = this.pickedVideosOrder.filter((item) => item !== slug)
    this.update_suggestions();
  }

  reorderAllVideos(oldIndex: number, newIndex: number) {
    this.allVideosOrder = arrayMove(this.allVideosOrder, oldIndex, newIndex);
  }

  reorderPickedVideos(oldIndex: number, newIndex: number) {

    // Move first video to somewhere else
    const is_move_ok_1 = (oldIndex===0 && newIndex !== oldIndex) ? this.is_video_after_other_ok(this.pickedVideosOrder[oldIndex]) : true;
    
    // Move last video to somewhere else
    const is_move_ok_2 = (oldIndex===this.pickedVideosOrder.length-1 && newIndex !== oldIndex) ? this.is_video_before_other_ok(this.pickedVideosOrder[oldIndex]) : true;

    // Move some video to first
    const is_move_ok_3 = (newIndex===0 && newIndex !== oldIndex) ? this.is_video_after_other_ok(this.pickedVideosOrder[0]) : true;

    // Move some video to last
    const is_move_ok_4 = (newIndex===this.pickedVideosOrder.length-1 && newIndex !== oldIndex) ? this.is_video_before_other_ok(this.pickedVideosOrder[this.pickedVideosOrder.length-1]) : true;

    if (is_move_ok_1 && is_move_ok_2 && is_move_ok_3 && is_move_ok_4) {
      this.pickedVideosOrder = arrayMove(
        this.pickedVideosOrder,
        oldIndex,
        newIndex
      );
    }
    this.update_suggestions();
  }

  insertIntoPickedVideos(slug: string) {
    // new video cannot before nor after, don't insert
    if ( !this.is_video_after_other_ok(slug) && !this.is_video_before_other_ok(slug) ) {
      return;
    }
    // nothing picked, just insert without doing anything
    else if ( this.pickedVideosOrder.length === 0 ) {
      this.pickedVideosOrder = arrayInsert(this.pickedVideosOrder, 0, slug);
    }
    // new video can after but cannot before, only option is insert to end
    else if ( this.is_video_after_other_ok(slug) && !this.is_video_before_other_ok(slug) ) {
      // if last video can before others, insert
      if ( this.is_video_before_other_ok(this.pickedVideosOrder[this.pickedVideosOrder.length-1]) ) {
        this.pickedVideosOrder = arrayInsert(this.pickedVideosOrder, this.pickedVideosOrder.length, slug);
      } 
      // otherwise, we cannot insert this video
    }
    // new video can before but cannot after, only option is insert to start
    else if ( !this.is_video_after_other_ok(slug) && this.is_video_before_other_ok(slug) ) {
      // if first video can after others, insert
      if ( this.is_video_after_other_ok(this.pickedVideosOrder[0]) ) {
        this.pickedVideosOrder = arrayInsert(this.pickedVideosOrder, 0, slug);
      } 
      // otherwise, we cannot insert this video
    }
    // new video can be anywhere
    else {
      // default insert to end
      if ( this.is_video_before_other_ok(this.pickedVideosOrder[this.pickedVideosOrder.length-1]) ) {
        this.pickedVideosOrder = arrayInsert(this.pickedVideosOrder, this.pickedVideosOrder.length, slug);
      } 
      // otherwise insert before last
      else {
        this.pickedVideosOrder = arrayInsert(this.pickedVideosOrder, this.pickedVideosOrder.length-1, slug);
      }
    }

    this.update_suggestions();
  }

  selectVideo(slug: string) {
    if (slug === ".temp_final_video") {
      this.setCurrentPage("ConcatenatedVideo");
    } else {
      this.setCurrentPage("SingleVideoEditor");
    }
    this.selectedVideoSlug = slug;
    if (slug != ".temp_final_video") {
      this.prev_selectedVideoSlug = this.selectedVideoSlug
    }
  }

  async sendConcatVideosRequest() {
    if (!this.is_concat_changed) {
      if (!window.confirm("Do you really want to clear all edits and re-concatenate candidate clips?")) {
        return;
      }
    }

    this.is_concat_changed = false;
    this.videoStatesStore['.temp_final_video'].is_stabilizable = true;
    for (let video_i = 0; video_i < this.pickedVideosOrder.length; video_i++) {
      if (!this.videoStatesStore[this.pickedVideosOrder[video_i]].is_stabilizable) {
        this.videoStatesStore['.temp_final_video'].is_stabilizable = false;
      }
      if (this.videoStatesStore[this.pickedVideosOrder[video_i]].is_suggested_to_be_stabilized) {
        let cur_video_state = this.videoStatesStore[this.pickedVideosOrder[video_i]];
        const temp_stabilized_trim_start = cur_video_state.stabilized_trim_start;
        const temp_stabilized_trim_end = cur_video_state.stabilized_trim_end;
        cur_video_state.stabilized_trim_start = 0;
        cur_video_state.stabilized_trim_end = cur_video_state.sampled_percents.length-1;
        let old_res = await cur_video_state.sentStabilizeVideoRequest(false);
        cur_video_state.cur_trim_start = temp_stabilized_trim_start;
        cur_video_state.cur_trim_end = temp_stabilized_trim_end;
        let res = await cur_video_state.sentStabilizeVideoRequest();
        cur_video_state.set_is_stabilized(true);
        const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
        cur_video_state.cameraManager?.updateCameraTrajectory(cameraTrajectory);
        cur_video_state.cameraManager?.setCurrentProgress(0);
        cur_video_state.set_max_stabilization_strength(res.max_stabilization_strength)
        cur_video_state.set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
      }
    }
    // let max_angle_cost = 180 / 180 * Math.PI;
    // for (let video_i = 0; video_i < this.pickedVideosOrder.length-1; video_i++) {
    //   let last_video_i = video_i;
    //   let next_video_i = video_i+1;
    //   let is_last_video_need_stabilize = false;
    //   let is_next_video_need_stabilize = false;
    //   let last_video_trim_end = -1;
    //   let next_video_trim_start = -1;
    //   let last_video_state = this.videoStatesStore[this.pickedVideosOrder[last_video_i]];
    //   let next_video_state = this.videoStatesStore[this.pickedVideosOrder[next_video_i]];
    //   // both cannot be trimmed
    //   if ((last_video_state.is_edited_by_user && next_video_state.is_edited_by_user) || (!last_video_state.is_stabilizable && !next_video_state.is_stabilizable)) {
    //     continue;
    //   }
    //   // See if default is fine
    //   let last_video_end_cam_state = last_video_state.cameraManager?.getCameraStateByProgress(1.0);
    //   let next_video_start_cam_state = next_video_state.cameraManager?.getCameraStateByProgress(0.0);
    //   let last_video_end_forward_vec = get_forward_vec_from_cam_rotation(last_video_end_cam_state.rotation);
    //   let next_video_start_forward_vec = get_forward_vec_from_cam_rotation(next_video_start_cam_state.rotation);
    //   let translation_vec3 = next_video_start_cam_state?.position.clone().sub(last_video_end_cam_state?.position);
    //   let translation_vec = [translation_vec3?.x, translation_vec3?.y, translation_vec3?.z]
    //   let angle_cost = total_angle_cost_radian(last_video_end_forward_vec, next_video_start_forward_vec, translation_vec);
    //   if (angle_cost[0] + angle_cost[1] < max_angle_cost) {
    //     continue;
    //   }
    //   // last can be trimmed, next cannot be trimmed
    //   if ((last_video_state.is_stabilizable && !last_video_state.is_edited_by_user) && (next_video_state.is_edited_by_user || !next_video_state.is_stabilizable)) {
    //     console.log("try trim last")
    //     for (let trim_end=last_video_state.sampled_percents.length-2; trim_end>4; trim_end--) {
    //       let last_cam_index = last_video_state.cameraManager?.getClosestIndexByProgress(last_video_state.sampled_percents[last_trim_end]);
    //       last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index];
    //       for (let search_range = 1; last_video_end_cam_state.position == undefined; search_range++) {
    //         last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index-search_range];
    //         if (!last_video_end_cam_state.position==undefined) {
    //           break;
    //         }
    //         last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index+search_range];
    //       }
    //       last_video_end_forward_vec = get_forward_vec_from_cam_rotation(last_video_end_cam_state.rotation);
    //       translation_vec3 = next_video_start_cam_state?.position.clone().sub(last_video_end_cam_state?.position);
    //       translation_vec = [translation_vec3?.x, translation_vec3?.y, translation_vec3?.z];
    //       angle_cost = total_angle_cost_radian(last_video_end_forward_vec, next_video_start_forward_vec, translation_vec);
    //       if (angle_cost[0] + angle_cost[1] < max_angle_cost) {
    //         is_last_video_need_stabilize = true;
    //         last_video_trim_end = trim_end;
    //         break;
    //       }
    //     }
    //   }
    //   // last cannot be trimmed, next can be trimmed
    //   else if ((last_video_state.is_edited_by_user || !last_video_state.is_stabilizable) && (!next_video_state.is_edited_by_user && next_video_state.is_stabilizable)) {
    //     console.log("try trim next");
    //     for (let trim_start=0; trim_start<next_video_state.sampled_percents.length-5; trim_start++) {
    //       let next_cam_index = next_video_state.cameraManager?.getClosestIndexByProgress(next_video_state.sampled_percents[next_trim_start]);
    //       next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index];
    //       for (let search_range = 1; next_video_start_cam_state.position == undefined; search_range++) {
    //         next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index-search_range];
    //         if (!next_video_start_cam_state.position==undefined) {
    //           break;
    //         }
    //         next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index+search_range];
    //       }
    //       next_video_start_forward_vec = get_forward_vec_from_cam_rotation(next_video_start_cam_state.rotation);
    //       translation_vec3 = next_video_start_cam_state?.position.clone().sub(last_video_end_cam_state?.position);
    //       translation_vec = [translation_vec3?.x, translation_vec3?.y, translation_vec3?.z];
    //       angle_cost = total_angle_cost_radian(last_video_end_forward_vec, next_video_start_forward_vec, translation_vec);
    //       if (angle_cost[0] + angle_cost[1] < max_angle_cost) {
    //         is_next_video_need_stabilize = true;
    //         next_video_trim_start = trim_start;
    //         break;
    //       }
    //     }
    //   }
    //   // both can be trimmed
    //   else if ((last_video_state.is_stabilizable && !last_video_state.is_edited_by_user) && (!next_video_state.is_edited_by_user && next_video_state.is_stabilizable)) {
    //     console.log("try trim both");
    //     let max_total_trim = last_video_state.sampled_percents.length+next_video_state.sampled_percents.length-11;
    //     for (let total_trim=1; total_trim<max_total_trim; total_trim++) {
    //       for (let last_video_trim=Math.max(total_trim-(next_video_state.sampled_percents.length-5), 0); last_video_trim <= Math.min(total_trim, last_video_state.sampled_percents.length-5); last_video_trim++) {
    //         let last_trim_end = last_video_state.sampled_percents.length - 1 - last_video_trim;
    //         let next_trim_start = total_trim - last_video_trim;
    //         let last_cam_index = last_video_state.cameraManager?.getClosestIndexByProgress(last_video_state.sampled_percents[last_trim_end]);
    //         last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index];
    //         for (let search_range = 1; last_video_end_cam_state.position == undefined; search_range++) {
    //           last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index-search_range];
    //           if (!last_video_end_cam_state.position==undefined) {
    //             break;
    //           }
    //           last_video_end_cam_state = last_video_state.cameraManager?.cameraTrajectory[last_cam_index+search_range];
    //         }
    //         let next_cam_index = next_video_state.cameraManager?.getClosestIndexByProgress(next_video_state.sampled_percents[next_trim_start]);
    //         next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index];
    //         for (let search_range = 1; next_video_start_cam_state.position == undefined; search_range++) {
    //           next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index-search_range];
    //           if (!next_video_start_cam_state.position==undefined) {
    //             break;
    //           }
    //           next_video_start_cam_state = next_video_state.cameraManager?.cameraTrajectory[next_cam_index+search_range];
    //         }
    //         last_video_end_forward_vec = get_forward_vec_from_cam_rotation(last_video_end_cam_state.rotation);
    //         next_video_start_forward_vec = get_forward_vec_from_cam_rotation(next_video_start_cam_state.rotation);
    //         translation_vec3 = next_video_start_cam_state?.position.clone().sub(last_video_end_cam_state?.position);
    //         translation_vec = [translation_vec3?.x, translation_vec3?.y, translation_vec3?.z]
    //         angle_cost = total_angle_cost_radian(last_video_end_forward_vec, next_video_start_forward_vec, translation_vec);
    //         console.log(last_video_trim, next_trim_start, angle_cost);
    //         if (angle_cost[0] + angle_cost[1] < max_angle_cost) {
    //           if (last_video_trim > 0) {
    //             last_video_trim_end = last_trim_end;
    //             is_last_video_need_stabilize = true;
    //           }
    //           if (next_trim_start > 0) {
    //             next_video_trim_start = next_trim_start;
    //             is_next_video_need_stabilize = true;
    //           }
    //           break;
    //         }
    //       }
    //       if (is_next_video_need_stabilize || is_last_video_need_stabilize) {
    //         break;
    //       }
    //     }
    //   }

    //   // stabilize if needed
    //   if (is_last_video_need_stabilize) {
    //     last_video_state.set_cur_trim_start_end(last_video_state.cur_trim_start, last_video_trim_end);
    //     let res = await last_video_state.sentStabilizeVideoRequest();
    //     last_video_state.set_is_stabilized(true);
    //     const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
    //     last_video_state.cameraManager?.updateCameraTrajectory(cameraTrajectory);
    //     last_video_state.cameraManager?.setCurrentProgress(0);
    //     last_video_state.set_max_stabilization_strength(res.max_stabilization_strength)
    //     last_video_state.set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
    //   }
    //   if (is_next_video_need_stabilize) {
    //     next_video_state.set_cur_trim_start_end(next_video_trim_start, next_video_state.cur_trim_end);
    //     let res = await next_video_state.sentStabilizeVideoRequest();
    //     next_video_state.set_is_stabilized(true);
    //     const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
    //     next_video_state.cameraManager?.updateCameraTrajectory(cameraTrajectory);
    //     next_video_state.cameraManager?.setCurrentProgress(0);
    //     next_video_state.set_max_stabilization_strength(res.max_stabilization_strength)
    //     next_video_state.set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
    //   }
    // }
    return concatVideos(this.pickedVideosOrder);
  }

  async sendRenderVideoRequest() {
    return render_video(this.pickedVideosOrder);
  }
}

export const GlobalStateContext = createContext<GlobalState>(new GlobalState());

export type PageType =
  | "OpenCreateProject"
  | "EnvironmentExplorer"
  | "SingleVideoEditor"
  | "ConcatenatedVideo"
  | "Setting";

export const pageTypeFormatter = (pageType: PageType) => {
  switch (pageType) {
    case "OpenCreateProject":
      return "Open or Create Project"
    case "EnvironmentExplorer":
      return "Explore Reconstruction";
    case "SingleVideoEditor":
      return "Edit Candidate Clips";
    case "ConcatenatedVideo":
      return "Concatenate Candidate Clips";
    case "Setting":
      return "Configure Shell Script Settings"
  }
};

function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;

  if (h >= 0 && h < 60) {
      r = c; g = x; b = 0;
  } else if (h >= 60 && h < 120) {
      r = x; g = c; b = 0;
  } else if (h >= 120 && h < 180) {
      r = 0; g = c; b = x;
  } else if (h >= 180 && h < 240) {
      r = 0; g = x; b = c;
  } else if (h >= 240 && h < 300) {
      r = x; g = 0; b = c;
  } else if (h >= 300 && h < 360) {
      r = c; g = 0; b = x;
  }

  const toHex = (n: number) => Math.round((n + m) * 255).toString(16).padStart(2, '0');

  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

import { Matrix4, Matrix3, Euler, Object3D } from "three";

function get_forward_vec_from_cam_rotation(rotation: Euler) {
  const obj = new Object3D();
  obj.rotation.copy(rotation);
  obj.rotation.x = obj.rotation.x-Math.PI;
  const matrix4 = new Matrix4().makeRotationFromEuler(obj.rotation);
  const matrix3 = new Matrix3().setFromMatrix4(matrix4);
  const elements = matrix3.elements;
  return [elements[2], elements[5], elements[8]];
}

function total_angle_cost_radian(last_video_end_forward_vec: Array<number>, next_video_start_forward_vec: Array<number>, translation_vec: Array<number>) {
  let last_to_translation = vector_angle(last_video_end_forward_vec, translation_vec);
  let translation_to_next = vector_angle(translation_vec, next_video_start_forward_vec);
  return [last_to_translation, translation_to_next];
}

function vector_angle(vec1: Array<number>, vec2:Array<number>) {
  return Math.acos((vec1[0]*vec2[0] + vec1[1]*vec2[1] + vec1[2]*vec2[2]) / (Math.sqrt(vec1[0]*vec1[0] + vec1[1]*vec1[1] + vec1[2]*vec1[2])*Math.sqrt(vec2[0]*vec2[0] + vec2[1]*vec2[1] + vec2[2]*vec2[2])))
}