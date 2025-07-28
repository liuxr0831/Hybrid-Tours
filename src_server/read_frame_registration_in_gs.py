import json
import os
import numpy as np
from scipy.spatial.transform import Rotation
from argparse import ArgumentParser

# Parse command-line arguments
parser = ArgumentParser("Update to_be_concatenated_video_info.json with To-be-concatenated Frames Registration Result")
parser.add_argument("--project_path", "-s", required=True, type=str)
args = parser.parse_args()

# Format source path
source = args.project_path
source = source.replace("\\", "/")
if source[-1] != "/":
    source = source + "/"

# Read to_be_concatenated_video_info
to_be_concatenated_video_info_file_path = source + "to_be_concatenated/to_be_concatenated_video_info.json"
if os.path.exists(to_be_concatenated_video_info_file_path):
    with open(to_be_concatenated_video_info_file_path, "r") as file:
        to_be_concatenated_video_info = json.load(file)
else:
    raise ValueError("The given project path does not contain to_be_concatenated/to_be_concatenated_video_info.json")
to_be_concatenated_video_names = list(to_be_concatenated_video_info.keys())
if 'cam_intrinsic_params' in to_be_concatenated_video_names:
    to_be_concatenated_video_names.remove('cam_intrinsic_params')

# Read cameras.json
cameras_json_file_path = source + "gaussian_splatting_reconstruction/cameras.json"
if os.path.exists(cameras_json_file_path):
    with open(cameras_json_file_path, 'r') as file:
        gs_registered_frames = json.load(file)
else:
    raise ValueError("The given project path does not contain gaussian_splatting_reconstruction/cameras.json")

rotation_order = 'zxy'

# Read camera intrinsic parameters
sample_frame = gs_registered_frames[0]
to_be_concatenated_video_info['cam_intrinsic_params'] = (sample_frame['fx'], sample_frame['fy'], sample_frame['width'], sample_frame['height'])
print(to_be_concatenated_video_info['cam_intrinsic_params'])

# Format cameras.json into dict
frame_dict = {}
for frame in gs_registered_frames:
    frame_dict[frame['img_name']] = {"pos": frame['position'], \
                                     "rot": Rotation.from_matrix( np.array(frame['rotation']) ).as_euler(rotation_order).tolist()}

# Fill in to_be_concatenated_video_info
for video_info_dict_i in range(len(to_be_concatenated_video_names)):
    cur_video_name = to_be_concatenated_video_names[video_info_dict_i]
    num_frames = len(to_be_concatenated_video_info[cur_video_name]['frame_names'])
    frame_pos = np.zeros((num_frames, 3))
    frame_rot = np.zeros((num_frames, 3))
    for frame_i in range(num_frames):
        cur_frame_name_without_suffix = to_be_concatenated_video_info[cur_video_name]['frame_names'][frame_i].split('.')[0]
        if frame_dict.get(cur_frame_name_without_suffix) is None:
            frame_pos[frame_i, :] = [np.nan, np.nan, np.nan]
            frame_rot[frame_i, :] = [np.nan, np.nan, np.nan]
        else:
            frame_pos[frame_i, :] = frame_dict[cur_frame_name_without_suffix]['pos']
            frame_rot[frame_i, :] = frame_dict[cur_frame_name_without_suffix]['rot']
    to_be_concatenated_video_info[cur_video_name]['frame_pos'] = frame_pos.tolist()
    to_be_concatenated_video_info[cur_video_name]['frame_rot'] = frame_rot.tolist()


# Save to_be_concatenated_video_info and frame_dict
with open(source + 'to_be_concatenated/to_be_concatenated_video_info.json', 'w') as file:
    json.dump(to_be_concatenated_video_info, file)
with open(source + 'gaussian_splatting_reconstruction/frame_name_indexed_cameras.json', 'w') as file:
    json.dump(frame_dict, file)
