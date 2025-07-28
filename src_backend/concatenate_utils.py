from copy import deepcopy
import numpy as np
from scipy.spatial.transform import Rotation
import os

from orientation_quaternion import rotation_order

def get_cur_frame_dict(cam_instrinsic_params, pos, rot, frame_name):
    fx, fy, width, height = cam_instrinsic_params
    return {'name': frame_name, 'fx': fx, 'fy': fy, 'width': width, 'height': height, \
            'position': deepcopy(pos), 'rotation': deepcopy(rot)}

# Helper function to get the frame index of given frame
def frame_index_of(frame_file_name):
    return int(frame_file_name.split('.')[0].split('_')[-1])


def remove_slash(path):
    if path[-1]=='/':
        return path[:-1]
    else:
        return path
    


def generate_register_and_reconstruct_shell_script(project_path, repo_path, colmap_bin_path, env_scan_extract_fps, tbc_extract_fps, output_folder, data_device, tbc_two_ends_num_frame):
    project_path = remove_slash(project_path)
    colmap_bin_path = remove_slash(colmap_bin_path)
    repo_path = remove_slash(repo_path)
    shell_script = f'''
PROJECT_PATH={project_path}

REPO_PATH={repo_path}

COLMAP_PATH={colmap_bin_path}

eval "$(conda shell.bash hook)"
conda activate gaussian_splatting
python3 $REPO_PATH/src_server/extract_video_frames.py \\
    -s $PROJECT_PATH \\
    -esfps {env_scan_extract_fps} \\
    -tbcfps {tbc_extract_fps} \\
    -tbctef {tbc_two_ends_num_frame}
conda deactivate
$COLMAP_PATH feature_extractor \\
    --database_path $PROJECT_PATH/environment_scan/database.db \\
    --image_path $PROJECT_PATH/environment_scan/images \\
    --ImageReader.single_camera 1 \\
    --ImageReader.camera_model SIMPLE_PINHOLE
$COLMAP_PATH matches_importer \\
    --database_path $PROJECT_PATH/environment_scan/database.db \\
    --match_list_path $PROJECT_PATH/environment_scan/extracted_frames_match_list.txt
mkdir $PROJECT_PATH/environment_scan/sparse
$COLMAP_PATH mapper \\
    --database_path $PROJECT_PATH/environment_scan/database.db \\
    --image_path $PROJECT_PATH/environment_scan/images \\
    --output_path $PROJECT_PATH/environment_scan/sparse
conda activate gaussian_splatting
ulimit -n 4096
python3 $REPO_PATH/gaussian-splatting/train.py \\
    -s $PROJECT_PATH/environment_scan \\
    -m $PROJECT_PATH/gaussian_splatting_reconstruction \\
    --test_iterations -1 \\
    --data_device {data_device} \\
    --resolution 4
python3 $REPO_PATH/src_server/read_frame_registration_in_gs.py -s $PROJECT_PATH
python3 $REPO_PATH/src_server/extract_frames_for_frontend.py -s $PROJECT_PATH
conda deactivate
unset PROJECT_PATH
unset REPO_PATH
unset COLMAP_PATH
'''
    with open(os.path.join(output_folder, 'perform_3D_registration_and_reconstruction.sh'), 'w') as file:
        file.write(shell_script)


def generate_render_shell_script(project_path, render_json_path, repo_path, output_folder, final_video_name):
    project_path = remove_slash(project_path)
    render_json_path = remove_slash(render_json_path)
    repo_path = remove_slash(repo_path)
    shell_script=f'''
PROJECT_PATH={project_path}

REPO_PATH={repo_path}

RENDER_JSON_PATH={render_json_path}

eval "$(conda shell.bash hook)"
conda activate gaussian_splatting
python3 $REPO_PATH/gaussian-splatting/render_from_camera_file.py \\
    -m $PROJECT_PATH/gaussian_splatting_reconstruction \\
    -f $RENDER_JSON_PATH
python3 $REPO_PATH/src_server/render_final_video.py \\
    -s $PROJECT_PATH \\
    -f {final_video_name}
conda deactivate
unset PROJECT_PATH
unset RENDER_JSON_PATH
unset REPO_PATH
'''
    with open(os.path.join(output_folder, 'render_with_pre-visualization_reconstruction.sh'), 'w+') as file:
        file.write(shell_script)


