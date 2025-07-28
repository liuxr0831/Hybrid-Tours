import { GlobalStateContext } from "@/stores/globalState";
import { KeyboardControls, useKeyboardControls } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { observer } from "mobx-react-lite";
import { useContext, useMemo } from "react";
import { Euler, Matrix4, Vector3 } from "three";
import { Camera } from "@react-three/fiber";
import { WebglCanvasType } from "@/stores/CameraManager";

enum Controls {
  moveForward = "moveForward",
  moveLeft = "moveLeft",
  moveRight = "moveRight",
  moveBackward = "moveBackward",
  moveUp = "moveUp",
  moveDown = "moveDown",
  rotateLeft = "rotateLeft",
  rotateRight = "rotateRight",
  lookLeft = "lookLeft",
  lookRight = "lookRight",
  lookUp = "lookUp",
  lookDown = "lookDown",
}

export type KeyboardControlsEntry<T extends string = string> = {
  /** Name of the action */
  name: T;
  /** The keys that define it, you can use either event.key, or event.code */
  keys: string[];
  /** If the event receives the keyup event, true by default */
  up?: boolean;
};

export const KeyboardControl = observer(
  ({ canvasType }: { canvasType: WebglCanvasType }) => {
    const map = useMemo<KeyboardControlsEntry[]>(
      () => [
        { name: Controls.moveForward, keys: ["KeyW"] },
        { name: Controls.moveBackward, keys: ["KeyS"] },
        { name: Controls.moveLeft, keys: ["KeyA"] },
        { name: Controls.moveRight, keys: ["KeyD"] },
        { name: Controls.moveUp, keys: ["Space"] },
        { name: Controls.moveDown, keys: ["ShiftLeft"] },
        { name: Controls.rotateLeft, keys: ["KeyC"] },
        { name: Controls.rotateRight, keys: ["KeyZ"] },
        { name: Controls.lookLeft, keys: ["KeyQ"] },
        { name: Controls.lookRight, keys: ["KeyE"] },
        { name: Controls.lookUp, keys: ["KeyR"] },
        { name: Controls.lookDown, keys: ["KeyF"] },
      ],
      []
    );

    return (
      <KeyboardControls map={map}>
        <ControlContent canvasType={canvasType} />
      </KeyboardControls>
    );
  }
);

const ZeroVector = new Vector3();
const translationVector = new Vector3();
const rotationAxis = new Vector3();

const ControlContent = observer(
  ({ canvasType }: { canvasType: WebglCanvasType }) => {
    const [, get] = useKeyboardControls<Controls>();
    const globalState = useContext(GlobalStateContext);
    const cameraManager = globalState.currentCameraManager!;
    const { translationVelocity, rotationVelocity } =
      cameraManager.getVelocitySetting(canvasType);
    useFrame(({ camera }, delta) => {
      const state = get();
      const { forwardVector, rightVector, upVector } =
        getTranslationVectorsForKeyboardControl(camera);
      cameraManager.setIsUsingKeyboardControl(true);
      let noTranslationControl = false;
      let noRotationControl = false;

      // handle translation
      if (state.moveLeft) {
        translationVector.copy(rightVector.clone().negate());
      } else if (state.moveRight) {
        translationVector.copy(rightVector.clone());
      } else if (state.moveForward) {
        translationVector.copy(forwardVector.clone());
      } else if (state.moveBackward) {
        translationVector.copy(forwardVector.clone().negate());
      } else if (state.moveUp) {
        translationVector.copy(upVector.clone());
      } else if (state.moveDown) {
        translationVector.copy(upVector.clone().negate());
      } else {
        translationVector.copy(ZeroVector);
        noTranslationControl = true;
      }
      camera.position.addScaledVector(
        translationVector,
        translationVelocity * delta
      );

      // handle rotation
      if (state.rotateLeft) {
        rotationAxis.copy(forwardVector.clone());
      } else if (state.rotateRight) {
        rotationAxis.copy(forwardVector.clone().negate());
      } else if (state.lookLeft) {
        rotationAxis.copy(upVector.clone());
      } else if (state.lookRight) {
        rotationAxis.copy(upVector.clone().negate());
      } else if (state.lookUp) {
        rotationAxis.copy(rightVector.clone());
      } else if (state.lookDown) {
        rotationAxis.copy(rightVector.clone().negate());
      } else {
        rotationAxis.copy(ZeroVector);
        noRotationControl = true;
      }
      const newUpVector = upVector
        .clone()
        .applyAxisAngle(rotationAxis, rotationVelocity * delta);
      const newRightVector = rightVector
        .clone()
        .applyAxisAngle(rotationAxis, rotationVelocity * delta);
      const newForwardVector = forwardVector
        .clone()
        .applyAxisAngle(rotationAxis, rotationVelocity * delta);
      camera.rotation.copy(
        computeEulerFromForwardUpRightVectors(
          newForwardVector,
          newUpVector,
          newRightVector
        )
      );
      if (noTranslationControl && noRotationControl) {
        cameraManager.setIsUsingKeyboardControl(false);
      }
    });

    return null;
  }
);

function getTranslationVectorsForKeyboardControl(currentCamera: Camera) {
  const forwardVector = new Vector3(0, 0, -1).applyEuler(
    currentCamera.rotation
  );
  const upVector = new Vector3(0, 1, 0).applyEuler(currentCamera.rotation);
  const rightVector = new Vector3(1, 0, 0).applyEuler(currentCamera.rotation);
  return { forwardVector, upVector, rightVector };
}

function computeEulerFromForwardUpRightVectors(
  forward: Vector3,
  up: Vector3,
  right: Vector3
) {
  const euler = new Euler();
  euler.setFromRotationMatrix(
    new Matrix4().makeBasis(right, up, forward.clone().negate())
  );
  return euler;
}
