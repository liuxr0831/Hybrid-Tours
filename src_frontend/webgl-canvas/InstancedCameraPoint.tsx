import { useRef, useEffect, useContext } from "react";
import { GlobalStateContext } from "../stores/globalState";
import * as THREE from "three";
import { CameraState } from "@/api/cameraTrajectoryLoader";

const tempObject = new THREE.Object3D();

export function InstancedCameraPoint({
  cameraTrajectory,
}: {
  cameraTrajectory: CameraState[];
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const globalState = useContext(GlobalStateContext);
  const colorArray = Float32Array.from(globalState.camera_trajectory_mesh_color_array);

  useEffect(() => {
    if (meshRef.current) {
      cameraTrajectory.forEach((cameraState, index) => {
        if (cameraState.position !== undefined) {
          tempObject.position.copy(cameraState.position);
          tempObject.rotation.copy(cameraState.rotation);
          tempObject.updateMatrix();
          meshRef.current!.setMatrixAt(index, tempObject.matrix);
        }
      });
      meshRef.current.instanceMatrix.needsUpdate = true;
    }
  }, [cameraTrajectory]);

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, cameraTrajectory.length]}
    >
      <boxGeometry args={[0.1, 0.01, 0.001]}>
        <instancedBufferAttribute
          attach="attributes-color"
          args={[colorArray, 3]}
        />
      </boxGeometry>
      <meshBasicMaterial vertexColors />
    </instancedMesh>
  );
}
