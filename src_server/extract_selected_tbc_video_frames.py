import cv2
import os
from argparse import ArgumentParser
import json
import numpy as np

video_file_suffix = ['mov', 'MOV', 'mp4']

parser = ArgumentParser("Extract Additional Frames in To-be-concatenated Videos")
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--video_paths", "-v", required=True, type=str)
parser.add_argument("--output_video_name", "-o", required=True, type=str)
parser.add_argument("--matching_range", "-mr", default=15, type=int)
args = parser.parse_args()

# Format source path
source = args.source_path
source = source.replace("\\", "/")

# Load extraction config
with open(os.path.join(source, 'to_be_concatenated/extract_config.json'), 'r') as file:
    extract_config = json.load(file)

# Load final video config and get list of final video segment names
output_video_name = args.output_video_name
with open(os.path.join(source, output_video_name, 'final_video_config.json')) as file:
    final_video_config = json.load(file)
stabilized_seg_names = list(final_video_config['stabilized_video_selected_range'].keys())

# Prepare irrelevant frame list
temp_irrelevant_frame_set = set(os.listdir(os.path.join(source, output_video_name, 'registration_with_extra_frames', 'images')))

# Get path to all videos, extract frames, and write matching list
to_be_concatenated_file_names = args.video_paths.split(",")
matching_list_file = open(os.path.join(source, output_video_name, 'registration_with_extra_frames', 'extracted_frames_match_list.txt'), 'w')
for to_be_concatenated_file_name in to_be_concatenated_file_names:
    # skip videos that are not stabilized (if not stabilized, then high-quality 2D frames are used, so no need to extract extra frames)
    if not to_be_concatenated_file_name in stabilized_seg_names:
        continue

    # Open video and prepare necessary variables
    video_capture = cv2.VideoCapture(os.path.join(source, 'to_be_concatenated', to_be_concatenated_file_name))
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    extracted_frames = []
    image_folder_path_str = os.path.join(source, output_video_name, 'registration_with_extra_frames', 'images')
    selected_range = final_video_config['stabilized_video_selected_range'][to_be_concatenated_file_name]
    start_frame_i = max(0, int(np.floor(selected_range[0] * total_frames)))
    end_frame_i = min(total_frames, int(np.ceil(selected_range[1] * total_frames)))

    # Extract frames
    for frame_i in range(start_frame_i, end_frame_i):
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_i)
        ret, frame = video_capture.read()
        if ret:
            frame_file_name = 'to_be_concatenated_' + to_be_concatenated_file_name[::-1].split('.', 1)[-1][::-1] +  "_{:08d}".format(frame_i) + '.jpg'
            cv2.imwrite(os.path.join(image_folder_path_str, frame_file_name), frame)
            colmap_frame_file_name = frame_file_name
            extracted_frames.append(frame_file_name)
        else:
            print(f"Frame {frame_i} of {to_be_concatenated_file_name} cannot be extracted.")
    video_capture.release()

    temp_irrelevant_frame_set = temp_irrelevant_frame_set - set(extracted_frames)

    # Write matching list
    for frame_i in range(len(extracted_frames)):
        for frame_j in range(frame_i+1, min(frame_i+1+args.matching_range, len(extracted_frames))):
            matching_list_file.write(extracted_frames[frame_i] + " " + extracted_frames[frame_j] + '\n')

matching_list_file.close()

irrelevant_frame_file = open(os.path.join(source, output_video_name, 'registration_with_extra_frames', 'irrelevant_frames.txt'), 'w')
for frame in temp_irrelevant_frame_set:
    irrelevant_frame_file.write(frame+'\n')
irrelevant_frame_file.close()