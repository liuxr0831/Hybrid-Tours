import { useRef, useEffect, useContext } from "react";
import {
  ArcballControls,
  CameraControls,
  FlyControls,
  OrbitControls,
  PointerLockControls,
  PresentationControls,
  TrackballControls,
} from "@react-three/drei";
import { GlobalStateContext } from "../stores/globalState";
import { observer } from "mobx-react-lite";
import { PerspectiveCamera } from "three";
import {
  WebglCanvasType,
  syncCamera,
  syncCameraStateToCamera,
} from "@/stores/CameraManager";
import { Camera, useThree } from "@react-three/fiber";
import { Vector3 } from "three";
import * as THREE from "three";
import { OrbitControls as OrbitControlsObject } from "three/examples/jsm/controls/OrbitControls.js";

export const SyncedCamera = observer(
  ({ canvasType }: { canvasType: WebglCanvasType }) => {
    const globalState = useContext(GlobalStateContext);
    const cameraManager = globalState.currentCameraManager;
    if (!cameraManager) {
      return null;
    }
    const {
      getCamera,
      currentCameraState,
      isPlaying,
      isUsingKeyboardControl,
      isDraggingProgressBar: isDraggingProgress,
    } = cameraManager;
    const { set, controls } = useThree();
    const storedCamera = getCamera(canvasType);
    useEffect(() => {
      set({ camera: storedCamera });
      syncCameraStateToCamera(currentCameraState, storedCamera);
    }, [controls]);

    useEffect(() => {
      if (canvasType === "cameraViewCanvas") {
        syncCameraStateToCamera(currentCameraState, storedCamera);
      }

      if (controls) {
        const { up, target } = getUpAndTargetFromCamera(storedCamera);
        const orbitControls = controls as OrbitControlsObject;
        orbitControls.target = target;
        orbitControls.object.up = up;
      }
    }, [storedCamera, controls, isPlaying, isDraggingProgress]);

    useEffect(() => {
      if (controls) {
        const { up, target } = getUpAndTargetFromCamera(storedCamera);
        const orbitControls = controls as OrbitControlsObject;
        orbitControls.target = target;
        orbitControls.object.up = up;
      }
    }, [isUsingKeyboardControl]);

    return (
      <OrbitControls
        enabled={(globalState.currentPage==="EnvironmentExplorer" && !isUsingKeyboardControl && !isPlaying && !isDraggingProgress) || (canvasType!="cameraViewCanvas" && !isUsingKeyboardControl && ((!isPlaying && !isDraggingProgress) || canvasType==="ThirdPersonViewCanvas"))}
        camera={storedCamera}
        makeDefault
      />
    );
    // return <PresentationControls />;
  }
);

function getUpAndTargetFromCamera(camera: Camera) {
  const target = new Vector3(0, 0, -1)
    .applyEuler(camera.rotation)
    .add(camera.position);
  const up = new Vector3(0, 1, 0).applyEuler(camera.rotation);
  return { up, target };
}
