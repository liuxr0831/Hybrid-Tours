import numpy as np
import quaternion
from scipy.spatial.transform import Rotation, Slerp

from bezier_curve import d_bezier, bezier_coeff
from fit_path_and_velocity import get_path_control_points_and_t, get_distance
from quaternion_operations import dot, rot_to_quat

# Z forward, Y down, X right
rotation_order = 'zxy'

# Default times
direct_path_time = 3.6
fade_in_time = 1.8
fade_out_time = 1.8

def calc_default_orientation_change(concatenate_dict, up_vec, time_between_frames):
    # Unpack input
    travel_times = concatenate_dict['travel_times']
    total_travel_time = np.sum(travel_times)
    last_video_frame_rot = np.array(concatenate_dict['last_video_frame_rot'])
    last_video_frame_ts = np.array(concatenate_dict['last_video_frame_ts'])
    next_video_frame_rot = np.array(concatenate_dict['next_video_frame_rot'])
    next_video_frame_ts = np.array(concatenate_dict['next_video_frame_ts'])


    # Calculate initial and final speed and accel
    if len(concatenate_dict['last_video_frame_ts']) >= 7:
        last_i, second_last_i, third_last_i = (-1,-4,-7)
    elif len(concatenate_dict['last_video_frame_ts']) >= 5:
        last_i, second_last_i, third_last_i = (-1,-3,-5)
    else:
        last_i, second_last_i, third_last_i = (-1,-2,-3)
    if len(concatenate_dict['last_video_frame_ts']) >= 7:
        first_i, second_i, third_i = (0,3,6)
    elif len(concatenate_dict['last_video_frame_ts']) >= 5:
        first_i, second_i, third_i = (0,2,4)
    else:
        first_i, second_i, third_i = (0,1,2)
    initial_rot = Rotation.from_euler(rotation_order, last_video_frame_rot[last_i, :])
    final_rot = Rotation.from_euler(rotation_order, next_video_frame_rot[first_i, :])
    initial_orientation_quat = rot_to_quat(initial_rot)
    initial_angular_velocity = get_angular_velocity(Rotation.from_euler(rotation_order, last_video_frame_rot[second_last_i, :]), initial_rot, last_video_frame_ts[second_last_i], last_video_frame_ts[last_i])
    second_last_angular_velocity = get_angular_velocity(Rotation.from_euler(rotation_order, last_video_frame_rot[third_last_i, :]), Rotation.from_euler(rotation_order, last_video_frame_rot[second_last_i, :]), last_video_frame_ts[third_last_i], last_video_frame_ts[second_last_i])
    initial_angular_accel = get_angular_accel(second_last_angular_velocity, initial_angular_velocity, last_video_frame_ts[second_last_i], last_video_frame_ts[last_i])
    final_orientation_quat = rot_to_quat(final_rot)
    final_angular_velocity = get_angular_velocity(final_rot, Rotation.from_euler(rotation_order, next_video_frame_rot[second_i, :]), next_video_frame_ts[first_i], next_video_frame_ts[second_i])
    second_angular_velocity = get_angular_velocity(Rotation.from_euler(rotation_order, next_video_frame_rot[second_i, :]), Rotation.from_euler(rotation_order, next_video_frame_rot[third_i, :]), next_video_frame_ts[second_i], next_video_frame_ts[third_i])
    final_angular_accel = get_angular_accel(final_angular_velocity, second_angular_velocity, next_video_frame_ts[first_i], next_video_frame_ts[second_i])


    # Time too long, do SLERP with start and end accommodating the two videos on two ends
    # This is NECESSARY because if we keep the camera's start and end orientation, angular
    # velocity, and angular acceleration constant and only change the travel time, we are
    # actually CHANGING THE PATH OF ROTATION. If the travel time is too long, and we just 
    # fit to last and next video, the rotation trajectory would be too violent
    if total_travel_time > direct_path_time:
        # Initialize fields
        orientation_control_points = []
        transition_refs = []
        transition_times = []
        

        # Construct scipy SLERP object and get angular velocity during SLERP
        slerp = Slerp(np.array([0, total_travel_time]), Rotation.concatenate([initial_rot, final_rot]))
        angular_velocity_during_slerp = get_angular_velocity(slerp(0), slerp(total_travel_time/3), 0, total_travel_time/3)

        # First segment to enter SLERP
        cur_orientation_control_points = get_rotation_path(initial_orientation_quat, initial_angular_velocity, initial_angular_accel, rot_to_quat(slerp(fade_in_time)), angular_velocity_during_slerp, np.array([0,0,0]), fade_in_time)
        orientation_control_points.append(cur_orientation_control_points)
        transition_refs.append('world')
        transition_times.append(fade_in_time)

        # Second segment do SLERP
        cur_orientation_control_points = get_rotation_path(rot_to_quat(slerp(fade_in_time)), angular_velocity_during_slerp, np.array([0,0,0]), rot_to_quat(slerp(total_travel_time-fade_out_time)), angular_velocity_during_slerp, np.array([0,0,0]), total_travel_time-fade_in_time-fade_out_time)
        orientation_control_points.append(cur_orientation_control_points)
        transition_refs.append('world')
        transition_times.append(total_travel_time-fade_in_time-fade_out_time)

        # Last segment to exit SLERP
        cur_orientation_control_points = get_rotation_path(rot_to_quat(slerp(total_travel_time-fade_out_time)), angular_velocity_during_slerp, np.array([0,0,0]), final_orientation_quat, final_angular_velocity, final_angular_accel, fade_out_time)
        orientation_control_points.append(cur_orientation_control_points)
        transition_refs.append('world')
        transition_times.append(fade_out_time)

        return orientation_control_points, transition_refs, transition_times

    # Very little time, direct transition world
    # Currently only this is used
    else:
        # Calculate final rotation control points
        rotation_control_points = get_rotation_path(initial_orientation_quat, initial_angular_velocity, initial_angular_accel, \
                                                    final_orientation_quat, final_angular_velocity, final_angular_accel, total_travel_time)
        return [rotation_control_points], ['world'], [total_travel_time]


