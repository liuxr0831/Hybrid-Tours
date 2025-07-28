import numpy as np
from scipy.optimize import fsolve as solve

from bezier_curve import d_bezier_coeff, dd_bezier_coeff, bezier_arc_length, t

# Helper function to calculate default control points of the path
def calc_default_path_and_velocity(concatenate_dict, time_between_frames):
    last_video_pos = np.array(concatenate_dict['last_video_frame_pos'])
    next_video_pos = np.array(concatenate_dict['next_video_frame_pos'])
    last_video_ts = concatenate_dict['last_video_frame_ts']
    next_video_ts = concatenate_dict['next_video_frame_ts']
    first_order_d_scale = 0.5
    second_order_d_scale = 0.03


    # naive strategy by just considering last ones
    if len(concatenate_dict['last_video_frame_pos']) >= 7:
        last_i, second_last_i, third_last_i = (-1,-4,-7)
    elif len(concatenate_dict['last_video_frame_pos']) >= 5:
        last_i, second_last_i, third_last_i = (-1,-3,-5)
    else:
        last_i, second_last_i, third_last_i = (-1,-2,-3)
    if len(concatenate_dict['next_video_frame_pos']) >= 7:
        first_i, second_i, third_i = (0,3,6)
    elif len(concatenate_dict['next_video_frame_pos']) >= 5:
        first_i, second_i, third_i = (0,2,4)
    else:
        first_i, second_i, third_i = (0,1,2)

    if any(np.isnan([last_i, second_last_i, third_last_i, first_i, second_i, third_i])):
        return None, None, None, None, None

    last_first_order_d = last_video_pos[last_i,:] - last_video_pos[second_last_i,:]
    if np.all(np.isclose(last_first_order_d, 0)):
        last_first_order_d = next_video_pos[first_i,:] - last_video_pos[last_i,:]
        last_velocity = 0
    else:
        last_velocity = np.linalg.norm(np.linalg.norm(last_first_order_d)/(last_video_ts[last_i] - last_video_ts[second_last_i]))
    last_first_order_d_direction = last_first_order_d / np.linalg.norm(np.linalg.norm(last_first_order_d))
    last_first_order_d_second_last = last_video_pos[second_last_i,:] - last_video_pos[third_last_i,:]
    if np.all(np.isclose(last_first_order_d_second_last, 0)):
        last_first_order_d_second_last = next_video_pos[first_i,:] - last_video_pos[last_i,:]
    last_first_order_d_direction_second_last = last_first_order_d_second_last / np.linalg.norm(np.linalg.norm(last_first_order_d_second_last))
    last_second_order_d = last_first_order_d_direction - last_first_order_d_direction_second_last
    if np.all(np.isclose(last_second_order_d, 0)):
        last_second_order_d_direction = next_video_pos[first_i,:] - last_video_pos[last_i,:]
    last_second_order_d_direction = last_second_order_d / np.linalg.norm(np.linalg.norm(last_second_order_d))
    
    next_first_order_d = next_video_pos[second_i,:] - next_video_pos[first_i,:]
    if np.all(np.isclose(next_first_order_d, 0)):
        next_first_order_d = next_video_pos[first_i,:] - last_video_pos[last_i,:]
        next_velocity = 0
    else:
        next_velocity = np.linalg.norm(np.linalg.norm(next_first_order_d)/(next_video_ts[second_i] - next_video_ts[first_i]))
    next_first_order_d_direction = next_first_order_d / np.linalg.norm(np.linalg.norm(next_first_order_d))
    next_first_order_d_second = next_video_pos[third_i,:] - next_video_pos[second_i,:]
    if np.all(np.isclose(next_first_order_d_second, 0)):
        next_first_order_d_second = next_video_pos[first_i,:] - last_video_pos[last_i,:]
    next_first_order_d_direction_second_next = next_first_order_d_second / np.linalg.norm(np.linalg.norm(next_first_order_d_second))
    next_second_order_d = next_first_order_d_direction - next_first_order_d_direction_second_next
    if np.all(np.isclose(next_second_order_d, 0)):
        next_second_order_d = next_video_pos[first_i,:] - last_video_pos[last_i,:]
    next_second_order_d_direction = next_second_order_d / np.linalg.norm(np.linalg.norm(next_second_order_d))

    

    distance = np.linalg.norm(next_video_pos[first_i,:] - last_video_pos[last_i,:])
    path_control_points = fit_path(last_video_pos[last_i,:], last_first_order_d_direction * distance * first_order_d_scale, \
                                last_second_order_d_direction * distance * second_order_d_scale, next_video_pos[first_i,:], \
                                next_first_order_d_direction * distance * first_order_d_scale, \
                                next_second_order_d_direction * distance * second_order_d_scale, np.zeros((0,3)))



    # Calculate acceleration along the path
    path_total_length = 0
    path_lengths = []
    for control_points in path_control_points:
        cur_path_length = bezier_arc_length(control_points, 0, 1)
        path_total_length += cur_path_length
        path_lengths.append(cur_path_length)
    if np.isclose(last_velocity, 0) and np.isclose(next_velocity, 0):
        middle_point_velocity = (concatenate_dict['last_video_avg_velocity'] + concatenate_dict['next_video_avg_velocity']) / 2
        if np.isclose(middle_point_velocity, 0):
            middle_point_velocity = distance / 2
        last_v_1, accel_1, t_1 = fit_speed(last_velocity, middle_point_velocity, path_total_length/2, time_between_frames)
        last_v_2, accel_2, t_2 = fit_speed(middle_point_velocity, next_velocity, path_total_length/2, time_between_frames)
        return path_control_points, path_lengths, [last_v_1, last_v_2], [accel_1, accel_2], [t_1, t_2]
    else:
        last_velocity, accel_along_path, travel_time = fit_speed(last_velocity, next_velocity, path_total_length, time_between_frames)
        return path_control_points, path_lengths, [last_velocity], [accel_along_path], [travel_time]

