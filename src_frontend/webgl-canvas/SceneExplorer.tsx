import { WebglCanvasType } from "@/stores/CameraManager";
import { observer } from "mobx-react-lite";
import WebglCanvas from "./WebglCanvas";
import WebglCanvasController from "./WebglCanvasController";
import WebglCanvasHeading from "./WebglCanvasHeading";

function SceneExplorer({ canvasType }: { canvasType: WebglCanvasType }) {
  return (
    <div className="h-full flex flex-col text-center" style={{width: '30vw'}}>
      <WebglCanvasHeading canvasType={canvasType} />
      <div className="flex-1">
        <WebglCanvas canvasType={canvasType} />
      </div>
      <WebglCanvasController canvasType={canvasType} />
    </div>
  );
}
export default observer(SceneExplorer);
