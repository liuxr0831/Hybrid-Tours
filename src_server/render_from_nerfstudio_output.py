import os
import argparse
import json
import torch
import imageio
import numpy as np
from pathlib import Path

# Updated import for loading the pipeline
from nerfstudio.utils.eval_utils import eval_setup
from nerfstudio.cameras.cameras import Cameras, CameraType


def load_custom_camera_poses(json_path, transform_json):
    with open(json_path, "r") as f:
        pose_data = json.load(f)
    with open(transform_json, "r") as f:
        transform_data = json.load(f)

    transforms = []
    names = []
    sample_entry = pose_data[0]
    fx = sample_entry['fx']
    fy = sample_entry['fy']
    cx = sample_entry['width'] / 2
    cy = sample_entry['height'] / 2
    width = sample_entry['width']
    height = sample_entry['height']

    uniform_transform = np.eye(4)
    uniform_transform[:3, :] = transform_data['transform']

    for entry in pose_data:
        position = np.array(entry["position"])
        rotation = np.array(entry["rotation"])

        cam2world = np.eye(4)
        cam2world[:3, :3] = rotation
        cam2world[:3, 3] = position
        cam2world[:3, 1:3] *= -1
        cam2world = uniform_transform @ cam2world
        cam2world[:3, 3] *= transform_data['scale']
        transforms.append(cam2world)

        names.append(entry["name"])

    transforms = np.array(transforms)

    return {
        "names": names,
        "transforms": transforms,
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
        "width": width,
        "height": height
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Render custom camera poses using a trained Nerfstudio model.")
    parser.add_argument("--pose_file", type=str, required=True, help="Path to your custom camera pose JSON file")
    parser.add_argument("--config_file", type=str, required=True, help="Path to your config.yml file")
    parser.add_argument("--transform_file", type=str, required=True, help="Path to your dataparser_transforms.json file. Usually in the same directory as config.yml")
    parser.add_argument("--save_dir", type=str, required=True, help="Directory to save rendered images")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu", help="Device to use (cuda or cpu)")
    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    pose_file = args.pose_file
    device = args.device



    print("Loading custom camera poses...")
    cam_data = load_custom_camera_poses(pose_file, args.transform_file)


    save_dir.mkdir(parents=True, exist_ok=True)

    print("Loading pipeline...")
    setup = eval_setup(Path(args.config_file))
    print('finish setup')
    pipeline = setup[1]
    pipeline.to(device)

    print("Rendering images...")
    with torch.no_grad():
        for i in range(len(cam_data['names'])):
            camera = Cameras(
                camera_to_worlds=torch.tensor(cam_data["transforms"][i][:3,:], dtype=torch.float32).unsqueeze(0),
                fx=cam_data["fx"],
                fy=cam_data["fy"],
                cx=cam_data["cx"],
                cy=cam_data["cy"],
                width=cam_data["width"],
                height=cam_data["height"],
                camera_type=CameraType.PERSPECTIVE,
            ).to(device)
            outputs = pipeline.model.get_outputs_for_camera(camera)
            image = outputs["rgb"].cpu().numpy()
            image_path = save_dir / f"{cam_data['names'][i]}.png"
            imageio.imwrite(image_path, (image * 255).astype("uint8"))
