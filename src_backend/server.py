from flask import Flask, request, jsonify
from flask_cors import CORS

import os
import shutil
import json
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
import traceback
import base64
import pickle
from copy import deepcopy
import networkx as nx

from stabilizer import Stabilizer
from stabilize_helper import Stabilize_Helper
from concatenate_utils import get_relevant_range, generate_initial_concatenate_config_by_order, get_continuously_extracted_frames, get_non_nan_chunk_from_list, get_cur_frame_dict, get_frame_name, generate_register_and_reconstruct_shell_script, generate_render_shell_script, sample_points, generate_render_with_extra_frames_shell_script, frame_index_of
from fit_path_and_velocity import calc_default_path_and_velocity, get_distance, get_path_control_points_and_t
from orientation_quaternion import calc_default_orientation_change, rotation_order, get_orientation_control_points_and_t, get_orientation_mat_along_rotation_path, get_path_coord_zero_orientation_mat
from bezier_curve import bezier, d_bezier


app = Flask(__name__)
CORS(app)
up_vec = None
tbc_video_info = None
tbc_stabilizers = {}
tbc_stabilizers_full_range = {}
final_video_fps = -1
project_name = None
project_path = None
repo_path = None
shell_project_path = None
mega_video_name = '.temp_final_video'
original_sampling_interval_sec = -1
median_cam_velocity = 0
video_graph = nx.DiGraph()

# These variables can be manually set by the frontend
shell_repo_path = None
colmap_bin_path = 'colmap'
data_device = 'cuda'


# Helper function to clear the exisitng infos
def clear():
    global up_vec, tbc_stabilizers, final_video_fps, tbc_video_info, project_path, tbc_stabilizers_full_range, project_name, median_cam_velocity, video_graph
    up_vec = None
    tbc_video_info = None
    tbc_stabilizers = {}
    tbc_stabilizers_full_range = {}
    final_video_fps = -1
    project_path = None
    project_name = None
    median_cam_velocity = 0
    video_graph = nx.DiGraph()



