import cv2
import os
from argparse import ArgumentParser
import json
from copy import deepcopy

video_file_suffix = ['mov', 'MOV', 'mp4']
image_file_suffix = ['jpeg', 'png', 'jpg']

parser = ArgumentParser("Extract Environment Scan and To-be-concatenated Video Frames")
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--num_extracted_frame_per_sec_for_tbc_videos", "-tbcfps", default="10", type=str)
parser.add_argument("--num_extracted_frame_for_tbc_videos_at_two_ends", "-tbctef", default="-1", type=str)
parser.add_argument("--num_extracted_frame_per_sec_for_env_scan_videos", "-esfps", default="2", type=str)
args = parser.parse_args()

# Format source path
source = args.source_path
source = source.replace("\\", "/")

# Read extraction fps
tbc_extraction_fps = float(args.num_extracted_frame_per_sec_for_tbc_videos)
env_scan_extraction_fps = float(args.num_extracted_frame_per_sec_for_env_scan_videos)

# Scan to-be-concatenated videos and prepare dir for frames
with open(os.path.join(source, 'to_be_concatenated/extract_config.json'), 'r') as file:
    extract_config = json.load(file)
extract_config['original_sampling_interval_sec'] = 1/tbc_extraction_fps
with open(os.path.join(source, 'to_be_concatenated/extract_config.json'), 'w') as file:
    json.dump(extract_config, file)
to_be_concatenated_file_names = sorted(list(extract_config['tbc_file_extracted_frames'].keys()))
all_files_in_env_scan = sorted(os.listdir(os.path.join(source, 'environment_scan')))
environment_scan_file_names = []
for file in all_files_in_env_scan:
    if file[0] != '.' and (file.split('.')[-1] in video_file_suffix or file.split('.')[-1] in image_file_suffix) and os.path.isfile(os.path.join(source, 'environment_scan', file)):
        environment_scan_file_names.append(file)
video_frame_extraction_dir = os.path.join(source, 'environment_scan', 'images')
os.makedirs(video_frame_extraction_dir, exist_ok=True)

# Create to_be_concatenated_video_info.json
to_be_concatenated_video_info_dict_template = {'frame_names':[], 'frame_ts':[]}
to_be_concatenated_video_info = {}
for to_be_concatenated_video_i in range(len(to_be_concatenated_file_names)):
    to_be_concatenated_video_info[to_be_concatenated_file_names[to_be_concatenated_video_i]] = deepcopy(to_be_concatenated_video_info_dict_template)

# Helper function to make custom matching perform exhaustive matching between extracted frames and all other frames
def write_match_list_for_file(img_list_file, extracted_frame_lists, match_range=5):
    for video_i in range(len(extracted_frame_lists)):
        cur_video_extracted_frames = extracted_frame_lists[video_i]
        for extracted_frame_name_i in range(len(cur_video_extracted_frames)):
            cur_extracted_frame_name = cur_video_extracted_frames[extracted_frame_name_i]
            # Within the same video, match with match_range previous frames and match_range following frames
            for extracted_frame_name_j in range(extracted_frame_name_i+1, min(extracted_frame_name_i+1+match_range, len(cur_video_extracted_frames))):
                img_list_file.write(cur_extracted_frame_name + " " + cur_video_extracted_frames[extracted_frame_name_j] + '\n')
            # Exhaustive matching with frames in other videos
            other_video_frames = []
            for video_ii in range(video_i+1, len(extracted_frame_lists)):
                if video_ii == video_i:
                    continue
                other_video_frames += extracted_frame_lists[video_ii]
            for img_file in other_video_frames:
                img_list_file.write(cur_extracted_frame_name + " " + img_file + "\n")

# Prepare fields and files
img_list_file_path_str = os.path.join(source, 'environment_scan', 'extracted_frames_match_list.txt')
img_list_file = open(img_list_file_path_str, 'w')
extracted_frame_names_lists = []