def get_path_coord_zero_orientation_mat(path_tangent, up_vec):
    path_tangent = np.array(path_tangent) 
    path_tangent = path_tangent / np.linalg.norm(path_tangent)
    up_vec = np.array(up_vec) 
    up_vec = up_vec / np.linalg.norm(up_vec)

    if np.linalg.norm(path_tangent - up_vec) == 0:
        raise ValueError("The path tangent is at the same direction as the up vector.")

    pt_up_angle_rad = np.arccos( np.dot(path_tangent, up_vec) )
    return Rotation.align_vectors([path_tangent, up_vec], \
                                  [[0,0,1], Rotation.from_euler('x', pt_up_angle_rad).as_matrix() @ np.array([0,0,1]) ])[0].as_matrix()


def get_orientation_control_points_and_t(orientation_control_points, transition_refs, transition_times, total_time):
    if total_time > np.sum(transition_times):
        raise ValueError("The provided total time is larger than the sum of transition_times.")
    
    for transition_time_i in range(len(transition_times)):
        cur_transition_time = transition_times[transition_time_i]
        if total_time < cur_transition_time:
            return np.array(orientation_control_points[transition_time_i]), total_time/cur_transition_time, transition_refs[transition_time_i]
        total_time -= cur_transition_time

def get_orientation_mat_along_rotation_path(rotation_path, t):
    '''
    return a 3-by-3 np array
    from https://dl.acm.org/doi/pdf/10.1145/218380.218486
    '''
    basis = bezier_coeff(rotation_path, t)
    qt = rotation_path[0]
    for omega_i in range(1, len(rotation_path)):
        cur_cumulative_basis = np.sum(basis[omega_i:])
        qt = qt * np.exp(cur_cumulative_basis * rotation_path[omega_i])
    
    return Rotation.from_quat([qt.x, qt.y, qt.z, qt.w]).as_matrix()


def get_rotation_path(initial_quat, initial_angular_velocity, initial_angular_accel, final_quat, final_angular_velocity, final_angular_accel, travel_time):
    '''
    initial_quat and final_quat should be np.quaternion
    initial_angular_velocity and final_angular_velocity should be 3-element np array showing angular velocity in radians/sec
    initial_angular_accel and final_angular_accel should be 3-element np array showing angular velocity in radians/sec^2
    rotation path represented by 6 quaternions, which are q0, omega1, omega2, omega3, omega4, and omega5
    '''
    if dot(initial_quat, final_quat) < 0:
        final_quat = -final_quat

    omega_start = np.quaternion(0, *(initial_angular_velocity * travel_time))
    omega_end = np.quaternion(0, *(final_angular_velocity * travel_time))
    alpha_start = np.quaternion(0, *(initial_angular_accel * travel_time * travel_time))
    alpha_end = np.quaternion(0, *(final_angular_accel * travel_time * travel_time))
    q0 = initial_quat
    q5 = final_quat
    q1 = q0 * np.exp(omega_start/10)
    q4 = q5 * np.exp(omega_end/10).inverse()
    omega_1 = np.log(q0.inverse()*q1)
    omega_5 = np.log(q4.inverse()*q5)
    q2 = q1 * np.exp(alpha_start/40+omega_1)
    q3 = q4 * np.exp(q4.inverse()*q5*(omega_5 - alpha_end/40)*q5.inverse()*q4).inverse()
    
    omega_2 = np.log(q1.inverse() * q2)
    omega_3 = np.log(q2.inverse() * q3)
    omega_4 = np.log(q3.inverse() * q4)

    return np.array([q0, omega_1, omega_2, omega_3, omega_4, omega_5])


def get_angular_velocity(first_rot: Rotation, second_rot: Rotation, first_ts, second_ts):
    '''
    first_rot and second_rot should be scipy Rotation objects
    first_ts and second_ts should be double
    from https://mariogc.com/post/angular-velocity-quaternions/
    '''
    rot_mat = first_rot.inv().as_matrix() @ second_rot.as_matrix()
    rot_vec = Rotation.from_matrix(rot_mat).as_rotvec()
    return rot_vec / (second_ts - first_ts)


def get_angular_accel(first_angular_velocity, second_angular_velocity, first_ts, second_ts):
    return (second_angular_velocity-first_angular_velocity)/(second_ts-first_ts)