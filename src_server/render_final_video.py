import os
import json
import cv2
import numpy as np
from argparse import ArgumentParser

def get_frame_name(prefix, video_name, frame_index, file_extension):
    if prefix is None or len(prefix)==0:
        return video_name[::-1].split('.', 1)[-1][::-1]+ '_' + f'{frame_index:08d}' + "." + file_extension
    else:
        return prefix + '_' + video_name[::-1].split('.', 1)[-1][::-1] + '_' + f'{frame_index:08d}' + "." + file_extension

parser = ArgumentParser("Hybrid Tours Render Final Video")
parser.add_argument("--project_path", "-s", required=True, type=str)
parser.add_argument("--final_video_name", "-f", required=True, type=str)
args = parser.parse_args()
project_path = args.project_path
final_video_name = args.final_video_name

final_video_folder = os.path.join(project_path, final_video_name)
rendered_frame_path = os.path.join(final_video_folder, 'concatenate_frames')
tbc_video_path = os.path.join(project_path, 'to_be_concatenated')
extract_config_path = os.path.join(project_path, 'to_be_concatenated/extract_config.json')
with open(extract_config_path, 'r') as file:
    extract_config = json.load(file)
final_video_fps = extract_config['final_video_fps']

with open(os.path.join(final_video_folder, 'final_video_config.json'), 'r') as file:
    final_video_config = json.load(file)

print('Rendering final video...')

# Create final_video writer
final_video_file_name = os.path.join(final_video_folder, final_video_name + '.mp4')
frame_size = final_video_config['frame_size']
video_writer = cv2.VideoWriter(final_video_file_name, cv2.VideoWriter_fourcc(*'mp4v'), final_video_fps, frame_size)

# Write video
cur_video_cap = None
cur_opened_video_name = None
for final_video_seg_i in range(len(final_video_config["final_video_config_list"])):
    final_video_seg = final_video_config["final_video_config_list"][final_video_seg_i]

    for frame_i in range(len(final_video_seg['frame_indexes'])):
        cur_frame_index = final_video_seg['frame_indexes'][frame_i]
        if final_video_seg['blend'][frame_i] == 0:
            frame_name = get_frame_name(None, final_video_seg['video_name'], cur_frame_index, 'png')
            rendered_frame = cv2.imread(os.path.join(rendered_frame_path, frame_name))
            video_writer.write(rendered_frame)
        else: 
            if cur_video_cap is None or cur_opened_video_name != final_video_seg['video_name']:
                if not cur_video_cap is None:
                    cur_video_cap.release()
                cur_video_cap = cv2.VideoCapture(os.path.join(tbc_video_path, final_video_seg['video_name']))
                cur_opened_video_name = final_video_seg['video_name']
            cur_video_cap.set(cv2.CAP_PROP_POS_FRAMES, cur_frame_index)
            ret, frame = cur_video_cap.read()
            if final_video_seg['blend'][frame_i] < 1:
                frame_name = get_frame_name('rendered', final_video_seg['video_name'], cur_frame_index, 'png')
                rendered_frame = cv2.imread(os.path.join(rendered_frame_path, frame_name))
                real_weight = final_video_seg['blend'][frame_i]
                rendered_weight = 1-real_weight
                frame = np.array(real_weight * frame + rendered_weight * rendered_frame, dtype=np.uint8)
            video_writer.write(frame)