def generate_render_with_extra_frames_shell_script(project_path, output_video_name, repo_path, colmap_path, included_video_names, data_device, output_folder):
    project_path = remove_slash(project_path)
    repo_path = remove_slash(repo_path)
    included_video_str = str(included_video_names)[1:-1].replace('\'', '').replace(' ','')
    shell_script=f'''
COLMAP_PATH={colmap_path}

PROJECT_PATH={project_path}

REPO_PATH={repo_path}

OUTPUT_VIDEO_NAME={output_video_name}

eval "$(conda shell.bash hook)"
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0
cp -r $PROJECT_PATH/environment_scan/sparse/0 $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/without_extra_frames
cp -r $PROJECT_PATH/environment_scan/images/ $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/images
cp $PROJECT_PATH/environment_scan/database.db $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db
conda activate gaussian_splatting
python3 $REPO_PATH/src_server/extract_selected_tbc_video_frames.py \\
    -s $PROJECT_PATH \\
    -v {included_video_str} \\
    -o $OUTPUT_VIDEO_NAME
conda deactivate
$COLMAP_PATH feature_extractor \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --image_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/images \\
    --ImageReader.single_camera 1 \\
    --ImageReader.existing_camera_id 1
$COLMAP_PATH matches_importer \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --match_list_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/extracted_frames_match_list.txt
$COLMAP_PATH image_registrator \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --input_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/without_extra_frames/ \\
    --output_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0
conda activate gaussian_splatting
ulimit -n 4096
python3 $REPO_PATH/gaussian-splatting/train.py \\
    -s $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames \\
    -m $PROJECT_PATH/$OUTPUT_VIDEO_NAME/high_quality_reconstruction \\
    --data_device {data_device} \\
    --test_iterations -1
python3 $REPO_PATH/gaussian-splatting/render_from_camera_file.py \\
    -m $PROJECT_PATH/$OUTPUT_VIDEO_NAME/high_quality_reconstruction \\
    -f $PROJECT_PATH/$OUTPUT_VIDEO_NAME/concatenate_frames.json
python3 $REPO_PATH/src_server/render_final_video.py \\
    -s $PROJECT_PATH \\
    -f $OUTPUT_VIDEO_NAME
conda deactivate
unset COLMAP_PATH
unset PROJECT_PATH
unset REPO_PATH
unset OUTPUT_VIDEO_NAME
'''
    with open(os.path.join(output_folder, 'render_with_extra_frames_along_final_trajectory.sh'), 'w+') as file:
        file.write(shell_script)


        shell_script_remove_irrelevant_frame=f'''
COLMAP_PATH={colmap_path}

PROJECT_PATH={project_path}

REPO_PATH={repo_path}

OUTPUT_VIDEO_NAME={output_video_name}

eval "$(conda shell.bash hook)"
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0
cp -r $PROJECT_PATH/environment_scan/sparse/0 $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/without_extra_frames
cp -r $PROJECT_PATH/environment_scan/images/ $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/images
cp $PROJECT_PATH/environment_scan/database.db $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db
conda activate gaussian_splatting
python3 $REPO_PATH/src_server/extract_selected_tbc_video_frames.py \\
    -s $PROJECT_PATH \\
    -v {included_video_str} \\
    -o $OUTPUT_VIDEO_NAME
conda deactivate
$COLMAP_PATH feature_extractor \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --image_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/images \\
    --ImageReader.single_camera 1 \\
    --ImageReader.existing_camera_id 1
$COLMAP_PATH matches_importer \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --match_list_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/extracted_frames_match_list.txt
$COLMAP_PATH image_registrator \\
    --database_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/database.db \\
    --input_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/without_extra_frames/ \\
    --output_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0
mv $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0 $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/with_irrelevant_frames
mkdir $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0
$COLMAP_PATH image_deleter \\
    --input_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/with_irrelevant_frames \\
    --output_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/sparse/0 \\
    --image_names_path $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames/irrelevant_frames.txt
conda activate gaussian_splatting
ulimit -n 4096
python3 $REPO_PATH/gaussian-splatting/train.py \\
    -s $PROJECT_PATH/$OUTPUT_VIDEO_NAME/registration_with_extra_frames \\
    -m $PROJECT_PATH/$OUTPUT_VIDEO_NAME/high_quality_reconstruction \\
    --data_device {data_device} \\
    --test_iterations -1
python3 $REPO_PATH/gaussian-splatting/render_from_camera_file.py \\
    -m $PROJECT_PATH/$OUTPUT_VIDEO_NAME/high_quality_reconstruction \\
    -f $PROJECT_PATH/$OUTPUT_VIDEO_NAME/concatenate_frames.json
python3 $REPO_PATH/src_server/render_final_video.py \\
    -s $PROJECT_PATH \\
    -f $OUTPUT_VIDEO_NAME
conda deactivate
unset COLMAP_PATH
unset PROJECT_PATH
unset REPO_PATH
unset OUTPUT_VIDEO_NAME
'''
        
    with open(os.path.join(output_folder, 'render_with_extra_frames_along_final_trajectory_no_irrelevant_frames.sh'), 'w+') as file:
        file.write(shell_script_remove_irrelevant_frame)