def get_path_control_points_and_t(path_control_points, path_lengths, total_distance):
    if total_distance > np.sum(path_lengths):
        raise ValueError("Total distance traveled is longer than the length of the provided path.")
    
    for curve_i in range(len(path_lengths)):
        if total_distance <= path_lengths[curve_i]:
            return np.array(path_control_points[curve_i]), t(np.array(path_control_points[curve_i]), total_distance)[0]
        total_distance -= path_lengths[curve_i]

def get_distance(initial_velocities, accels_along_path, travel_times, total_time):
    if total_time > np.sum(travel_times):
        raise ValueError("Total time to travel along the path is longer than the sum of travel_times.")
    
    total_distance = 0
    for travel_time_i in range(len(travel_times)):
        cur_travel_time = travel_times[travel_time_i]
        if total_time < cur_travel_time:
            total_distance += initial_velocities[travel_time_i] * total_time + 1/2 * accels_along_path[travel_time_i] * total_time**2
            return total_distance
        total_distance += initial_velocities[travel_time_i] * cur_travel_time + 1/2 * accels_along_path[travel_time_i] * cur_travel_time**2
        total_time -= cur_travel_time

def fit_speed(last_velocity, next_velocity, path_total_length, time_between_frames):
    def speed_equation(x):
        '''
        x[0] accel, x[1] time
        '''
        return [last_velocity * x[1] + 1/2 * x[0] * x[1]**2 - path_total_length, last_velocity + x[0] * x[1] - next_velocity]
    
    accel_along_path, travel_time = solve(speed_equation, [1,1])

    # Adjust travel_time and accel_along_path to stay consistent with frame rates
    travel_time = np.round(travel_time/time_between_frames)*time_between_frames
    accel_along_path = 2 * (path_total_length - last_velocity * travel_time) / travel_time**2

    return last_velocity, accel_along_path, travel_time

