import { Matrix3, Matrix4 } from "three";
import { Object3D } from "three";

export function rotationMatrixToEuler(rotationMatrix) {
  const temObject = new Object3D();
  temObject.rotateX(Math.PI);
  const rotationMatrix4 = new Matrix4().setFromMatrix3(
    new Matrix3(
      rotationMatrix[0][0],
      rotationMatrix[0][1],
      rotationMatrix[0][2],
      rotationMatrix[1][0],
      rotationMatrix[1][1],
      rotationMatrix[1][2],
      rotationMatrix[2][0],
      rotationMatrix[2][1],
      rotationMatrix[2][2]
    )
  );
  temObject.applyMatrix4(rotationMatrix4);
  return temObject.rotation;
}
