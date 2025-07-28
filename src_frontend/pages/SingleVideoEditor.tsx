import SceneExplorer from "@/webgl-canvas/SceneExplorer";
import { observer } from "mobx-react-lite";
import VelocityEditor from "@/velocity-editor/VelocityEditor";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { useContext, useRef } from "react";
import { GlobalStateContext } from "@/stores/globalState";
import { useMutation } from "@tanstack/react-query";
import { cancel_stabilization, load_video } from "@/api/server";
import { Loader2 } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import MultiRangeSlider from "multi-range-slider-react";
import { convert_to_cameraTrajectory } from "@/api/cameraTrajectoryLoader";

function SingleVideoEditor() {
  const globalState = useContext(GlobalStateContext);
  if (globalState.project_name !== "") {
    const { currentVideoState, pickedVideosOrder, sendRenderVideoRequest, sendConcatVideosRequest } = globalState;
    const { stabilizationStrength, maxStabilizationStrength, sentStabilizeVideoRequest, setStabilizationStrength, set_cur_trim_start_end, set_velocity_smoothing_strength, note, set_note } =
      currentVideoState;
    const { currentCameraManager } = globalState;
    const is_concat_again_needed = useRef(false);

    async function set_stabilize_video() {
      if (!currentVideoState.is_stabilized) {
        if (globalState.selectedVideoSlug === ".temp_final_video") {
          for (let video_i = 0; video_i < globalState.pickedVideosOrder.length; video_i++) {
            if (!globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].is_stabilized) {
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].reset_stabilization_settings();
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_is_stabilized(true);
              const res = await globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].sentStabilizeVideoRequest();
              const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].cameraManager?.updateCameraTrajectory(cameraTrajectory);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].cameraManager?.setCurrentProgress(0);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_max_stabilization_strength(res.max_stabilization_strength)
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_is_forced_to_be_stabilized_by_mega_video(true);
              is_concat_again_needed.current = true;
            }
          }
          if (is_concat_again_needed.current) {
            is_concat_again_needed.current = false;
            const res = await sendConcatVideosRequest();
            currentVideoState.set_sampled_percents(res.sampled_percents);
          }
          const res = await sentStabilizeVideoRequest(false);
          currentVideoState.set_is_stabilized(true);
          return res;
        } else {
          if (globalState.pickedVideosOrder.includes(globalState.selectedVideoSlug)) {
            // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
            globalState.is_concat_changed = true;
            globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
            globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
          }
          const res = await sentStabilizeVideoRequest(false);
          currentVideoState.set_is_stabilized(true);
          currentVideoState.set_is_forced_to_be_stabilized_by_mega_video(false);
          currentVideoState.set_is_edited_by_user(true);
          return res;
        }
      } else {
        if (globalState.selectedVideoSlug === ".temp_final_video") {
          for (let video_i = 0; video_i < globalState.pickedVideosOrder.length; video_i++) {
            if (globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].is_forced_to_be_stabilized_by_mega_video) {
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_is_forced_to_be_stabilized_by_mega_video(false);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_is_stabilized(false);
              const res = await cancel_stabilization(globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].videoSlug);
              const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].cameraManager?.updateCameraTrajectory(cameraTrajectory);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].cameraManager?.setCurrentProgress(0);
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_max_stabilization_strength(res.max_stabilization_strength)
              globalState.videoStatesStore[globalState.pickedVideosOrder[video_i]].set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
              is_concat_again_needed.current = true;
            }
          }
          currentVideoState.set_is_stabilized(false);
          const res = await cancel_stabilization(currentVideoState.videoSlug);
          if (is_concat_again_needed.current) {
            is_concat_again_needed.current = false;
            const res = await sendConcatVideosRequest();
            currentVideoState.set_sampled_percents(res.sampled_percents);
          }
          return res;
        } else {
          if (globalState.pickedVideosOrder.includes(globalState.selectedVideoSlug)) {
            // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
            globalState.is_concat_changed = true;
            globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
            globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
          }
          currentVideoState.set_is_stabilized(false);
          currentVideoState.set_is_forced_to_be_stabilized_by_mega_video(false);
          currentVideoState.set_is_edited_by_user(true);
          const res = await cancel_stabilization(currentVideoState.videoSlug);
          return res;
        }
      }
    }

    const { mutate: mutate_stabilize_video, isPending } = useMutation({
      mutationKey: ["change stabilize video"],
      mutationFn: set_stabilize_video,
      onSuccess: (res) => {
        const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
        currentCameraManager?.updateCameraTrajectory(cameraTrajectory);
        currentCameraManager?.setCurrentProgress(0);
        currentVideoState.set_max_stabilization_strength(res.max_stabilization_strength)
        currentVideoState.set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
      },
      onError: (err) => {
        //@ts-ignore
        console.error(err.response.data);
      },
    });

    async function change_setting() {
        if (globalState.pickedVideosOrder.includes(globalState.selectedVideoSlug)) {
          // globalState.videoStatesStore['.temp_final_video'].set_is_stabilized(false);
          globalState.is_concat_changed = true;
          globalState.videoStatesStore['.temp_final_video'].set_is_stabilizable(false);
          globalState.videoStatesStore['.temp_final_video'].reset_stabilization_settings();
        }
        const res = await sentStabilizeVideoRequest();
        return res;
    }

    const { mutate: change_stabilization_setting, isPending: isPending2 } = useMutation({
      mutationKey: ["change_stabilization_setting"],
      mutationFn: change_setting,
      onSuccess: (res) => {
        const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.original_video_ts);
        currentCameraManager?.updateCameraTrajectory(cameraTrajectory);
        currentCameraManager?.setCurrentProgress(0);
        currentVideoState.set_max_stabilization_strength(res.max_stabilization_strength)
        currentVideoState.set_velocity_smoothing_percent_and_multipliers(res.velocity_smoothing_percents, res.velocity_smoothing_multipliers)
        currentVideoState.set_is_forced_to_be_stabilized_by_mega_video(false);
      },
      onError: (err) => {
        //@ts-ignore
        console.error(err.response.data);
      },
    });


    const cantConcat = pickedVideosOrder.length < 2;
    
    const {
      isSuccess: concatIsSuccess,
      mutate: concatMutate,
      isPending: concatIsPending,
    } = useMutation({
      mutationFn: sendConcatVideosRequest,
      onSuccess: (res) => {
        const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.ts);
        currentCameraManager?.updateCameraTrajectory(cameraTrajectory);
        currentCameraManager?.setCurrentProgress(0);
        currentCameraManager?.set_real_frames(res.frames);
        currentVideoState.set_sampled_percents(res.sampled_percents);
        currentVideoState.set_is_stabilized(false);
      },
      onError: (err) => {
        console.log(err);
      },
    });

    const { mutate: renderMutate, isPending: renderIsPending } = useMutation({
      mutationFn: sendRenderVideoRequest,
      onSuccess: (res) => {
        alert(res.msg);
      }
    });

    function load_video_with_name() {
      return load_video('29X');
    }

    const {
      isSuccess: a,
      mutate: c,
      isPending: b,
    } = useMutation({
      mutationFn: load_video_with_name,
      onSuccess: (res) => {
        const cameraTrajectory = convert_to_cameraTrajectory(res.pos, res.rot, res.ts, res.ts);
        currentCameraManager?.updateCameraTrajectory(cameraTrajectory);
        currentCameraManager?.setCurrentProgress(0);
        currentCameraManager?.set_real_frames(res.frames);
        currentVideoState.set_sampled_percents(res.sampled_percents);
        currentVideoState.set_is_stabilized(false);
      },
      onError: (err) => {
        // @ts-ignore
        console.error(err.response.data);
      },
    });

    return (
      <div className="w-full h-full flex flex-col space-y-2"> 
        <div
          className="flex justify-center space-x-2 items-start w-full px-10"
        >
          <div style={{width: '30vw'}}><SceneExplorer canvasType="ThirdPersonViewCanvas" /></div>
          <div style={{width: '30vw'}}><SceneExplorer canvasType="cameraViewCanvas" /></div>
          
        </div>
        <div className="w-full h-60 cursor-pointer flex px-3 text-white">
          {/* <InfoPanel /> */}
          <div className="py-2 flex flex-col space-y-2">
            {/* <SettingPanel>
              <div className="flex flex-col space-y-1 items-end">
                <p>Allow Keyboard Control</p>
                <Switch
                  checked={currentCameraManager?.allowKeyboardControl}
                  onCheckedChange={() => {
                    currentCameraManager?.toggleAllowKeyboardControl();
                  }}
                />
              </div>
              <div className="flex flex-col space-y-1 items-end">
                <p>Progress Follow Mouse</p>
                <Switch
                  checked={
                    currentCameraManager?.velocityEditorProgressShouldFollowMouse
                  }
                  onCheckedChange={() => {
                    currentCameraManager?.toggleVelocityEditorProgressShouldFollowMouse();
                  }}
                />
              </div>
            </SettingPanel> */}
          </div>
          <div className="flex flex-col flex-1 pt-2">
            <div className='flex flex-row text-xs font-semibold pl-5 pr-7'>
              <p>Trim:</p>
              <div className='grow'>
                <MultiRangeSlider 
                  disabled = {!currentVideoState.is_stabilized || (isPending || isPending2 || renderIsPending || concatIsPending)}
                  label={false}
                  ruler={false}
                  style={{ border: "none", boxShadow: "none", padding: "0.35em 0em 0em 1.2em"}}
                  barInnerColor="#A9CE54"
                  min={0}
                  max={currentVideoState.sampled_percents.length-1}
                  minValue={currentVideoState.is_stabilized? currentVideoState.cur_trim_start : 0}
                  maxValue={currentVideoState.is_stabilized? currentVideoState.cur_trim_end : currentVideoState.sampled_percents.length-1}
                  onInput={(e) => {
                    if (currentVideoState.is_stabilized) {
                      // currentCameraManager?.setIsDraggingProgressBar(true);
                      set_cur_trim_start_end(e.minValue, e.maxValue);
                    } else {
                      currentCameraManager?.setIsDraggingProgressBar(false);
                    }
                  }}
                  onChange={(e) => {
                    if (currentVideoState.is_stabilized) {
                      currentCameraManager?.setIsDraggingProgressBar(false);
                    }
                  }}
                />
              </div>
            </div>
            <VelocityEditor />
          </div>

          <div className=" h-full rounded-xl flex flex-col space-y-2 justify-between py-2 select-none">
            <SettingPanel>
              <div className="flex flex-col space-y-1">
                <p>Stabilize This Video</p>
                <Switch checked={currentVideoState.is_stabilized} disabled={!currentVideoState.is_stabilizable || (isPending || isPending2 || renderIsPending || concatIsPending)} onCheckedChange={() => mutate_stabilize_video()}/>
              </div>
              <div>
                <p>Stabalization Strength</p>
                <div className="mt-1.5 h-5 mb-1">
                  <Slider
                    disabled = {!currentVideoState.is_stabilized || (isPending || isPending2 || renderIsPending || concatIsPending)}
                    value={currentVideoState.is_stabilized? [currentVideoState.stabilizationStrength] : [1]}
                    min={1}
                    max={currentVideoState.is_stabilized? maxStabilizationStrength: 10}
                    step={1}
                    onValueChange={([value]) => {
                      if (currentVideoState.is_stabilized) {
                        setStabilizationStrength(value);
                      }
                    }}
                    style={{ height: "100%" }}
                  />
                </div>
              </div>
              <div>
                <p>Velocity Smoothing</p>
                <div className="mt-1.5 h-5 mb-1">
                  <Slider
                    disabled = {!currentVideoState.is_stabilized || (isPending || isPending2 || renderIsPending || concatIsPending)}
                    value={currentVideoState.is_stabilized? [currentVideoState.velocity_smoothing_strength] : [0]}
                    min={0}
                    max={1}
                    step={0.01}
                    onValueChange={([value]) => {
                      if (currentVideoState.is_stabilized) {
                        set_velocity_smoothing_strength(value);
                      }
                    }}
                    style={{ height: "100%" }}
                  />
                </div>
              </div>
            </SettingPanel>
            <div className="h-full flex justify-center items-center  rounded-md">
              <Button
                disabled={(isPending || isPending2 || renderIsPending || concatIsPending) || !currentVideoState.is_stabilized}
                variant={"primary"}
                onClick={() => change_stabilization_setting()}
              >
                {(isPending || isPending2 || concatIsPending) && (
                  <Loader2 className="mr-2 h-5 w-5 animate-spin size-24" />
                )}
                {(isPending || isPending2 || concatIsPending) ? "Updating..." : "Update Video"}
              </Button>
            </div>
          </div>
        </div>
        {globalState.currentPage === "ConcatenatedVideo" &&  <div className="mt-12 flex space-x-2  justify-center items-center ">
          <Button
            variant={cantConcat ? "default" : "primary"}
            disabled={isPending || isPending2 || cantConcat || concatIsPending || renderIsPending}
            onClick={() => concatMutate()}
          >
            {concatIsPending && (
              <Loader2 className="mr-2 h-5 w-5 animate-spin size-24" />
            )}
            {concatIsPending
              ? "Concatenating"
              : concatIsSuccess
              ? "Concatenate Again"
              : "Concatenate Clips"}
          </Button>
          {currentCameraManager && (
            <Button
              disabled={isPending || isPending2 || renderIsPending || concatIsPending || currentCameraManager.totalTime == 0}
              onClick={() => renderMutate()}
            >
              {renderIsPending && (
                <Loader2 className="mr-2 h-5 w-5 animate-spin size-24" />
              )}
              {renderIsPending ? "Rendering" : "Render Video"}
            </Button>
          )}
        </div>}
        {globalState.currentPage === "SingleVideoEditor" && <div className="w-full flex space-x-2 justify-left items-center">
            <p className="font-semibold">Note: </p>
            <input type="text" value={note} style={{ color: 'white', backgroundColor: '#1D1D1D', flex: '1'}} onChange={(event) => {
                set_note(event.target.value);
            }} onFocus={() => {currentCameraManager?.toggleAllowKeyboardControl();}} onBlur={() => {currentCameraManager?.toggleAllowKeyboardControl()}}/>
        </div>}
      </div>
    );
  } else {
    return (<div></div>);
  }
}

function SettingPanel({ children }: React.PropsWithChildren<{}>) {
  return (
    <div className="bg-dark-800 rounded-md px-4 pt-3 pb-2 space-y-2 text-xs font-semibold text-start select-none">
      {children}
    </div>
  );
}

export default observer(SingleVideoEditor);