def fit_path(initial_pos, initial_first_order_d, initial_second_order_d, final_pos, final_first_order_d, final_second_order_d, intermediate_pos):
    '''
    Fit a C2 continuous bezier path through the initial_pos, all the intermediate_pos, and the final_pos.
    This path makes sure that the 
    The curve's first order derivative and second order derivatieve at initial_pos is given by initial_first_order_d and initial_second_order_d.
    The curve's first order derivative and second order derivatieve at final_pos is given by final_first_order_d and final_second_order_d.
    All parameters should be given as a N-by-num_dimension np array
    If no intermediate_pos needed, pass in a 0-by-num_dimension np array
    '''
    if len(initial_pos.shape) != 1 or len(initial_first_order_d.shape) != 1 or len(initial_second_order_d.shape) != 1 or len(final_pos.shape) != 1 \
        or len(final_first_order_d.shape) != 1 or len(final_second_order_d.shape) != 1 or len(intermediate_pos.shape) != 2:
        raise ValueError("Dimensions of input arrays not correct. initial_pos, initial_first_order_d, initial_second_order_d, final_pos, \
                         final_first_order_d, and final_second_order_d should all have only 1 dimension, and the size along this dimension should \
                         be the number of world dimensions (i.e. 3 for real world, 2 for a plane). intermediate_pos should have 2 dimensions: the \
                         size along the 0-th dimension should be the number of intermediate points; the size along the 1-th dimension should be the \
                         the number of world dimensions (i.e. 3 for real world, 2 for a plane).")

    num_dimension = np.size(intermediate_pos, 1)

    # One 5-th order bezier curve if no intermediate_pos defined
    if np.size(intermediate_pos, 0)==0:
        control_points_place_holder_6 = np.zeros((6,num_dimension))
        d_0 = d_bezier_coeff(control_points_place_holder_6, 0)
        dd_0 = dd_bezier_coeff(control_points_place_holder_6, 0)
        d_1 = d_bezier_coeff(control_points_place_holder_6, 1)
        dd_1 = dd_bezier_coeff(control_points_place_holder_6, 1)
        b = np.array([ initial_first_order_d - d_0[0] * initial_pos, initial_second_order_d - dd_0[0] * initial_pos, \
                       final_first_order_d - d_1[-1] * final_pos,    final_second_order_d - dd_1[-1] * final_pos, ])
        A = np.array([ d_0[1:-1], dd_0[1:-1], d_1[1:-1], dd_1[1:-1] ])
        middle_control_points = np.linalg.inv(A) @ b
        return [np.vstack((initial_pos, middle_control_points, final_pos))]
    
    # Two 4-th order bezier curve if only one intermediate_pos
    elif np.size(intermediate_pos, 0)==1:
        control_points_place_holder_5 = np.zeros((5,num_dimension))
        A = np.zeros((6,6))
        b = np.zeros((6, num_dimension))
        d_0 = d_bezier_coeff(control_points_place_holder_5, 0)
        dd_0 = dd_bezier_coeff(control_points_place_holder_5, 0)
        d_1 = d_bezier_coeff(control_points_place_holder_5, 1)
        dd_1 = dd_bezier_coeff(control_points_place_holder_5, 1)

        # initial
        A[0,0:4] = d_0[1:]
        b[0,:] = initial_first_order_d - d_0[0] * initial_pos
        A[1,0:4] = dd_0[1:]
        b[1,:] = initial_second_order_d - dd_0[0] * initial_pos

        # final
        A[4, -4:] = d_1[:-1]
        b[4,:] = final_first_order_d - d_1[-1] * final_pos
        A[5, -4:] = dd_1[:-1]
        b[5,:] = final_second_order_d - dd_1[-1] * final_pos

        # intermediate
        A[2, 2:4] = [1, 1]
        b[2,:] = 2*intermediate_pos[0,:]
        A[3, 1:5] = [1, -2, 2, -1]
        b[3,:] = [0] * num_dimension

        middle_control_points = np.linalg.inv(A) @ b

        return [np.vstack((initial_pos, middle_control_points[0:3,:], intermediate_pos[0,:])), \
                np.vstack((intermediate_pos[0,:], middle_control_points[3:,:], final_pos))]
    
    # One 4-th order bezier curve, num_intermediate_pos-1 3-rd order bezier curves, one 4-th order bezier curve if num_intermediate_pos > 1
    else:
        control_points_place_holder_5 = np.zeros((5,num_dimension))
        num_key_pos = np.size(intermediate_pos, 0) + 2
        num_curve = num_key_pos - 1
        A = np.zeros((2*num_key_pos, 2*num_key_pos))
        b = np.zeros((2*num_key_pos, num_dimension))
        for cur_curve_i in range(num_curve-1):
            # here, the index of curves start with 0

            # at cur_curve_i = 0, we set up initial condition and continuation with curve 1
            if cur_curve_i == 0:

                # initial condition
                d_0 = d_bezier_coeff(control_points_place_holder_5, 0)
                dd_0 = dd_bezier_coeff(control_points_place_holder_5, 0)
                A[0, 0:len(d_0)-1] = d_0[1:]
                b[0,:] = initial_first_order_d - d_0[0] * initial_pos
                A[1, 0:len(dd_0)-1] = dd_0[1:]
                b[1,:] = initial_second_order_d - dd_0[0] * initial_pos

                # continuation with curve 1
                A[2,2:4] = [4,3]
                b[2,:] = 7*intermediate_pos[0,:]
                A[3, 1:5] = [2, -4, 2, -1]
                b[3,:] = -intermediate_pos[0,:]


            # at cur_curve_i = num_curve-2, we set up continuation between curve num_curve-2 and num_curve-1
            # we also set up the final condition for curve num_curve-1
            elif cur_curve_i == num_curve-2:

                # continuation between num_curve-2 and num_curve-1
                A[-4, -5:] = [0, 3, 4, 0, 0]
                b[-4,:] = 7*intermediate_pos[-1,:]
                A[-3, -5:] = [1, -2, 4, -2, 0]
                b[-3,:] = intermediate_pos[-1,:]

                # final condition
                d_1 = d_bezier_coeff(control_points_place_holder_5, 1)
                dd_1 = dd_bezier_coeff(control_points_place_holder_5, 1)
                A[-2, -3:] = d_1[1:-1]
                b[-2,:] =  final_first_order_d - d_1[-1] * final_pos
                A[-1, -3:] = dd_1[1:-1]
                b[-1,:] =  final_second_order_d - dd_1[-1] * final_pos


            # at cur_curve_i = i where 0<i<num_curve-2, we set up continuation between curve i and curve i+1
            # for each curve, we have two continuation conditions, we also have two equations for initial condition, so 2*cur_curve_i + 2
            # for each curve, we have two unknown control points, but the first one has three, so 2*curve_i + 1
            else:
                A[2*cur_curve_i+2, 2*cur_curve_i+1:2*cur_curve_i+1+4] = [0, 1, 1, 0]
                b[2*cur_curve_i+2,:] = 2*intermediate_pos[cur_curve_i,:]
                A[2*cur_curve_i+2+1, 2*cur_curve_i+1:2*cur_curve_i+1+4] = [1,-2, 2, -1]
                b[2*cur_curve_i+2+1,:] = [0] * num_dimension

        middle_control_points = np.linalg.inv(A) @ b

        control_points = []
        for curve_i in range(num_curve):
            if curve_i == 0:
                control_points.append(np.vstack(((initial_pos, middle_control_points[0:3,:], intermediate_pos[0,:]))))
            elif curve_i == num_curve-1:
                control_points.append(np.vstack(((intermediate_pos[-1,:], middle_control_points[-3:,:], final_pos))))
            else:
                control_points.append(np.vstack((intermediate_pos[curve_i-1,:], middle_control_points[2*curve_i+1:2*curve_i+1+2], \
                                                     intermediate_pos[curve_i,:])))
                
        return control_points