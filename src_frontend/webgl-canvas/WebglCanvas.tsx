import { Fragment, useContext, useRef, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import { Splat } from "./splat";
//@ts-ignore
import { GlobalStateContext } from "../stores/globalState";
import { observer } from "mobx-react-lite";
import { InstancedCameraPoint } from "./InstancedCameraPoint";
import { SyncedCamera } from "./SyncedCamera";
import { CameraManager, WebglCanvasType } from "@/stores/CameraManager";
import { KeyboardControl } from "./KeyboardControl";
import { CameraState } from "@/api/cameraTrajectoryLoader";
function WebglCanvas({ canvasType }: { canvasType: WebglCanvasType }) {
  const globalState = useContext(GlobalStateContext);
  const cameraTrajectoryManager = globalState.currentCameraManager;
  if (!cameraTrajectoryManager) {
    return null;
  }
  // const { getShouldShowCameraTrajectory, allowKeyboardControl, cam_aspect_ratio, cameraTrajectory } = cameraTrajectoryManager;
  const cameraTrajectory = globalState.all_camera_trajectories;
  const { getShouldShowCameraTrajectory, allowKeyboardControl, cam_aspect_ratio } = cameraTrajectoryManager;
  const shouldShowCameraTrajectory = getShouldShowCameraTrajectory(canvasType);
  const point_cloud_path = `../../data/${globalState.project_name}/gaussian_splatting_reconstruction/point_cloud/iteration_30000/point_cloud.ply`
  return (
    <Fragment>
      {cameraTrajectoryManager && (
        <WebglCanvasUI
          aspect_ratio={cam_aspect_ratio.valueOf()}
          point_cloud_path={point_cloud_path}
          cameraManager={cameraTrajectoryManager}
          is_using_real_footage={cameraTrajectoryManager.is_using_real_footage}
          camera_trajectory={cameraTrajectory}
          shouldShowCameraTrajectory={shouldShowCameraTrajectory}
          canvasType={canvasType}
        >
          {allowKeyboardControl &&
            cameraTrajectoryManager.selectedCanvas === canvasType && (
              <KeyboardControl canvasType={canvasType} />
            )}
          <SyncedCamera
            canvasType={canvasType}
            key={globalState.selectedVideoSlug}
          />
        </WebglCanvasUI>
      )}
    </Fragment>
  );
}

function WebglCanvasUI({
  aspect_ratio,
  point_cloud_path,
  cameraManager,
  shouldShowCameraTrajectory,
  is_using_real_footage,
  camera_trajectory,
  children,
  canvasType
}: React.PropsWithChildren<WebglCanvasUIProps>) {
  
  // compute canvas size
  const custom_width = useRef("100%");
  const custom_height = useRef("100%");
  if (aspect_ratio > 16/9) {
    const new_height = 16 / (aspect_ratio * 9) * 100;
    custom_height.current = `${new_height}%`;
  } else if (aspect_ratio < 16/9) {
    const new_width = (aspect_ratio * 9) / 16 * 100;
    custom_width.current = `${new_width}%`;
  }

  const canvas_ref = useRef();
  useEffect(() => {
    const interval = is_using_real_footage
      ? setInterval(() => {
        const canvas = canvas_ref.current;
        if (canvas && canvasType==="cameraViewCanvas" && cameraManager.is_using_real_footage) {
          canvas.src = `data:image/jpeg;base64,${cameraManager.current_real_frame}`;
        }
      }, 1000/60)
      : null;

    return () => {
      interval ? clearInterval(interval) : {};
    }
  }, [cameraManager, is_using_real_footage])
  
  return (
    <div className="rounded-t-lg h-full aspect-video bg-dark-800 flex flex-col overflow-hidden items-center justify-center">
      <div style={{width: custom_width.current, height: custom_height.current, position: 'relative'}}>
        {cameraManager && (
          <Canvas dpr={[1, 1.5]}>
            {children}
            <color attach="background" args={["#000000"]} />
            {shouldShowCameraTrajectory && (
              <InstancedCameraPoint cameraTrajectory={camera_trajectory} />
            )}
            <Splat rotation={[Math.PI, 0, 0]} src={point_cloud_path} />
            <Environment preset="apartment" />
          </Canvas>
        )}
        { canvasType==="cameraViewCanvas" && cameraManager.is_using_real_footage &&
          (<img
            id="overlayCanvas"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              zIndex: 10, // Adjust the z-index as needed to place it above the 3D canvas
            }}
            ref={canvas_ref}
          />)
        }
        
      </div>
    </div>
  );
}

type WebglCanvasUIProps = {
  aspect_ratio: number,
  point_cloud_path: string,
  cameraManager: CameraManager;
  shouldShowCameraTrajectory: boolean;
  is_using_real_footage: boolean;
  camera_trajectory: CameraState[];
  children: React.ReactNode;
  canvasType: string
};
export default observer(WebglCanvas);