def generate_initial_concatenate_config_by_order(to_be_concatenated_video_info, tbc_stabilizers, concatenate_order, up_vec, final_video_fps):
    '''
    to_be_concatenated_video_info: output dict in to_be_concatenated_video_info.json
    tbc_stabilizers: dict with keys=tbc video name, values=Stabilizer
    concatenate_order: list of to-be-concatenated video names
    '''
    concatenate_config = {}
    concatenate_config['cam_intrinsic_params'] = to_be_concatenated_video_info['cam_intrinsic_params']
    concatenate_config['up_vec'] = up_vec
    concatenate_config['concatenate_dicts'] = []
    for concatenate_clip_i in range(len(concatenate_order)-1):
        last_video_file_name = concatenate_order[concatenate_clip_i]
        if not tbc_stabilizers.get(last_video_file_name) is None:
            last_video_is_stabilized = True
            last_video_stabilizer = tbc_stabilizers.get(last_video_file_name)
            last_video_frame_pos, last_video_frame_rot, last_video_frame_ts, _, _, _ = last_video_stabilizer.get_stabilization_result()
            last_video_num_frame = len(last_video_frame_pos)
            if last_video_num_frame >= 7:
                num_relevant_frames = 7 
            elif last_video_num_frame >= 5:
                num_relevant_frames = 5
            else:
                num_relevant_frames = 3
            last_video_frame_indexes = [last_video_num_frame-i-1 for i in range(num_relevant_frames)]
            last_video_frame_pos = last_video_frame_pos[-num_relevant_frames:]
            last_video_frame_rot_mat = last_video_frame_rot[-num_relevant_frames:]
            last_video_frame_rot = []
            for rot_mat in last_video_frame_rot_mat:
                last_video_frame_rot.append(Rotation.from_matrix(np.array(rot_mat)).as_euler(rotation_order).tolist())
            last_video_frame_ts = last_video_frame_ts[-num_relevant_frames:]
            last_video_avg_velocity = last_video_stabilizer.get_avg_velocity()
        else:
            last_video_is_stabilized = False
            last_video_info = to_be_concatenated_video_info[last_video_file_name]
            frame_names = last_video_info['frame_names']
            start_i, end_i = last_video_info['end_considered_range']

            considered_frame_names = frame_names[start_i:end_i]
            last_video_frame_pos = last_video_info['frame_pos'][start_i:end_i]
            last_video_frame_rot = last_video_info['frame_rot'][start_i:end_i]
            last_video_frame_ts = last_video_info['frame_ts'][start_i:end_i]
            last_video_frame_indexes = [frame_index_of(frame_name) for frame_name in considered_frame_names]
            last_video_frame_pos_np = np.array(last_video_frame_pos)
            last_video_avg_velocity = np.mean(np.linalg.norm(last_video_frame_pos_np[1:] - last_video_frame_pos_np[:-1], axis=1) * final_video_fps)


        next_video_file_name = concatenate_order[concatenate_clip_i+1]
        if not tbc_stabilizers.get(next_video_file_name) is None:
            next_video_is_stabilized = True
            next_video_stabilizer = tbc_stabilizers.get(next_video_file_name)
            next_video_frame_pos, next_video_frame_rot, next_video_frame_ts, _, _, _ = next_video_stabilizer.get_stabilization_result()
            next_video_num_frame = len(next_video_frame_ts)
            if next_video_num_frame >= 7:
                num_relevant_frames = 7 
            elif next_video_num_frame >= 5:
                num_relevant_frames = 5
            else:
                num_relevant_frames = 3
            next_video_frame_indexes = [i for i in range(num_relevant_frames)]
            next_video_frame_pos = next_video_frame_pos[0:num_relevant_frames]
            next_video_frame_rot_mat = next_video_frame_rot[0:num_relevant_frames]
            next_video_frame_rot = []
            for rot_mat in next_video_frame_rot_mat:
                next_video_frame_rot.append(Rotation.from_matrix(np.array(rot_mat)).as_euler(rotation_order).tolist())
            next_video_frame_ts = next_video_frame_ts[0:num_relevant_frames]
            next_video_avg_velocity = next_video_stabilizer.get_avg_velocity()
        else:
            next_video_is_stabilized = False
            next_video_info = to_be_concatenated_video_info[next_video_file_name]
            frame_names = next_video_info['frame_names']
            start_i, end_i = next_video_info['start_considered_range']

            considered_frame_names = frame_names[start_i:end_i]
            next_video_frame_pos = next_video_info['frame_pos'][start_i:end_i]
            next_video_frame_rot = next_video_info['frame_rot'][start_i:end_i]
            next_video_frame_ts = next_video_info['frame_ts'][start_i:end_i]
            next_video_frame_indexes = [frame_index_of(frame_name) for frame_name in considered_frame_names]
            next_video_frame_pos_np = np.array(next_video_frame_pos)
            next_video_avg_velocity = np.mean(np.linalg.norm(next_video_frame_pos_np[1:] - next_video_frame_pos_np[:-1], axis=1) * final_video_fps)

        cur_concatenate_dict = {'last_video_file_name': last_video_file_name, 'last_video_frame_indexes': last_video_frame_indexes, 'last_video_is_stabilized': last_video_is_stabilized, 'last_video_frame_ts': last_video_frame_ts, 'last_video_frame_pos': last_video_frame_pos, 'last_video_frame_rot': last_video_frame_rot, 'last_video_avg_velocity': last_video_avg_velocity, 'next_video_file_name': next_video_file_name, 'next_video_frame_indexes': next_video_frame_indexes, 'next_video_is_stabilized': next_video_is_stabilized, 'next_video_frame_ts': next_video_frame_ts, 'next_video_frame_pos': next_video_frame_pos, 'next_video_frame_rot': next_video_frame_rot, 'next_video_avg_velocity': next_video_avg_velocity}
        concatenate_config['concatenate_dicts'].append(cur_concatenate_dict)
    
    return concatenate_config