# Extract frames from to-be-concatenated videos
for to_be_concatenated_file_i in range(len(to_be_concatenated_file_names)):
    # Read info
    to_be_concatenated_file_name = to_be_concatenated_file_names[to_be_concatenated_file_i]
    to_be_concatenated_full_file_name = os.path.join(source, 'to_be_concatenated', to_be_concatenated_file_name)
    print(to_be_concatenated_full_file_name)
    cur_file_extract_config = extract_config['tbc_file_extracted_frames'][to_be_concatenated_file_name]

    # Calculate needed constants
    video_capture = cv2.VideoCapture(to_be_concatenated_full_file_name)
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    extract_every_x_frame = fps/tbc_extraction_fps

    # Find to-be-extracted frames based on config
    to_be_extracted_frame_is = []
    num_frames_to_extract_at_start_and_end = int(args.num_extracted_frame_for_tbc_videos_at_two_ends)
    if num_frames_to_extract_at_start_and_end == -1:
        num_frames_to_extract_at_start_and_end = int(extract_config['final_video_fps'])
    if 'all' in cur_file_extract_config:
        to_be_extracted_frame_is += [i for i in range(min(total_frames, num_frames_to_extract_at_start_and_end))]
        next_to_be_extracted_frame_i = to_be_extracted_frame_is[-1]
        while total_frames - to_be_extracted_frame_is[-1] > num_frames_to_extract_at_start_and_end+extract_every_x_frame:
            next_to_be_extracted_frame_i += extract_every_x_frame
            to_be_extracted_frame_is.append(int(next_to_be_extracted_frame_i))
        last_extracted_frame_i = to_be_extracted_frame_is[-1]
        to_be_extracted_frame_is += [i for i in range(max(last_extracted_frame_i+1, total_frames-num_frames_to_extract_at_start_and_end), total_frames)]
    else:
        if 'start' in cur_file_extract_config:
            to_be_extracted_frame_is += [i for i in range(min(total_frames, num_frames_to_extract_at_start_and_end))]
        if 'end' in cur_file_extract_config:
            if len(to_be_extracted_frame_is) != 0:
                next_frame_of_last_extracted_frame = min(to_be_extracted_frame_is[-1] + 1, total_frames)
            else:
                next_frame_of_last_extracted_frame = 0
            last_extracted_frame_i = max(0, next_frame_of_last_extracted_frame, total_frames-num_frames_to_extract_at_start_and_end)
            to_be_extracted_frame_is += [i for i in range(last_extracted_frame_i, total_frames)]
    
    # Actually extract frames
    cur_video_extracted_frames = []
    for frame_i in to_be_extracted_frame_is:
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_i)
        ret, frame = video_capture.read()
        if ret:
            frame_file_name = 'to_be_concatenated_' + to_be_concatenated_file_name[::-1].split('.', 1)[-1][::-1] +  "_{:08d}".format(frame_i) + '.jpg'
            cv2.imwrite(os.path.join(video_frame_extraction_dir, frame_file_name), frame)
            to_be_concatenated_video_info[to_be_concatenated_file_name]['frame_names'].append(frame_file_name)
            to_be_concatenated_video_info[to_be_concatenated_file_name]['frame_ts'].append((frame_i) / fps)
            cur_video_extracted_frames.append(frame_file_name)
        else:
            print(f"Frame {frame_i} of {to_be_concatenated_file_name} cannot be extracted.")
    extracted_frame_names_lists.append(cur_video_extracted_frames)

    video_capture.release()


# Extract frames from environment scan videos
for environment_scan_file_i in range(len(environment_scan_file_names)):
    # Read info
    environment_scan_file_name = environment_scan_file_names[environment_scan_file_i]
    environment_scan_full_file_name = os.path.join(source, 'environment_scan', environment_scan_file_name)
    print(environment_scan_full_file_name)

    if environment_scan_file_name.split('.')[-1] in image_file_suffix:
        frame = cv2.imread(environment_scan_full_file_name)
        frame_file_name = 'environment_scan_' + environment_scan_file_name[::-1].split('.', 1)[-1][::-1] + '.jpg'
        cv2.imwrite(os.path.join(video_frame_extraction_dir, frame_file_name), frame)
        extracted_frame_names_lists.append([frame_file_name])
        continue

    # Calculate needed constants
    video_capture = cv2.VideoCapture(environment_scan_full_file_name)
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    extract_every_x_frame = fps/env_scan_extraction_fps

    # Find to-be-extracted frames based on config
    to_be_extracted_frame_is = [0]
    next_to_be_extracted_frame_i = extract_every_x_frame
    while total_frames - next_to_be_extracted_frame_i > 0:
        to_be_extracted_frame_is.append(int(next_to_be_extracted_frame_i))
        next_to_be_extracted_frame_i += extract_every_x_frame

    
    # Actually extract frames
    cur_video_extracted_frames = []
    for frame_i in to_be_extracted_frame_is:
        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_i)
        ret, frame = video_capture.read()
        if ret:
            frame_file_name = 'environment_scan_' + environment_scan_file_name[::-1].split('.', 1)[-1][::-1] +  "_{:08d}".format(frame_i) + '.jpg'
            cv2.imwrite(os.path.join(video_frame_extraction_dir, frame_file_name), frame)
            cur_video_extracted_frames.append(frame_file_name)
        else:
            print(f"Frame {frame_i} of {environment_scan_file_name} cannot be extracted.")
    extracted_frame_names_lists.append(cur_video_extracted_frames)

    video_capture.release()


write_match_list_for_file(img_list_file, extracted_frame_names_lists)
img_list_file.close()

with open(os.path.join(source, "to_be_concatenated", "to_be_concatenated_video_info.json"), "w+") as file:
    json.dump(to_be_concatenated_video_info, file)

