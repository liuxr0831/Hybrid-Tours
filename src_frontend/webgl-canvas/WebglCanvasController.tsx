import { Slider } from "@/components/ui/slider";
import { VelocitySlider } from "@/components/ui/velocitySlider";
import { WebglCanvasType } from "@/stores/CameraManager";
import { GlobalStateContext } from "@/stores/globalState";
import { Move, Rotate3D } from "lucide-react";
import { observer } from "mobx-react-lite";
import React, { useContext, useEffect } from "react";
import { FaPlay, FaPause } from "react-icons/fa";

const PlayPauseButtonStyle = "w-4 h-4";
const VelocityControlStyle =
  "h-full flex justify-center items-center space-x-3 w-56";
function WebglCanvasController({
  canvasType,
}: {
  canvasType: WebglCanvasType;
}) {
  const globalState = useContext(GlobalStateContext);
  const { currentPage } = globalState;
  const currentCameraManager = globalState.currentCameraManager;
  useEffect(() => {
    if (currentCameraManager) {
      // currentCameraManager.startPlaying();
      return () => {
        currentCameraManager.stopPlaying();
      };
    }
  }, [currentCameraManager]);
  if (!currentCameraManager) {
    return null;
  }

  // set and goto ground plane view
  // const { groundPlaneView, setGroundPlaneView, goToGroundPlaneView } =
  //   globalState;

  // velocity control
  const { getVelocitySetting, setTranslationVelocity, setRotationVelocity } =
    currentCameraManager;
  const { translationVelocity, rotationVelocity } =
    getVelocitySetting(canvasType);

  // playing control
  const { isPlaying, togglePlaying, currentProgress, setCurrentProgress } =
    currentCameraManager;

  const currentFrameImgName = currentCameraManager.getCurrentImgName();
  const isCameraView = canvasType === "cameraViewCanvas";
  return (
    <div className="w-full">
      <div className="bg-dark-800 rounded-b-lg ">
        <div className="w-full flex flex-col justify-center space-y-4 "  style={{height: "2.5vh"}}>
          {isCameraView && (
            <Slider
              onDrag={(e) => {
                // console.log(e);
              }}
              onPointerDown={() => {
                currentCameraManager.setIsDraggingProgressBar(true);
              }}
              onPointerUp={() => {
                currentCameraManager.setIsDraggingProgressBar(false);
              }}
              value={[currentProgress * 100.0]}
              step={100/currentCameraManager.cameraTrajectory.length}
              onValueChange={([value]) => {
                setCurrentProgress(value / 100.0);
              }}
              style={{zIndex: 15}}
            />
          )}
        </div>
        <div className="flex items-center py-2 space-x-2 text-3xs px-4 justify-between" style={{height: "5vh"}}>
          {/* <Button onClick={setGroundPlaneView}>Set Ground</Button> */}
          <div className={VelocityControlStyle}>
            <VelocityControlIcon>
              <Move />
            </VelocityControlIcon>
            <VelocitySlider
              min={0.1}
              max={10}
              step={0.01}
              value={[translationVelocity]}
              onValueChange={([value]) =>
                setTranslationVelocity(canvasType, value)
              }
            />
          </div>
          {isCameraView && currentPage !== "EnvironmentExplorer" && (
            <Button onClick={togglePlaying}>
              {isPlaying ? (
                <FaPause className={PlayPauseButtonStyle} />
              ) : (
                <FaPlay
                  className={PlayPauseButtonStyle}
                  style={{
                    position: "relative",
                    left: "1px",
                  }}
                />
              )}
            </Button>
          )}
          <div className={VelocityControlStyle}>
            <VelocitySlider
              min={0.1}
              max={10}
              step={0.01}
              value={[rotationVelocity]}
              onValueChange={([value]) =>
                setRotationVelocity(canvasType, value)
              }
            />
            <VelocityControlIcon>
              <Rotate3D />
            </VelocityControlIcon>
          </div>
          {/* <Button
            disabled={!groundPlaneView}
            onClick={() => goToGroundPlaneView(canvasType)}
          >
            Goto Ground
          </Button> */}
        </div>
      </div>
      {isCameraView && currentFrameImgName && (
        <p className="font-semibold mt-4">{currentFrameImgName}</p>
      )}
    </div>
  );
}

function Button(
  props: React.PropsWithChildren<
    React.DetailedHTMLProps<
      React.ButtonHTMLAttributes<HTMLButtonElement>,
      HTMLButtonElement
    >
  >
) {
  return (
    <button
      className="bg-dark-700 text-white  rounded-full cursor-pointer p-3 "
      {...props}
    >
      {props.children}
    </button>
  );
}

function VelocityControlIcon({ children }: React.PropsWithChildren) {
  return <div className="flex flex-col items-center py-2">{children}</div>;
}

export default observer(WebglCanvasController);