def get_continuously_extracted_frames(frame_names, start_or_end, max_num_frame):
    if start_or_end == 'start':
        start_frame_name_i = 0
        last_frame_index = frame_index_of(frame_names[start_frame_name_i])
        cur_frame_name_i = start_frame_name_i + 1
        while True:
            cur_frame_index = frame_index_of(frame_names[cur_frame_name_i])
            if cur_frame_index - last_frame_index > 1 or cur_frame_name_i-start_frame_name_i >= max_num_frame or cur_frame_name_i==len(frame_names)-1:
                break
            last_frame_index = cur_frame_index
            cur_frame_name_i += 1
        return start_frame_name_i, cur_frame_name_i
    elif start_or_end == 'end':
        start_frame_name_i = len(frame_names) - 1
        next_frame_index = frame_index_of(frame_names[start_frame_name_i])
        cur_frame_name_i = start_frame_name_i - 1
        while True:
            cur_frame_index = frame_index_of(frame_names[cur_frame_name_i])
            if next_frame_index - cur_frame_index > 1 or start_frame_name_i-cur_frame_name_i >= max_num_frame or cur_frame_name_i==0:
                break
            next_frame_index = cur_frame_index
            cur_frame_name_i -= 1
        return cur_frame_name_i+1, start_frame_name_i+1
    



