import * as THREE from "three";
import { rotationMatrixToEuler } from "../webgl-canvas/splat/utils/rotationMatrixToEuler";
import { CameraManager } from "../stores/CameraManager";
export type Position = number[]; // 3 elements
export type RotationMat = number[][]; // row-major, 3x3 matrix

export type CameraTrajectoryRaw = {
  pos: Position[];
  rot: RotationMat[];
  ts: number[];
  video_name: string;
};

type EnvExplorerCameraTrajectoryRaw = {
  img_name: string;
  position: Position;
  rotation: RotationMat;
}[];

export type ConcatenatedVideoServerResponse = CameraTrajectoryRaw[];

export type CameraState = {
  position: THREE.Vector3;
  rotation: THREE.Euler;
  ts?: number; // timestamp
  imgName?: string;
  original_video_ts?: number;
};

export function convert_to_cameraTrajectory(pos: [], rot: [], ts: [], original_video_ts: []) {
  return ts.map((timestamp, i) => cameraStateLoader(pos[i], rot[i], timestamp, undefined, original_video_ts[i]))
}

export async function loadEnvironmentExplorerCameraTrajectory(project_name: string) {
  const envExplorerCameraTrjectoryRaw = await fetch(`../../data/${project_name}/gaussian_splatting_reconstruction/cameras.json`);
  const cam_raw = await envExplorerCameraTrjectoryRaw.json();
  return convertEnvExplorerCameraTrajectory(cam_raw);
}

export function convertEnvExplorerCameraTrajectory(
  envExplorerCameraTrajectoryRaw: EnvExplorerCameraTrajectoryRaw
) {
  const pos: Position[] = [];
  const rot: RotationMat[] = [];
  const imgNames: string[] = [];
  envExplorerCameraTrajectoryRaw.forEach(({ position, rotation, img_name }) => {
    pos.push(position);
    rot.push(rotation);
    imgNames.push(img_name);
  });
  return pos.map((position, i) =>
    cameraStateLoader(position, rot[i], undefined, imgNames[i])
  );
}

export function cameraStateLoader(
  pos: Position,
  rotationMat: RotationMat,
  ts?: number, // timestamp,
  imgName?: string,
  original_video_ts?: number
) {
  if (pos){
    const position = new THREE.Vector3(...pos);
    const rotation = rotationMatrixToEuler(rotationMat);
    return { position, rotation, ts, imgName, original_video_ts };
  } else {
    const position = undefined;
    const rotation = undefined;
    return { position, rotation, ts, imgName, original_video_ts }
  }
}

export function concatenatedVideoResultLoader(
  concatenatedVideoResultRaw: ConcatenatedVideoServerResponse
): CameraState[] {
  return concatenatedVideoResultRaw.flatMap(cameraTrajectoryLoader);
}