@app.route('/suggest_clips', methods=['POST'])
def suggest_clips():
    try:
        global video_graph, tbc_video_info
        js = request.get_json()
        picked_video_list = js['picked_videos']

        all_possible_paths = []
        start_video_trimmed_place = []

        for video_i in range(len(picked_video_list)-1):
            video_i = -video_i-1
            cur_next_video = picked_video_list[video_i]
            cur_last_video = picked_video_list[video_i-1]
            try:
                cur_transition_all_paths = list(nx.all_simple_paths(video_graph,cur_last_video,cur_next_video))
            except Exception as e:
                cur_transition_all_paths = []
            if len(all_possible_paths)==0:
                if len(cur_transition_all_paths)==0:
                    all_possible_paths.append([cur_last_video,cur_next_video])
                    if not tbc_video_info[cur_last_video]['is_stabilizable']:
                        start_video_trimmed_place.append(-1)
                    else:
                        start_video_trimmed_place.append(len(tbc_video_info[cur_last_video]['sampled_percents'])-1)
                else:
                    for path in cur_transition_all_paths:
                        is_path_ok = True
                        for video_vertex_i in range(1, len(path)-1):
                            if path[video_vertex_i] in picked_video_list:
                                is_path_ok = False
                        if is_path_ok:
                            all_possible_paths.append(path)
                            start_video_trimmed_place.append(video_graph[path[0]][path[1]]["trim_location"][0])
                continue
            
            still_possible_paths = []
            new_video_trimmed_place = []
            for possible_path_i in range(len(all_possible_paths)):
                possible_path = all_possible_paths[possible_path_i]
                cur_next_video_trim_end = start_video_trimmed_place[possible_path_i]
                if len(cur_transition_all_paths)==0:
                    still_possible_paths.append([cur_last_video, *possible_path])
                    new_video_trimmed_place.append(len(tbc_video_info[cur_last_video]['sampled_percents'])-1)
                else:
                    for cur_transition_path in cur_transition_all_paths:
                        is_path_ok = True
                        for video_vertex_i in range(1, len(cur_transition_path)-1):
                            if cur_transition_path[video_vertex_i] in picked_video_list or cur_transition_path[video_vertex_i] in possible_path:
                                is_path_ok = False 
                        if is_path_ok and (video_graph[cur_transition_path[-2]][cur_transition_path[-1]]['trim_location'][1] < cur_next_video_trim_end-5 or (video_graph[cur_transition_path[-2]][cur_transition_path[-1]]['trim_location'][1]==0 and cur_next_video_trim_end==-1)):
                            still_possible_paths.append([*(cur_transition_path[0:-1]), *possible_path])
                            new_video_trimmed_place.append(video_graph[cur_transition_path[0]][cur_transition_path[1]]['trim_location'][0])
            
            all_possible_paths = still_possible_paths
            start_video_trimmed_place = new_video_trimmed_place

        cur_lowest_cost = np.inf
        cur_lowest_cost_path = None
        for possible_path in all_possible_paths:
            cur_cost = 0
            for vertex_i in range(len(possible_path)-1):
                try:
                    cur_edge_cost = video_graph[possible_path[vertex_i]][possible_path[vertex_i+1]]['weight']
                except Exception as e:
                    cur_edge_cost = 0
                cur_cost += cur_edge_cost
            if cur_lowest_cost > cur_cost:
                cur_lowest_cost = cur_cost
                cur_lowest_cost_path = possible_path

        if cur_lowest_cost_path is None:
            cur_lowest_cost_path = picked_video_list

        return jsonify({'picked_videos': cur_lowest_cost_path}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Receive: {'file': (file; the file to be uploaded)}
# Return: {'msg': 'File uploaded successfully.'}
@app.route('/upload_file', methods=['POST'])
def upload_file():
    try:
        # Check if the request contains a file
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400
        
        file = request.files['file']

        # Check if the file has a name
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Save the file to the specified destination
        global repo_path
        file.save(os.path.join(repo_path, '.temp_project', file.filename))

        return jsonify({'msg': 'File uploaded successfully.'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Remove a file
# Receive: {'file_name': (string; name of the file to be removed)}
# Return: {'msg': 'File removed successfully.'}
@app.route('/remove_file', methods=['POST'])
def remove_file():
    try:
        # Read request
        js = request.get_json()
        file_name = js['file_name']

        # Check if the file exists
        global repo_path
        file_path = os.path.join(repo_path, '.temp_project', file_name)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Remove the file
        os.remove(file_path)

        return jsonify({'msg': 'File removed successfully.'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Create a project with given env_scan and tbc files
# Receive: {
# 'project_name': (string; name of the project), 
# 'env_scan_fps' (optional): (float; extraction fps for environemnt scan videos, default 2),
# 'tbc_fps' (optional): (float; extraction fps for to-be-concatenated videos, default is 10),
# 'env_scan_files': [ (string; path to first env_scan video), (string;
# path to second env_scan video), ... ],
# 'tbc_file_config': [{ (string; path to first tbc video): (list, can be one
# of the following: ['all'], ['start'], ['end'], ['start', 'end'])}, ... ],
# 'tbc_two_ends_num_frame': (int; number of frames to extract at the start and end of candidate
# clips))
# }
# Return: {'msg': 'create project succeed.'}
@app.route('/create_project', methods=['POST'])
def create_project():
    try:
        global repo_path, shell_repo_path, colmap_bin_path

        # read request
        js = request.get_json()
        project_name = js['project_name']
        project_path = os.path.join(repo_path, 'data', project_name)
        if js.get('env_scan_fps') is None:
            env_scan_extract_fps = 2
        else:
            env_scan_extract_fps = js.get('env_scan_fps')
        if js.get('tbc_fps') is None:
            tbc_extract_fps = 10
        else:
            tbc_extract_fps = js.get('tbc_fps')
        if js.get('tbc_two_ends_num_frame') is None:
            tbc_two_ends_num_frame = -1
        else:
            tbc_two_ends_num_frame = js.get('tbc_two_ends_num_frame')

        # create directories 
        os.makedirs(project_path, exist_ok=True)
        env_scan_path = os.path.join(project_path, 'environment_scan')
        tbc_path = os.path.join(project_path, 'to_be_concatenated')
        os.makedirs(env_scan_path, exist_ok=True)
        os.makedirs(tbc_path, exist_ok=True)
        
        
        # set up project folder
        # copy environment scan files
        for env_scan_file in js['env_scan_files']:
            shutil.copy2(os.path.join(repo_path, '.temp_project', env_scan_file), env_scan_path)

        # set up to-be-concatenated files
        tbc_file_extracted_frames = js['tbc_file_config']
        lowest_tbc_fps = np.inf
        tbc_file_extracted_frames_basename_key = {}
        for tbc_file_dict in tbc_file_extracted_frames:
            tbc_file = list(tbc_file_dict.keys())[0]
            shutil.copy2(os.path.join(repo_path, '.temp_project', tbc_file), tbc_path)
            cap = cv2.VideoCapture(os.path.join(tbc_path, tbc_file))
            lowest_tbc_fps = np.min([lowest_tbc_fps, cap.get(cv2.CAP_PROP_FPS)])
            cap.release()
            tbc_file_extracted_frames_basename_key[os.path.basename(tbc_file)] = tbc_file_dict[tbc_file]
        extract_config = {'tbc_file_extracted_frames': tbc_file_extracted_frames_basename_key}
        extract_config['final_video_fps'] = lowest_tbc_fps
        with open(os.path.join(tbc_path, 'extract_config.json'), 'w') as file:
            json.dump(extract_config, file)

        # generate the shell scripts for this project
        shell_script_dir = env_scan_path
        shell_project_path = os.path.join(shell_repo_path, 'data', project_name)
        shell_project_path = shell_project_path.replace('\\', '/')
        generate_register_and_reconstruct_shell_script(shell_project_path, shell_repo_path, colmap_bin_path, env_scan_extract_fps, tbc_extract_fps, shell_script_dir, data_device, tbc_two_ends_num_frame)

        return jsonify({'msg': 'create project succeed.'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Receive: {'video_name': (string; name of the video); 'start_percent': (double;
# the start of current selected range); 'end_percent': (double; the end of the
# current selected range)}
# Return: {'maximum_stabilization_strength': (int; the maximum stabilization
# coefficient)}
@app.route('/get_maximum_stabilization_strength', methods=['POST'])
def get_maximum_stabilization_strength():
    try:
        global tbc_video_info

        # read request
        js = request.get_json()
        video_name = js['video_name']
        start_percent = js['start_percent']
        end_percent = js['end_percent']

        # calculate maximum stabilization strength
        cur_video_info = tbc_video_info[video_name]
        original_sampling_interval = cur_video_info['original_sampling_interval']
        cur_stabilization_strength = min(10, int((end_percent - start_percent)/original_sampling_interval/2))
        _, _, sampled_ts = sample_points(cur_video_info['frame_pos'], cur_video_info['frame_rot'], cur_video_info['frame_ts'], start_percent, end_percent, cur_stabilization_strength*original_sampling_interval)
        while len(sampled_ts) < 4:
            cur_stabilization_strength -= 1
            _, _, sampled_ts = sample_points(cur_video_info['frame_pos'], cur_video_info['frame_rot'], cur_video_info['frame_ts'], start_percent, end_percent, cur_stabilization_strength*original_sampling_interval)

        return jsonify({'maximum_stabilization_strength': cur_stabilization_strength}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Open a project
# Receive:
# {project_name: "(name of opened project)"}
# Return: 
# {(string; to-be-concatenated video name): 
# {'is_stabilizable': (True or False), 
#  'is_before_other_video_ok': (True or False; If video is not stabilized, use this 
#  variable. If video is stabilized, it can be placed before or after other videos, 
#  so ignore this variable.), 
#  'is_after_other_video_ok': (True or False; same as 'is_before_other_video_ok‘), 
#  'sampled_percents': (list of doubles or None; if the video is stabilizable, this 
#  list shows the percents (start=0.0, end=1.0) in terms of video length where a 
#  frame is extracted and properly registered. When the user trims the video, the 
#  start and end of the trimming point must be the sampled_percents. Also, we need 
#  at least 4 sampled points to perform stabilization, so user's trimming range 
#  decides the maximum sampling interval.), 
#  'frames': (list of jpeg image bytes),
#  'pos': (list of list representing camera positions, contain None for not 
#  registered frames),
#  'rot': (same as above but as rotation matrices)
#  'ts': (list of double)
#  'suggestion_for_next_clip': (list of strings; names of videos that are suggested)
#  'trim_for_suggested_clips' = (dict; keys are suggested video names, values are trim index within sampled_percents)
# } 
#  (string; another to-be-conatenated video name): {another dict}, ...}
# Here's the way we sample frames for stabilization, which allows for calculation
# of max_sampling_interval (the maximum stabilization strength):
# We sample the start of the trimming
# For each frame after that, we include it if it meets one of the two following
# conditions:
# 1. the time difference between this frame and last sampled stabilization frame is 
# the same as the desired sampling interval (use isclose to decide that, not ==).
# 2. the time difference between this frame and last sampled stabilization frame is
# smaller than the desired sampling interval, but not including the current frame 
# and including the next frame will cause the time difference between two sampled 
# stabilization frame exceed 1.2 times the desired sampling interval.
# At the end, we always sample the end of the trimming range.
# Examples for how stabilization works:
# sampled_percents: [0, 0.1, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
# original_sampling_interval: 0.1
# sampling_interval: 0.2
# sampled_percents: [0, 0.2, 0.4, 0.6, 0.8, 1.0]
# sampling_interval: 0.3
# sampled_percents: [0, 0.2, 0.5, 0.8, 1.0]
# Mayebe just start from 1 sample every second, if satisfy then set 
# max_sampling_interval as 10, if not enough sample then gradually try smaller?
@app.route('/open_project', methods=['POST'])
def open_project():
    try:
        clear()
        global tbc_stabilizers, final_video_fps, tbc_video_info, project_path, project_name, shell_repo_path, shell_project_path, original_sampling_interval_sec

        # read request
        js = request.get_json()
        project_name = js['project_name']
        project_path = os.path.join(repo_path, 'data', project_name)
        shell_project_path = os.path.join(shell_repo_path, 'data', project_name)
        shell_project_path = shell_project_path.replace('\\', '/')

        # load extract_config and to_be_concatenated_video_info
        extract_config_path = os.path.join(project_path, 'to_be_concatenated/extract_config.json')
        with open(extract_config_path, 'r') as file:
            extract_config = json.load(file)
        tbc_video_info_path = os.path.join(project_path, 'to_be_concatenated/to_be_concatenated_video_info.json')
        with open(tbc_video_info_path, 'r') as file:
            tbc_video_info = json.load(file)
        final_video_fps = extract_config['final_video_fps']
        original_sampling_interval_sec = extract_config['original_sampling_interval_sec']

        # For graph-based clip suggestion
        camera_velocities = []
        all_videos_sampled_pos = {}
        all_videos_sampled_rot = {}
        
        # Construct return json
        tbc_meta_info = {}
        tbc_file_extracted_frames = extract_config['tbc_file_extracted_frames']
        for tbc_video_name in tbc_file_extracted_frames.keys():
            # Initialize things
            cur_video_dict = {}
            cur_video_info = tbc_video_info[tbc_video_name]
            tbc_stabilizers[tbc_video_name] = None

            # Figure out if the video be stabilized and where can it be placed
            is_all_frame_extracted = 'all' in tbc_file_extracted_frames[tbc_video_name] and cur_video_info['frame_ts'][-1] > 5*extract_config['original_sampling_interval_sec']
            cur_video_dict['is_stabilizable'] = is_all_frame_extracted
            cur_video_info['is_stabilizable'] = is_all_frame_extracted
            cur_video_dict['is_before_other_video_ok'] = False
            cur_video_dict['is_after_other_video_ok'] = False
            frame_names = cur_video_info['frame_names']
            num_frame_to_check = min(len(frame_names), final_video_fps)
            if 'start' in tbc_file_extracted_frames[tbc_video_name] or 'all' in tbc_file_extracted_frames[tbc_video_name]:
                start_i, end_i = get_continuously_extracted_frames(frame_names, 'start', num_frame_to_check)
                start_frame_names = frame_names[start_i:end_i]
                start_pos = np.array(cur_video_info['frame_pos'])[start_i:end_i,0]
                non_nan_start_i, non_nan_end_i = get_non_nan_chunk_from_list(start_pos, 3, 'start')
                if not np.isnan(non_nan_start_i):
                    cur_video_dict['is_after_other_video_ok'] = True
                    considered_i_start = frame_names.index(start_frame_names[non_nan_start_i])
                    considered_i_end = frame_names.index(start_frame_names[non_nan_end_i-1]) + 1
                    tbc_video_info[tbc_video_name]['start_considered_range'] = (considered_i_start, considered_i_end)
                else:
                    tbc_video_info[tbc_video_name]['start_considered_range'] = (np.nan, np.nan)
            else:
                tbc_video_info[tbc_video_name]['start_considered_range'] = (np.nan, np.nan)
            if 'end' in tbc_file_extracted_frames[tbc_video_name] or 'all' in tbc_file_extracted_frames[tbc_video_name]:
                start_i, end_i = get_continuously_extracted_frames(frame_names, 'end', num_frame_to_check)
                end_frame_names = frame_names[start_i:end_i]
                end_pos = np.array(cur_video_info['frame_pos'])[start_i:end_i,0]
                non_nan_start_i, non_nan_end_i = get_non_nan_chunk_from_list(end_pos, 3, 'end')
                if not np.isnan(non_nan_start_i):
                    cur_video_dict['is_before_other_video_ok'] = True
                    considered_i_start = frame_names.index(end_frame_names[non_nan_start_i])
                    considered_i_end = frame_names.index(end_frame_names[non_nan_end_i-1]) + 1
                    tbc_video_info[tbc_video_name]['end_considered_range'] = (considered_i_start, considered_i_end)
                else:
                    tbc_video_info[tbc_video_name]['end_considered_range'] = (np.nan, np.nan)
            else:
                tbc_video_info[tbc_video_name]['end_considered_range'] = (np.nan, np.nan)

            # Calculate sampled_percents
            cur_video_dict['sampled_percents'] = None
            tbc_video_info[tbc_video_name]['original_sampling_interval'] = np.nan
            cur_video_sampled_pos = []
            cur_video_sampled_rot = []
            if is_all_frame_extracted:
                frame_ts = np.array(cur_video_info['frame_ts'])
                sample_pos = np.array(cur_video_info['frame_pos'])[:,0]
                frame_is_registered = ~np.isnan(sample_pos)
                sampling_interval = extract_config['original_sampling_interval_sec']
                video_total_time = frame_ts[-1]
                frame_ts = frame_ts[frame_is_registered] # Only consider registered frames
                sampled_ts = []
                last_pos = None
                for sampled_frame_i in range(len(frame_ts)-1):
                    cur_ts = frame_ts[sampled_frame_i]
                    next_ts = frame_ts[sampled_frame_i+1]

                    # Fill the first one
                    if len(sampled_ts)==0:
                        sampled_ts.append(cur_ts)
                        last_pos = np.array(cur_video_info['frame_pos'][cur_video_info['frame_ts'].index(cur_ts)])
                        cur_video_sampled_pos.append(last_pos)
                        cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][cur_video_info['frame_ts'].index(cur_ts)]))
                        continue

                    # Reach next sample or skipping this make interval too large
                    if np.isclose(cur_ts-sampled_ts[-1], sampling_interval) or (next_ts-sampled_ts[-1] > sampling_interval*1.2):
                        cur_pos = np.array(cur_video_info['frame_pos'][cur_video_info['frame_ts'].index(cur_ts)])
                        cur_video_sampled_pos.append(cur_pos)
                        cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][cur_video_info['frame_ts'].index(cur_ts)]))
                        camera_velocity = np.linalg.norm(cur_pos-last_pos) / (cur_ts - sampled_ts[-1])
                        last_pos = cur_pos
                        camera_velocities.append(camera_velocity)
                        sampled_ts.append(cur_ts)
                
                if not np.isnan(cur_video_info['frame_pos'][-1][0]):
                    cur_pos = np.array(cur_video_info['frame_pos'][-1])
                    cur_video_sampled_pos.append(cur_pos)
                    cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][-1]))
                    camera_velocity = np.linalg.norm(cur_pos-last_pos) / (frame_ts[-1] - sampled_ts[-1])
                    sampled_ts.append(frame_ts[-1])
                    sampled_ts = np.array(sampled_ts) 
                cur_video_dict['sampled_percents'] = (sampled_ts / video_total_time).tolist()
                cur_video_info['sampled_percents'] = cur_video_dict['sampled_percents']

                tbc_video_info[tbc_video_name]['original_sampling_interval'] = extract_config['original_sampling_interval_sec'] / video_total_time
            else:
                cur_video_sampled_pos.append(np.array(cur_video_info['frame_pos'][0]))
                cur_video_sampled_pos.append(np.array(cur_video_info['frame_pos'][1]))
                cur_video_sampled_pos.append(np.array(cur_video_info['frame_pos'][-2]))
                cur_video_sampled_pos.append(np.array(cur_video_info['frame_pos'][-1]))
                cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][0]))
                cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][1]))
                cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][-2]))
                cur_video_sampled_rot.append(np.array(cur_video_info['frame_rot'][-1]))

            all_videos_sampled_pos[tbc_video_name] = cur_video_sampled_pos
            all_videos_sampled_rot[tbc_video_name] = cur_video_sampled_rot

            # read the frames
            # Initialize fields
            video_capture = cv2.VideoCapture(os.path.join(project_path, 'to_be_concatenated', tbc_video_name))
            video_fps = video_capture.get(cv2.CAP_PROP_FPS)
            frames = []
            frame_pos = []
            frame_rot = []
            frame_ts = []
            # Get the relevant range
            if (np.isnan(tbc_video_info[tbc_video_name]['end_considered_range'][1])):
                end_frame_i = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            else:
                end_frame_i = frame_index_of(frame_names[tbc_video_info[tbc_video_name]['end_considered_range'][1]-1])
            if (np.isnan(tbc_video_info[tbc_video_name]['start_considered_range'][0])):
                start_frame_i = 0
            else:
                start_frame_i = frame_index_of(frame_names[tbc_video_info[tbc_video_name]['start_considered_range'][0]])
            # Actually read frames
            # Check if frames are already extracted
            frame_file_path = os.path.join(project_path, 'to_be_concatenated/for_frontend', tbc_video_name+".pickle")
            if os.path.exists(frame_file_path):
                is_frame_loaded = True
                with open(frame_file_path, 'rb') as file:
                    frames = pickle.load(file)
                frames = frames[start_frame_i:end_frame_i+1]
            else:
                is_frame_loaded = False
            last_frame_i = -1
            for frame_name_i in range(len(frame_names)):
                # Get current frame name and index
                cur_frame_name = frame_names[frame_name_i]
                cur_frame_i = frame_index_of(cur_frame_name)

                # Skip the irrelevant part
                if cur_frame_i < start_frame_i:
                    continue
                if cur_frame_i > end_frame_i:
                    break

                # read intermediate frame
                for frame_i in range(last_frame_i+1, cur_frame_i):
                    if not is_frame_loaded:
                        video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_i)
                        ret, frame = video_capture.read()
                        ret, buffer = cv2.imencode('.jpg', frame)
                        frames.append(base64.b64encode(buffer.tobytes()).decode('utf-8'))
                    frame_pos.append(None)
                    frame_rot.append(None)
                    frame_ts.append(frame_i/video_fps)
                
                # read current frame
                if not is_frame_loaded:
                    video_capture.set(cv2.CAP_PROP_POS_FRAMES, cur_frame_i)
                    ret, frame = video_capture.read()
                    ret, buffer = cv2.imencode('.jpg', frame)
                    frames.append(base64.b64encode(buffer.tobytes()).decode('utf-8'))
                if np.isnan(cur_video_info['frame_pos'][frame_name_i][0]):
                    frame_pos.append(None)
                    frame_rot.append(None)
                else:
                    frame_pos.append(cur_video_info['frame_pos'][frame_name_i])
                    frame_rot.append(Rotation.from_euler(rotation_order, cur_video_info['frame_rot'][frame_name_i]).as_matrix().tolist())
                frame_ts.append(cur_frame_i/video_fps)

                last_frame_i = cur_frame_i

                if frame_name_i == len(frame_names)-1 and last_frame_i<end_frame_i-1:
                    for frame_i in range(last_frame_i+1, end_frame_i):
                        frame_pos.append(None)
                        frame_rot.append(None)
                        frame_ts.append(frame_i/video_fps)

            video_capture.release()

            

            # Store the frames and non-stabilized camera trajectory
            cur_video_dict['frames'] = frames
            cur_video_dict['pos'] = frame_pos
            cur_video_dict['rot'] = frame_rot
            cur_video_dict['ts'] = frame_ts
            cur_video_info['real_frames'] = frames
            cur_video_info['real_frame_pos'] = frame_pos
            cur_video_info['real_frame_rot'] = frame_rot
            cur_video_info['real_frame_ts'] = frame_ts


            # Store current video result
            cur_video_dict['suggestion_for_next_clip'] = []
            cur_video_dict['trim_for_suggested_clips'] = {}
            tbc_meta_info[tbc_video_name] = cur_video_dict


        # Compute suggestions for each 
        global median_cam_velocity
        median_cam_velocity = np.median(camera_velocities)
        max_distance_between_camera_views_for_edge = 3 * median_cam_velocity
        angular_cost_coeff = 5 / np.pi * median_cam_velocity
        max_cost_to_be_suggested = 5 * median_cam_velocity
        for cur_last_video_name in tbc_meta_info.keys():
            last_video_dict = tbc_meta_info[cur_last_video_name]
            if not last_video_dict['is_before_other_video_ok']:
                continue

            cur_video_as_last_graph = nx.DiGraph()
            
            # Get all vertices for the current video
            last_video_vertices = []
            if last_video_dict['is_stabilizable']:
                for sampled_percent_i in range(len(last_video_dict['sampled_percents'])):
                    last_video_vertices.append((cur_last_video_name, sampled_percent_i))
            else:
                last_video_vertices.append((cur_last_video_name, -1))
            
            # Create the edges for current last video
            e_list = []
            for last_video_vertex_i in range(len(last_video_vertices)-1):
                e_list.append((last_video_vertices[last_video_vertex_i], last_video_vertices[last_video_vertex_i+1], 0))
            cur_video_as_last_graph.add_weighted_edges_from(e_list)
            
            for cur_next_video_name in tbc_meta_info.keys():
                if cur_next_video_name==cur_last_video_name:
                    continue
                cur_next_video_dict = tbc_meta_info[cur_next_video_name]
                if not cur_next_video_dict['is_after_other_video_ok']:
                    continue

                # Simple case where both cannot be stabilized
                if not last_video_dict['is_stabilizable'] and not cur_next_video_dict['is_stabilizable']:
                    last_video_vertex_i = -1
                    next_video_vertex_i = 0
                    last_video_vertex_pos = all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i]
                    next_video_vertex_pos = all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i]
                    distance = np.linalg.norm(last_video_vertex_pos - next_video_vertex_pos)
                    if distance > max_distance_between_camera_views_for_edge:
                        continue
                    cost = distance + angular_cost_coeff * angular_cost(last_video_vertex_pos - all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i-1], all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i+1] - next_video_vertex_pos, next_video_vertex_pos - last_video_vertex_pos, all_videos_sampled_rot[cur_last_video_name][last_video_vertex_i], all_videos_sampled_rot[cur_next_video_name][next_video_vertex_i])
                    if cost < max_cost_to_be_suggested:
                        tbc_meta_info[cur_last_video_name]['suggestion_for_next_clip'].append(cur_next_video_name)
                        tbc_meta_info[cur_last_video_name]['trim_for_suggested_clips'][cur_next_video_name] = [last_video_vertex_i, next_video_vertex_i]
                    continue


                # Get vertices and edges for current next video
                cur_next_video_vertices = []
                if cur_next_video_dict['is_stabilizable']:
                    for sampled_percent_i in range(len(cur_next_video_dict['sampled_percents'])):
                        cur_next_video_vertices.append((cur_next_video_name, sampled_percent_i))
                else:
                    cur_next_video_vertices.append((cur_next_video_name, 0))
                edges_for_current_next_video = []
                for next_video_vertex_i in range(len(cur_next_video_vertices)-1):
                    edges_for_current_next_video.append((cur_next_video_vertices[next_video_vertex_i], cur_next_video_vertices[next_video_vertex_i+1], 0))
                
                # Connect two videos' vertices
                if last_video_dict['is_stabilizable'] and cur_next_video_dict['is_stabilizable']:
                    for last_video_vertex_i in range(5, len(last_video_vertices)):
                        for next_video_vertex_i in range(len(cur_next_video_vertices)-5):
                            last_video_vertex_pos = all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i]
                            next_video_vertex_pos = all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i]
                            distance = np.linalg.norm(last_video_vertex_pos - next_video_vertex_pos)
                            if distance > max_distance_between_camera_views_for_edge:
                                continue
                            edges_for_current_next_video.append((last_video_vertices[last_video_vertex_i], cur_next_video_vertices[next_video_vertex_i], distance + angular_cost_coeff * angular_cost(last_video_vertex_pos - all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i-1], all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i+1] - next_video_vertex_pos, next_video_vertex_pos - last_video_vertex_pos, all_videos_sampled_rot[cur_last_video_name][last_video_vertex_i], all_videos_sampled_rot[cur_next_video_name][next_video_vertex_i])))
                elif last_video_dict['is_stabilizable']:
                    next_video_vertex_i = 0
                    for last_video_vertex_i in range(5, len(last_video_vertices)):
                        last_video_vertex_pos = all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i]
                        next_video_vertex_pos = all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i]
                        distance = np.linalg.norm(last_video_vertex_pos - next_video_vertex_pos)
                        if distance > max_distance_between_camera_views_for_edge:
                            continue
                        edges_for_current_next_video.append((last_video_vertices[last_video_vertex_i], cur_next_video_vertices[next_video_vertex_i], distance + angular_cost_coeff * angular_cost(last_video_vertex_pos - all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i-1], all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i+1] - next_video_vertex_pos, next_video_vertex_pos - last_video_vertex_pos, all_videos_sampled_rot[cur_last_video_name][last_video_vertex_i], all_videos_sampled_rot[cur_next_video_name][next_video_vertex_i])))
                elif cur_next_video_dict['is_stabilizable']:
                    last_video_vertex_i = -1
                    for next_video_vertex_i in range(len(cur_next_video_vertices)-5):
                        last_video_vertex_pos = all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i]
                        next_video_vertex_pos = all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i]
                        distance = np.linalg.norm(last_video_vertex_pos - next_video_vertex_pos)
                        if distance > max_distance_between_camera_views_for_edge:
                            continue
                        edges_for_current_next_video.append((last_video_vertices[last_video_vertex_i], cur_next_video_vertices[next_video_vertex_i], distance + angular_cost_coeff * angular_cost(last_video_vertex_pos - all_videos_sampled_pos[cur_last_video_name][last_video_vertex_i-1], all_videos_sampled_pos[cur_next_video_name][next_video_vertex_i+1] - next_video_vertex_pos, next_video_vertex_pos - last_video_vertex_pos, all_videos_sampled_rot[cur_last_video_name][last_video_vertex_i], all_videos_sampled_rot[cur_next_video_name][next_video_vertex_i])))
                
                cur_video_as_last_graph.add_weighted_edges_from(edges_for_current_next_video)
                try:
                    shortest_path = nx.shortest_path(cur_video_as_last_graph, last_video_vertices[0], cur_next_video_vertices[-1], 'weight')
                    for path_node_i in range(len(shortest_path)-1):
                        if cur_video_as_last_graph[shortest_path[path_node_i]][shortest_path[path_node_i+1]]['weight'] > 0:
                            if cur_video_as_last_graph[shortest_path[path_node_i]][shortest_path[path_node_i+1]]['weight'] < max_cost_to_be_suggested:
                                tbc_meta_info[cur_last_video_name]['suggestion_for_next_clip'].append(cur_next_video_name)
                                tbc_meta_info[cur_last_video_name]['trim_for_suggested_clips'][cur_next_video_name] = [shortest_path[path_node_i][1], shortest_path[path_node_i+1][1]]
                                global video_graph
                                video_graph.add_edge(cur_last_video_name, cur_next_video_name, weight=cur_video_as_last_graph[shortest_path[path_node_i]][shortest_path[path_node_i+1]]['weight'])
                                video_graph[cur_last_video_name][cur_next_video_name].update({'trim_location': [shortest_path[path_node_i][1], shortest_path[path_node_i+1][1]]})
                            break
                except Exception as e:
                    pass
                cur_video_as_last_graph.remove_edges_from(edges_for_current_next_video)
            
            # print(cur_last_video_name, tbc_meta_info[cur_last_video_name]['suggestion_for_next_clip'], tbc_meta_info[cur_last_video_name]['trim_for_suggested_clips'])


                
            


        return jsonify(tbc_meta_info), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

