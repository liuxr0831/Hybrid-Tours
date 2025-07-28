import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { WebglCanvasType, canvasTypeFormatter } from "@/stores/CameraManager";
import { GlobalStateContext } from "@/stores/globalState";
import { observer } from "mobx-react-lite";
import { useContext } from "react";
const ShowTrajectoryToggleSwitchID = "show-trajectory-toggle";
function WebglCanvasHeading({ canvasType }: { canvasType: WebglCanvasType }) {
  const globalState = useContext(GlobalStateContext);
  const { currentPage } = globalState;
  const currentCameraManager = globalState.currentCameraManager;
  if (!currentCameraManager) {
    return null;
  }
  const { selectedCanvas, selectCanvas, getShouldShowCameraTrajectory } =
    currentCameraManager;
  const shouldShowCameraTrajectory = getShouldShowCameraTrajectory(canvasType);
  return (
    <div className="relative">
      <p
        // onDoubleClick={() => selectCanvas(canvasType)}
        className={
          "font-semibold py-1 inline-block px-3 rounded-t-md select-none text-md cursor-pointer " +
          (selectedCanvas === canvasType
            ? " bg-lightYellow text-darkYellow"
            : " bg-dark-700 text-dark-50")
        }
      >
        {currentPage === "EnvironmentExplorer"
          ? "Scene View"
          : canvasTypeFormatter(canvasType)}
      </p>
      <div>
        <div className="flex items-center space-x-2 absolute right-2 bottom-0 bg-dark-700 py-1.5 px-2.5 text-dark-50 rounded-t-md">
          <Switch
            disabled={currentCameraManager.is_using_real_footage && canvasType === "cameraViewCanvas"}
            id={ShowTrajectoryToggleSwitchID}
            checked={shouldShowCameraTrajectory}
            onCheckedChange={() => {
              currentCameraManager.toggleShouldShowCameraTrajectory(canvasType);
            }}
          />
          <label
            className="font-bold text-2xs"
            htmlFor={ShowTrajectoryToggleSwitchID}
          >
            Show Trajectory
          </label>
        </div>
      </div>
    </div>
  );
}

export default observer(WebglCanvasHeading);