def get_non_nan_chunk_from_list(input_list, num_continuous_non_nan, start_or_end):
    is_nan_list = np.isnan(input_list)
    nan_i = [i for i,x in enumerate(is_nan_list) if x]
    if len(nan_i)>0:
        if start_or_end == 'start':
            max_range_size = 0
            cur_start_i = 0
            cur_end_i = nan_i[0]
            start_i, end_i = (np.nan, np.nan)
            for cur_start_i_in_nan_list in range(len(nan_i)):
                if len(input_list[cur_start_i:cur_end_i]) > max_range_size:
                    start_i, end_i = (cur_start_i, cur_end_i)
                    max_range_size = len(input_list[cur_start_i:cur_end_i])
                if max_range_size >= num_continuous_non_nan:
                    return start_i, end_i 
                cur_start_i = nan_i[cur_start_i_in_nan_list] + 1
                if cur_start_i_in_nan_list == len(nan_i)-1:
                    cur_end_i = len(input_list)
                else:
                    cur_end_i = nan_i[cur_start_i_in_nan_list+1]
            if len(input_list[cur_start_i:cur_end_i]) > max_range_size:
                start_i, end_i = (cur_start_i, cur_end_i)
        elif start_or_end == 'end':
            max_range_size = 0
            cur_start_i = nan_i[-1] + 1
            cur_end_i = len(input_list)
            start_i, end_i = (np.nan, np.nan)
            for cur_end_i_in_nan_list in range(len(nan_i)):
                if len(input_list[cur_start_i:cur_end_i]) > max_range_size:
                    start_i, end_i = (cur_start_i, cur_end_i)
                    max_range_size = len(input_list[cur_start_i:cur_end_i])
                if max_range_size >= num_continuous_non_nan:
                    return start_i, end_i 
                cur_end_i = nan_i[-cur_end_i_in_nan_list-1]
                if cur_end_i_in_nan_list == len(nan_i)-1:
                    cur_start_i = 0
                else:
                    cur_start_i = nan_i[-cur_end_i_in_nan_list-2]+1
            if len(input_list[cur_start_i:cur_end_i]) > max_range_size:
                start_i, end_i = (cur_start_i, cur_end_i)
        return start_i, end_i
    else:
        return 0, len(input_list)
    

def sample_points(pos, rot, ts, start_percent, end_percent, sampling_interval):
    # Copy inputs
    pos_copy = np.copy(pos)
    rot_copy = np.copy(rot)
    ts_copy = np.copy(ts)

    # Calculate selected range
    start_ts = start_percent * ts_copy[-1]
    end_ts = end_percent * ts_copy[-1]
    sampling_interval = ts_copy[-1] * sampling_interval

    # Remove NaN
    included_idx = ~np.isnan(pos_copy[:,0])
    pos_copy = pos_copy[included_idx, :]
    rot_copy = rot_copy[included_idx, :]
    ts_copy = ts_copy[included_idx]

    # Remove the trimmed out part
    start_i = np.argmin(np.abs(ts_copy-start_ts))
    end_i = np.argmin(np.abs(ts_copy-end_ts))
    pos_copy = pos_copy[start_i:end_i+1, :]
    rot_copy = rot_copy[start_i:end_i+1, :]
    ts_copy = ts_copy[start_i:end_i+1]
    ts_copy = ts_copy - ts_copy[0]

    # Sample according sampling_interval
    sampled_i = []
    for sampled_frame_i in range(np.size(ts_copy)-1):
        cur_ts = ts_copy[sampled_frame_i]
        next_ts = ts_copy[sampled_frame_i+1]

        # Fill the first one
        if len(sampled_i)==0:
            sampled_i.append(sampled_frame_i)
            continue

        # Reach next sample or skipping this make sampling interval too large
        if np.isclose(cur_ts-ts_copy[sampled_i[-1]], sampling_interval) or \
                (next_ts-ts_copy[sampled_i[-1]] > sampling_interval*1.2):
            sampled_i.append(sampled_frame_i)
    sampled_i.append(np.size(ts_copy)-1)
    sampled_i = np.array(sampled_i)

    pos_copy = pos_copy[sampled_i]
    rot_copy = rot_copy[sampled_i]
    ts_copy = ts_copy[sampled_i]

    return pos_copy, rot_copy, ts_copy


def get_frame_name(prefix, video_name, frame_index, file_extension):
    if prefix is None or len(prefix)==0:
        return video_name[::-1].split('.', 1)[-1][::-1]+ '_' + f'{frame_index:08d}' + "." + file_extension
    else:
        return prefix + '_' + video_name[::-1].split('.', 1)[-1][::-1] + '_' + f'{frame_index:08d}' + "." + file_extension


def get_relevant_range(start_considered_range, end_considered_range):
    start_i_start, end_i_start = start_considered_range
    start_i_end, end_i_end = end_considered_range
    if start_i_start is np.nan and start_i_end is np.nan:
        return (np.nan, np.nan)
    elif start_i_start is np.nan:
        return (start_i_end, end_i_end)
    elif start_i_end is np.nan:
        return (start_i_start, end_i_start)
    else:
        return (start_i_start, end_i_end)


# print(get_non_nan_chunk_from_list([np.nan, 1,2,3,4, np.nan, np.nan, 4,5,np.nan,6,7,8, 10], 3, 'end'))
# print(get_frame_name('rendered', '1.mp4', 39, 'png'))