def angular_cost(last_video_forward_vec, next_video_forward_vec, translation_vec, last_video_cam_rot, next_video_cam_rot):
    angle1 = np.arccos(np.sum(last_video_forward_vec*translation_vec) / (np.linalg.norm(last_video_forward_vec) * np.linalg.norm(translation_vec)))
    angle2 = np.arccos(np.sum(next_video_forward_vec*translation_vec) / (np.linalg.norm(next_video_forward_vec) * np.linalg.norm(translation_vec)))
    return (angle1 + angle2 + np.linalg.norm((Rotation.from_euler(rotation_order, last_video_cam_rot).inv() * Rotation.from_euler(rotation_order, next_video_cam_rot)).as_rotvec())) / np.linalg.norm(translation_vec)


# Set the up vector for current project
# Receive: {'up_vec_rot_mat': (list; given in numpy matrix format, which is
# different from glMatrix mat3, [[row1col1, row1col2, row1col3], [row2col1, 
# row2col2, row2col3], [row3col1, row3col2, row3col3]])}
# Return: {'msg': 'up vec successfuly set'}
@app.route('/set_up_vector', methods=['POST'])
def set_up_vector():
    try:
        global up_vec

        # read request
        js = request.get_json()
        up_vec = np.array(js['up_vec'])

        return jsonify({'msg': 'up vec successfuly set'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Receive: {'video_name': (string; name of the requested video)}
# Return: {
#  'frames': (list of jpeg image bytes),
#  'pos': (list of list representing camera positions, contain None for not 
#  registered frames),
#  'rot': (same as above but as rotation matrices)
#  'ts': (list of double)
#  'original_video_ts': (list of double)
# }
@app.route('/cancel_stabilization', methods=['POST'])
def cancel_stabilization():
    try:
        # read request
        js = request.get_json()
        video_name = js['video_name']
        
        # set up vec
        global tbc_stabilizers, tbc_video_info
        tbc_stabilizers[video_name] = None

        if video_name == mega_video_name:
            final_video_config = tbc_video_info[mega_video_name]['final_video_config']
            concatenate_frames = tbc_video_info[mega_video_name]['concatenate_frames']

            final_video_folder = os.path.join(project_path, mega_video_name)
            os.makedirs(final_video_folder, exist_ok=True)
            with open(os.path.join(final_video_folder, 'final_video_config.json'), 'w+') as file:
                json.dump(final_video_config, file)
            with open(os.path.join(final_video_folder, 'concatenate_frames.json'), 'w+') as file:
                json.dump(concatenate_frames, file)

        return jsonify({'frames': tbc_video_info[video_name]['real_frames'], 'pos': tbc_video_info[video_name]['real_frame_pos'], 'rot': tbc_video_info[video_name]['real_frame_rot'], 'ts': tbc_video_info[video_name]['real_frame_ts'], 'original_video_ts': tbc_video_info[video_name]['real_frame_ts']}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Stabilize video
# Receive: 
# {'video_name': (string; name of the stabilized video),
# 'start_percent': (double; start of selected range, how many percent through video),
# 'end_percent': (double; end of selected range, same as last one), 
# 'stabilization_strength': (int; interval used for sampling stabilization data points, 
# must be a multiple of original_sampling_interval), 
# 'local_velocity_adjustment_curve_y': (list of double; slow down or speed up at each dist, 
# for initial stabilization (i.e. user click stabilized checkbox), just set as a bunch of 1.), 
# 'local_velocity_adjustment_curve_x': (list of double between 0 and 1. The relative timestamp 
# (horizontal axis value of frontend curve) for local_velocity_adjustment_curve_y.)}
# Return: {'video_name': (string; name of the stabilized video), 
# 'pos': (list; the position vectors), 
# 'rot': (list; the rotation matrices),
# 'ts': (list of doubles; the timestamps for each frame),
# 'max_stabilization_strength': (int), 
# 'original_video_ts': (list of doubles), 
# 'velocity_smoothing_percents': (list of doubles; progresses for velocity smoothing multipliers), 
# 'velocity_smoothing_multipliers': (list of doubles; the velocity smoothing multipliers for each progress point)}
@app.route('/stabilize_video', methods=['POST'])
def stabilize_video():
    try:
        global tbc_stabilizers, final_video_fps, tbc_video_info, tbc_stabilizers_full_range

        # read request
        js = request.get_json()
        video_name = js['video_name']
        start_percent = js['start_percent']
        end_percent = js['end_percent']
        sampling_interval = js['stabilization_strength'] * tbc_video_info[video_name]['original_sampling_interval']
        local_velocity_adjustment_curve_x = js['local_velocity_adjustment_curve_x']
        local_velocity_adjustment_curve_y = js['local_velocity_adjustment_curve_y']
        cur_video_info = tbc_video_info[video_name]

        # stabilize video
        pos = np.array(cur_video_info['frame_pos'])
        rot = np.array(cur_video_info['frame_rot'])
        ts = np.array(cur_video_info['frame_ts'])
        # Not stabilized at all before
        if tbc_stabilizers[video_name] is None:
            dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start = Stabilize_Helper(pos, rot, ts, start_percent, end_percent, tbc_video_info[video_name]['original_sampling_interval']*max(1, int(js['stabilization_strength']/3))).get_original_ts_to_distance_dense_mapping()
            tbc_stabilizers[video_name] = Stabilizer(pos, rot, ts, start_percent, end_percent, sampling_interval, local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y, final_video_fps, dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start)

            # Prepare for dragging slider
            tbc_stabilizers_full_range[video_name] = Stabilizer(pos, rot, ts, 0.0, 1.0, tbc_video_info[video_name]['original_sampling_interval'], [i/9 for i in range(10)], [1 for i in range(10)], final_video_fps, dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start)
        # Previously stabilized
        else:
            prev_selected_range, prev_sampling_interval = tbc_stabilizers[video_name].get_stabilization_params()
            # Did not change selected range and sampling interval
            if np.isclose(prev_selected_range[0], start_percent) and np.isclose(prev_selected_range[1], end_percent) and np.isclose(prev_sampling_interval, sampling_interval):
                tbc_stabilizers[video_name].set_local_velocity_adjustment_curve(local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y)
            # Changed selected range or sampling interval
            else:
                dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start = Stabilize_Helper(pos, rot, ts, start_percent, end_percent, tbc_video_info[video_name]['original_sampling_interval']).get_original_ts_to_distance_dense_mapping()
                tbc_stabilizers[video_name] = Stabilizer(pos, rot, ts, start_percent, end_percent, sampling_interval, local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y, final_video_fps, dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start)
                
        # get the stabilization result
        stabilized_pos, stabilized_rot, stabilized_ts, stabilized_ts_original, vsp, vsm = tbc_stabilizers[video_name].get_stabilization_result()

        # calculate maximum stabilization strength
        cur_video_info = tbc_video_info[video_name]
        original_sampling_interval = cur_video_info['original_sampling_interval']
        cur_stabilization_strength = min(10, int((end_percent - start_percent)/original_sampling_interval/2))
        _, _, sampled_ts = sample_points(cur_video_info['frame_pos'], cur_video_info['frame_rot'], cur_video_info['frame_ts'], start_percent, end_percent, cur_stabilization_strength*original_sampling_interval)
        while len(sampled_ts) <= 4:
            cur_stabilization_strength -= 1
            _, _, sampled_ts = sample_points(cur_video_info['frame_pos'], cur_video_info['frame_rot'], cur_video_info['frame_ts'], start_percent, end_percent, cur_stabilization_strength*original_sampling_interval)

        # Update mega video if we stabilize mega video
        if video_name == mega_video_name:
            num_frames = len(stabilized_ts)

            # Update final_video_config
            final_video_config = deepcopy(tbc_video_info[mega_video_name]['final_video_config'])
            final_video_name = 'stabilized_mega_video.mp4'
            final_video_config['final_video_config_list'] = [{'video_name': final_video_name, 'frame_indexes': [i for i in range(num_frames)],  'blend': [0] * num_frames}]

            # Update concatenate_frames
            concatenate_frames = []
            for frame_i in range(num_frames):
                concatenate_frames.append(get_cur_frame_dict(tbc_video_info['cam_intrinsic_params'], stabilized_pos[frame_i], stabilized_rot[frame_i], get_frame_name(None, final_video_name, frame_i, 'png')))
            
            final_video_folder = os.path.join(project_path, mega_video_name)
            os.makedirs(final_video_folder, exist_ok=True)
            with open(os.path.join(final_video_folder, 'final_video_config.json'), 'w+') as file:
                json.dump(final_video_config, file)
            with open(os.path.join(final_video_folder, 'concatenate_frames.json'), 'w+') as file:
                json.dump(concatenate_frames, file)

        return jsonify({'video_name': video_name, 'pos': stabilized_pos, 'rot': stabilized_rot, 'ts': stabilized_ts, 'max_stabilization_strength': cur_stabilization_strength, 'original_video_ts': stabilized_ts_original, 'velocity_smoothing_percents': vsp.tolist(), 'velocity_smoothing_multipliers': vsm}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Responsive API, use when user drag a point along the local velocity adjustment curve
# Receive: {'video_name': (string; name of stabilized video), 'percent': (float; the percent user
# clicked)}
# Return: {'pos': (list; the position vector), 'rot': (list; the rotation matrix)}
@app.route('/get_pos_and_rot_at_progress_percent', methods=['POST'])
def get_pos_and_rot_at_progress_percent():
    try:
        global tbc_stabilizers_full_range

        # read request
        js = request.get_json()
        video_name = js['video_name']
        percent = js['percent']

        # Get pos and rot
        pos, rot = tbc_stabilizers_full_range[video_name].get_pos_and_rot_at_percent(percent)

        return jsonify({'pos': pos, 'rot': rot}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Receive: {'video_name': (string; name of the requested video)}
# Return: {'pos': (list; list of position vectors), 'rot': (list of rotation matrices), 'ts': (list; timestamps for each pos and rot)}
# If a video just cannot be concatenated under the current setting, the values in the returned dict will all be None
@app.route('/get_cam_trajectory', methods=['POST'])
def get_cam_trajectory():
    try:
        global tbc_stabilizers, tbc_video_info

        # read request
        js = request.get_json()
        video_name = js['video_name']

        # Get pos rot ts
        # stabilized, just get the whole trajectory
        if not tbc_stabilizers[video_name] is None:
            pos, rot, ts, _, _, _ = tbc_stabilizers[video_name].get_stabilization_result()
        # not stabilized, at start & end, get only the frames used for concatenation.
        # Also extract frames in the middle if they are extracted and registered.
        else:
            # Get the range of to-be-sent frames
            start_i, end_i = get_relevant_range(tbc_video_info[video_name]['start_considered_range'], tbc_video_info[video_name]['end_considered_range'])
            if start_i is np.nan and end_i is np.nan:
                return jsonify({'pos': None, 'rot': None, 'ts': None}), 200

            # Get and format result
            pos = tbc_video_info[video_name]['frame_pos'][start_i:end_i]
            rot_eulers = tbc_video_info[video_name]['frame_rot'][start_i:end_i]
            rot = []
            for rot_euler in rot_eulers:
                rot.append(Rotation.from_euler(rotation_order, rot_euler).as_matrix().tolist())
            ts = tbc_video_info[video_name]['frame_ts'][start_i:end_i]
            
        return jsonify({'pos': pos, 'rot': rot, 'ts': ts}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Receive: {
# 'concatenation_order': (list of strings representing video names in the
# desired order of concatenation.)
# Return: 
# {'pos': (list; list of positions, None if using real frames), 
#  'rot': (list; list of rotation matrices, None if using real frames), 
#  'ts':(list of floats; the timestamp of the camera position and rotations in the final 
#  concatenated video)},
#  ‘frames': (list of jpeg bytes; None if using rendered frames),
#  'sampled_percents': (list of floats)
@app.route('/concatenate_video', methods=['POST'])
def concatenate_video():
    try:
        global up_vec, tbc_stabilizers, final_video_fps, tbc_video_info, project_path, repo_path

        # read request
        js = request.get_json()
        concatenation_order = js['concatenation_order']

        # build initial concatenation_config
        concatenate_config = generate_initial_concatenate_config_by_order(tbc_video_info, tbc_stabilizers, concatenation_order, up_vec, final_video_fps)
        
        # compute concatenation clip configuration
        time_between_frames = 1/final_video_fps
        num_concatenation_clip = len(concatenate_config['concatenate_dicts'])
        for concatenate_dict_i in range(num_concatenation_clip):
            # path and velocity
            concatenate_dict = concatenate_config['concatenate_dicts'][concatenate_dict_i]
            path_control_points, path_lengths, initial_velocities, accels_along_path, travel_times = calc_default_path_and_velocity(concatenate_dict, time_between_frames)
            concatenate_dict['path_control_points'] = path_control_points
            concatenate_dict['path_lengths'] = path_lengths
            concatenate_dict['initial_velocities'] = initial_velocities
            concatenate_dict['accels_along_path'] = accels_along_path
            concatenate_dict['travel_times'] = travel_times

            # orientation
            orientation_control_points, transition_refs, transition_times = calc_default_orientation_change(concatenate_dict, up_vec, time_between_frames)
            concatenate_dict['orientation_control_points'] = orientation_control_points
            concatenate_dict['transition_refs'] = transition_refs
            concatenate_dict['transition_times'] = transition_times

        # generate to-be-rendered json and final video configuration
        stabilized_video_selected_range_dict = {}
        frontend_pos = []
        frontend_rot = []
        frontend_ts = []
        frontend_frames = []
        last_video_end_time = 0
        if not concatenate_config['concatenate_dicts'][0]['last_video_is_stabilized']:
            first_to_be_concatenated_video_start_blend_frame_index = concatenate_config['concatenate_dicts'][0]['last_video_frame_indexes'][0]
            if first_to_be_concatenated_video_start_blend_frame_index > 0:
                final_video_config_list = [{'video_name': concatenate_config['concatenate_dicts'][0]['last_video_file_name'], 'frame_indexes': [i for i in range(first_to_be_concatenated_video_start_blend_frame_index)],  'blend': [1] * first_to_be_concatenated_video_start_blend_frame_index}]
            else:
               final_video_config_list = [] 
        else:
            final_video_config_list = []
        concatenate_frames = []
        cam_intrinsic_params = concatenate_config['cam_intrinsic_params']
        for concatenate_dict_i in range(len(concatenate_config['concatenate_dicts'])):
            concatenate_dict = concatenate_config['concatenate_dicts'][concatenate_dict_i]

            # deal with last video
            # Not stabilized, consider blending
            if not concatenate_dict['last_video_is_stabilized']:
                # Fill the concatenate_frames and final_video_config list with last_video_frames
                # Percent in 'blend' list show the percent of real frames during blending
                # See if this is a new segment or is overlapping with the previous segment
                is_new_config_segment_created = False
                if len(final_video_config_list)==0 or concatenate_dict['last_video_frame_indexes'][0] > final_video_config_list[-1]['frame_indexes'][-1]:
                    cur_seg_config = {'video_name': concatenate_dict['last_video_file_name'], 'frame_indexes': [], 'blend': []}
                    is_new_config_segment_created = True
                else:
                    cur_seg_config = final_video_config_list[-1]

                # Fill in an initial dict for frontend if the first video is not stabilized
                for last_video_frame_i in range(len(concatenate_dict['last_video_frame_indexes'])):
                    # Fill concatenate_frames list
                    cur_frame_rotation_mat = Rotation.from_euler(rotation_order, concatenate_dict['last_video_frame_rot'][last_video_frame_i]).as_matrix().tolist()
                    cur_frame_name = get_frame_name("rendered", concatenate_dict['last_video_file_name'], concatenate_dict['last_video_frame_indexes'][last_video_frame_i], 'png')
                    cur_frame_position = concatenate_dict['last_video_frame_pos'][last_video_frame_i]
                    concatenate_frames.append(get_cur_frame_dict(cam_intrinsic_params, cur_frame_position, cur_frame_rotation_mat, cur_frame_name))

                    # Fill final_video_config
                    cur_frame_index = concatenate_dict['last_video_frame_indexes'][last_video_frame_i]
                    try:
                        index_in_final_config = cur_seg_config['frame_indexes'].index(cur_frame_index)
                        cur_seg_config['blend'][index_in_final_config] = np.min(( cur_seg_config['blend'][index_in_final_config], 1 - last_video_frame_i/len(concatenate_dict['last_video_frame_indexes']) ))
                    except ValueError:
                        cur_seg_config['frame_indexes'].append(cur_frame_index)
                        cur_seg_config['blend'].append(1 - (last_video_frame_i)/len(concatenate_dict['last_video_frame_indexes']))
                        
                if is_new_config_segment_created:
                    final_video_config_list.append(cur_seg_config)

                # Append to result for frontend
                frontend_pos += tbc_video_info[concatenate_dict['last_video_file_name']]['real_frame_pos']
                frontend_rot += tbc_video_info[concatenate_dict['last_video_file_name']]['real_frame_rot']
                frontend_ts += [ts+last_video_end_time for ts in tbc_video_info[concatenate_dict['last_video_file_name']]['real_frame_ts']]
                frontend_frames += tbc_video_info[concatenate_dict['last_video_file_name']]['real_frames']
                
                # increment last_video_end_time
                last_video_end_time += concatenate_dict['last_video_frame_ts'][-1] 

            # Stabilized, just put everything in
            else:
                cur_seg_config = {'video_name': 'stabilized_' + concatenate_dict['last_video_file_name'], 'frame_indexes': [], 'blend': []}
                cur_video_pos, cur_video_rot, cur_video_ts, _, _, _ = tbc_stabilizers[concatenate_dict['last_video_file_name']].get_stabilization_result()
                stabilized_video_selected_range_dict[concatenate_dict['last_video_file_name']], _ = tbc_stabilizers[concatenate_dict['last_video_file_name']].get_stabilization_params()
                for frame_index in range(len(cur_video_pos)):
                    cur_seg_config['frame_indexes'].append(frame_index)
                    cur_seg_config['blend'].append(0)
                    cur_frame_name = get_frame_name('stabilized', concatenate_dict['last_video_file_name'], frame_index, 'png')
                    concatenate_frames.append(get_cur_frame_dict(cam_intrinsic_params, cur_video_pos[frame_index], cur_video_rot[frame_index], cur_frame_name))
                final_video_config_list.append(cur_seg_config)
                
                # Append to result for frontend
                frontend_pos += cur_video_pos
                frontend_rot += cur_video_rot
                frontend_ts += [ts+last_video_end_time for ts in cur_video_ts]
                frontend_frames += [None] * len(cur_video_ts)

                # increment last_video_end_time
                last_video_end_time += cur_video_ts[-1]
            

            # Deal with concatenation clip
            cur_clip_video_name = f'concatenation_clip_{concatenate_dict_i+1}'
            cur_seg_config = {'video_name': cur_clip_video_name, 'frame_indexes': [], 'blend': []}
            path_control_points = concatenate_dict['path_control_points']
            path_lengths = concatenate_dict['path_lengths']
            initial_velocities = concatenate_dict['initial_velocities']
            accels_along_path = concatenate_dict['accels_along_path']
            travel_times = concatenate_dict['travel_times']
            orientation_control_points = concatenate_dict['orientation_control_points']
            transition_refs = concatenate_dict['transition_refs']
            transition_times = concatenate_dict['transition_times']
            cur_time_in_concatenate_clip = time_between_frames
            cur_frame_index = 0
            total_travel_time = np.sum(travel_times)
            while not np.isclose(cur_time_in_concatenate_clip, total_travel_time):
                # Calculate pos
                cur_distance_along_whole_path = get_distance(initial_velocities, accels_along_path, travel_times, cur_time_in_concatenate_clip)
                curve_control_points, t_along_curve = get_path_control_points_and_t(path_control_points, path_lengths, cur_distance_along_whole_path)
                cur_pos = bezier(curve_control_points, t_along_curve).tolist()

                # Calculate orientation
                orientation_curve_control_points, t_along_orientation_curve, cur_transition_ref = get_orientation_control_points_and_t(orientation_control_points, transition_refs, transition_times, cur_time_in_concatenate_clip)
                if cur_transition_ref == 'world':
                    cur_rot = get_orientation_mat_along_rotation_path(orientation_curve_control_points, t_along_orientation_curve).tolist()
                elif cur_transition_ref == 'path':
                    cur_path_tangent = d_bezier(curve_control_points, t_along_curve)
                    path_ref_mat = get_path_coord_zero_orientation_mat(cur_path_tangent, up_vec)
                    rot_mat_in_path_ref = get_orientation_mat_along_rotation_path(orientation_curve_control_points, t_along_orientation_curve)
                    cur_rot = (path_ref_mat @ rot_mat_in_path_ref).tolist()


                # Append to things
                concatenate_frames.append(get_cur_frame_dict(cam_intrinsic_params, cur_pos, cur_rot, cur_clip_video_name + f'_{cur_frame_index:08d}.png'))
                cur_seg_config['frame_indexes'].append(cur_frame_index)
                cur_seg_config['blend'].append(0)
                frontend_pos.append(cur_pos)
                frontend_rot.append(cur_rot)
                frontend_ts.append(last_video_end_time + cur_time_in_concatenate_clip)
                frontend_frames.append(None)

                # Increment time and frame index
                cur_time_in_concatenate_clip += time_between_frames
                cur_frame_index += 1
            
            # Append to final_video_config_list
            final_video_config_list.append(cur_seg_config)

            # Increment last_video_end_time
            last_video_end_time += total_travel_time
            

            # Deal with next video
            # Not stabilized
            if not concatenate_dict['next_video_is_stabilized']:
                # Fill the concatenate_frames list and the final_video_config with next_video_frames 
                # Percent in 'blend' list show the percent of real frames during blending
                cur_seg_config = {'video_name': concatenate_dict['next_video_file_name'], 'frame_indexes': [], 'blend': []}
                for next_video_frame_i in range(len(concatenate_dict['next_video_frame_indexes'])):
                    # Fill concatenate_frames list
                    cur_frame_rotation_mat = Rotation.from_euler(rotation_order, concatenate_dict['next_video_frame_rot'][next_video_frame_i]).as_matrix().tolist()
                    cur_frame_name = get_frame_name("rendered", concatenate_dict['next_video_file_name'], concatenate_dict['next_video_frame_indexes'][next_video_frame_i], 'png')
                    cur_frame_position = concatenate_dict['next_video_frame_pos'][next_video_frame_i]
                    concatenate_frames.append(get_cur_frame_dict(cam_intrinsic_params, cur_frame_position, cur_frame_rotation_mat, cur_frame_name))

                    # Fill final_video_config
                    cur_frame_index = concatenate_dict['next_video_frame_indexes'][next_video_frame_i]
                    cur_seg_config['frame_indexes'].append(cur_frame_index)
                    cur_seg_config['blend'].append((next_video_frame_i+1)/len(concatenate_dict['next_video_frame_indexes']))
                final_video_config_list.append(cur_seg_config)


                # Fill final_video_config with frames of the next video that are irrelevant to concatenation
                # Not last dict
                if concatenate_dict_i < len(concatenate_config['concatenate_dicts']) - 1:
                    irrelevant_part_ending_index = concatenate_config['concatenate_dicts'][concatenate_dict_i+1]['last_video_frame_indexes'][0] - 1
                    if irrelevant_part_ending_index > cur_frame_index:
                        cur_seg_config = {'video_name': concatenate_dict['next_video_file_name'], 'frame_indexes': [i for i in range(cur_frame_index+1,irrelevant_part_ending_index+1)], 'blend': [1] * (irrelevant_part_ending_index - cur_frame_index)}
                        final_video_config_list.append(cur_seg_config)
                # Last dict => final video segment to deal with
                else:
                    last_video_cap = cv2.VideoCapture(os.path.join(os.path.join(project_path, 'to_be_concatenated'), concatenate_dict['next_video_file_name']))
                    total_num_frame = int(last_video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    last_video_cap.release()
                    cur_seg_config = {'video_name': concatenate_dict['next_video_file_name'], 'frame_indexes': [i for i in range(cur_frame_index+1, total_num_frame)], 'blend': [1 for i in range(cur_frame_index+1, total_num_frame)]}
                    final_video_config_list.append(cur_seg_config)

                    # Append to result for frontend
                    frontend_pos += tbc_video_info[concatenate_dict['next_video_file_name']]['real_frame_pos']
                    frontend_rot += tbc_video_info[concatenate_dict['next_video_file_name']]['real_frame_rot']
                    frontend_ts += [ts+last_video_end_time for ts in tbc_video_info[concatenate_dict['next_video_file_name']]['real_frame_ts']]
                    frontend_frames += tbc_video_info[concatenate_dict['next_video_file_name']]['real_frames']
                
            # Stabilized
            else:
                # Only fill in if it's the last video
                if concatenate_dict_i == len(concatenate_config['concatenate_dicts']) - 1:
                    cur_seg_config = {'video_name': 'stabilized_' + concatenate_dict['next_video_file_name'], 'frame_indexes': [], 'blend': []}
                    cur_video_pos, cur_video_rot, cur_video_ts, _, _, _ = tbc_stabilizers[concatenate_dict['next_video_file_name']].get_stabilization_result()
                    stabilized_video_selected_range_dict[concatenate_dict['next_video_file_name']], _ = tbc_stabilizers[concatenate_dict['next_video_file_name']].get_stabilization_params()
                    for frame_index in range(len(cur_video_pos)):
                        cur_seg_config['frame_indexes'].append(frame_index)
                        cur_seg_config['blend'].append(0)
                        cur_frame_name = get_frame_name('stabilized', concatenate_dict['next_video_file_name'], frame_index, 'png')
                        concatenate_frames.append(get_cur_frame_dict(cam_intrinsic_params, cur_video_pos[frame_index], cur_video_rot[frame_index], cur_frame_name))
                    final_video_config_list.append(cur_seg_config)

                    # Append to result for frontend
                    frontend_pos += cur_video_pos
                    frontend_rot += cur_video_rot
                    frontend_ts += [ts+last_video_end_time for ts in cur_video_ts]
                    frontend_frames += [None] * len(cur_video_ts)

        # Store result
        final_video_config = {'frame_size': cam_intrinsic_params[2:], 'time_between_frames': time_between_frames, 'final_video_config_list': final_video_config_list, 'stabilized_video_selected_range': stabilized_video_selected_range_dict}
        final_video_folder = os.path.join(project_path, mega_video_name)
        os.makedirs(final_video_folder, exist_ok=True)
        with open(os.path.join(final_video_folder, 'final_video_config.json'), 'w+') as file:
            json.dump(final_video_config, file)
        with open(os.path.join(final_video_folder, 'concatenate_frames.json'), 'w+') as file:
            json.dump(concatenate_frames, file)


        # Create the mega video for further processing
        global original_sampling_interval_sec, tbc_stabilizers_full_range
        mega_video_original_sampling_interval = original_sampling_interval_sec/frontend_ts[-1]
        tbc_video_info[mega_video_name] = {}
        tbc_video_info[mega_video_name]['original_sampling_interval'] = mega_video_original_sampling_interval
        tbc_video_info[mega_video_name]['real_frames'] = frontend_frames
        tbc_video_info[mega_video_name]['real_frame_pos'] = frontend_pos
        tbc_video_info[mega_video_name]['real_frame_rot'] = frontend_rot
        tbc_video_info[mega_video_name]['real_frame_ts'] = frontend_ts
        none_indexes = [i for i in range(len(frontend_pos)) if frontend_pos[i] is None]
        nan_removed_pos = [pos for i,pos in enumerate(frontend_pos) if i not in none_indexes]
        nan_removed_rot = [pos for i,pos in enumerate(frontend_rot) if i not in none_indexes]
        nan_removed_ts = [pos for i,pos in enumerate(frontend_ts) if i not in none_indexes]
        mega_video_pos, mega_video_rot, mega_video_ts = sample_points(nan_removed_pos, nan_removed_rot, nan_removed_ts, 0.0, 1.0, mega_video_original_sampling_interval)
        tbc_video_info[mega_video_name]['frame_pos'] = mega_video_pos
        tbc_video_info[mega_video_name]['frame_rot'] = [Rotation.from_matrix(rot).as_euler(rotation_order) for rot in mega_video_rot]
        tbc_video_info[mega_video_name]['frame_ts'] = mega_video_ts
        tbc_video_info[mega_video_name]['final_video_config'] = final_video_config
        tbc_video_info[mega_video_name]['concatenate_frames'] = concatenate_frames
        tbc_stabilizers[mega_video_name] = None
        tbc_stabilizers_full_range[mega_video_name] = None
        sampled_percents = (np.array(mega_video_ts) / mega_video_ts[-1]).tolist()
       
                    
        return jsonify({'pos': frontend_pos, 'rot': frontend_rot, 'ts': frontend_ts, 'frames': frontend_frames, 'sampled_percents': sampled_percents}), 200   
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400


# Receive: {
# 'final_video_name': (string; name of the final video without file extension),
# 'concatenation_order': (list of strings representing video names in the
# desired order of concatenation.), }
# Return: {'msg': f'Shell scripts for rendering {final_video_name} are generated in {project_path}/{final_video_name}. Run render_with_extra_frames_along_final_trajectory.sh if you want higher quality. Run render_with_pre-visualization_reconstruction.sh if you want to save time.'}
@app.route('/render_final_video', methods=['POST'])
def render_final_video():
    try:
        global project_path, shell_repo_path, shell_project_path

        # read request
        js = request.get_json()
        final_video_name = js['final_video_name']
        concatenation_order = js['concatenation_order']

        # Properly handle case where user clicks cancel
        if final_video_name is None:
            return jsonify({'msg': f'Please enter a non-empty final video name.'}), 200

        # Generate shell script
        shutil.move(os.path.join(project_path, '.temp_final_video'), os.path.join(project_path, final_video_name))
        final_video_folder = os.path.join(project_path, final_video_name)
        generate_render_with_extra_frames_shell_script(shell_project_path, final_video_name, shell_repo_path, colmap_bin_path, concatenation_order, data_device, final_video_folder)
        concat_json_path = os.path.join(shell_project_path, final_video_name, 'concatenate_frames.json')
        concat_json_path = concat_json_path.replace('\\', '/')
        generate_render_shell_script(shell_project_path, concat_json_path, shell_repo_path, final_video_folder, final_video_name)

        return jsonify({'msg': f'Shell scripts for rendering {final_video_name} are generated in {project_path}/{final_video_name}. Run render_with_extra_frames_along_final_trajectory.sh if you want higher quality. Run render_with_pre-visualization_reconstruction.sh if you want to save time.'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Receive: {}
# Return: {'repo_path': repo_path, 'data_device': data_device, 'colmap_bin_path': colmap_bin_path}
@app.route('/get_settings', methods=['POST'])
def get_settings():
    try:
        global shell_repo_path, data_device, colmap_bin_path
        return jsonify({'repo_path': shell_repo_path, 'data_device': data_device, 'colmap_bin_path': colmap_bin_path}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

# Receive: {'repo_path': repo_path, 'data_device': data_device, 'colmap_bin_path': colmap_bin_path}
# Return: {'msg': 'Setting changed.'}
@app.route('/set_settings', methods=['POST'])
def set_settings():
    try:
        global shell_repo_path, shell_project_path, data_device, colmap_bin_path, project_name

        # read request
        js = request.get_json()
        shell_repo_path = js['repo_path']
        data_device = js['data_device']
        colmap_bin_path = js['colmap_bin_path']

        shell_repo_path = shell_repo_path.replace('\\', '/')
        colmap_bin_path = colmap_bin_path.replace('\\', '/')
        if not project_name is None:
            shell_project_path = os.path.join(shell_repo_path, 'data', project_name)
            shell_project_path = shell_project_path.replace('\\', '/')
        
        settings = {'repo_path': shell_repo_path, 'colmap_bin_path': colmap_bin_path, 'data_device': data_device}
        setting_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')
        with open(setting_json_path, 'w') as file:
            json.dump(settings, file)

        return jsonify({'msg': 'Setting changed.'}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400
    

@app.route('/load_video', methods=['POST'])
def load_video():
    try:
        global shell_repo_path, shell_project_path, data_device, colmap_bin_path, project_name

        # read request
        js = request.get_json()
        video_name = js['video_name']
        
        # load frames and video config
        with open(os.path.join(project_path, video_name, 'concatenate_frames.json'), 'r') as file:
            virtual_frames = json.load(file)
        with open(os.path.join(project_path, video_name, 'final_video_config.json'), 'r') as file:
            final_video_config = json.load(file)

        # Initialize fields
        frontend_pos = []
        frontend_rot = []
        frontend_ts = []
        frontend_frames = []
        sampled_percents = [i*0.1 for i in range(11)]
        time_between_frames = final_video_config['time_between_frames']

        cur_ts = 0
        cur_i_in_virtual_frames = 0
        final_video_config_list = final_video_config['final_video_config_list']
        for seg in final_video_config_list:
            cur_seg_video_name = seg['video_name']
            for frame_i_in_list in range(len(seg['frame_indexes'])):
                if seg['blend'][frame_i_in_list] > 0:
                    frontend_frames.append(tbc_video_info[cur_seg_video_name]['real_frames'][seg['frame_indexes'][frame_i_in_list]])
                    
                    if seg['blend'][frame_i_in_list] < 1:
                        frontend_pos.append(virtual_frames[cur_i_in_virtual_frames]['position'])
                        frontend_rot.append(virtual_frames[cur_i_in_virtual_frames]['rotation'])
                        cur_i_in_virtual_frames += 1
                    else:
                        frontend_pos.append(None)
                        frontend_rot.append(None)
                else:
                    if 'stabilized' in cur_seg_video_name:
                        cur_frame_name = get_frame_name('stabilized', cur_seg_video_name, seg['frame_indexes'][frame_i_in_list], 'png')
                    else:
                        cur_frame_name = get_frame_name(None, cur_seg_video_name, seg['frame_indexes'][frame_i_in_list], 'png')
                    while True:
                        if virtual_frames[cur_i_in_virtual_frames]['name'] == cur_frame_name:
                            break
                        cur_i_in_virtual_frames += 1
                    
                    frontend_pos.append(virtual_frames[cur_i_in_virtual_frames]['position'])
                    frontend_rot.append(virtual_frames[cur_i_in_virtual_frames]['rotation'])
                    frontend_frames.append(None)

                frontend_ts.append(cur_ts)
                cur_ts += time_between_frames


        return jsonify({'pos': frontend_pos, 'rot': frontend_rot, 'ts': frontend_ts, 'frames': frontend_frames, 'sampled_percents': sampled_percents}), 200  
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'error': str(traceback.format_exc())}), 400

if __name__ == '__main__':
    repo_path = os.path.dirname(os.path.dirname(__file__))
    repo_path = repo_path.replace('\\', '/')
    setting_json_path = os.path.join(repo_path, 'settings.json')
    if os.path.exists(setting_json_path):
        with open(setting_json_path, 'r') as file:
            settings = json.load(file)
        shell_repo_path = settings['repo_path']
        colmap_bin_path = settings['colmap_bin_path']
        data_device = settings['data_device']
    else:
        shell_repo_path = repo_path
        settings = {'repo_path': repo_path, 'colmap_bin_path': 'colmap', 'data_device': 'cuda'}
        with open(setting_json_path, 'w') as file:
            json.dump(settings, file)

    shutil.rmtree(os.path.join(repo_path, '.temp_project'), ignore_errors=True)
    os.mkdir(os.path.join(repo_path, '.temp_project'))
        
    app.run(port=3596)
