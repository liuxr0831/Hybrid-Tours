import SceneExplorer from "@/webgl-canvas/SceneExplorer";
import { observer } from "mobx-react-lite";

function EnvironmentExplorer() {
  return (
    <div>
      <div className="flex justify-center items-center w-full py-3 h-full">
        <SceneExplorer canvasType="cameraViewCanvas" />
      </div>
    </div>
  );
}

export default observer(EnvironmentExplorer);
