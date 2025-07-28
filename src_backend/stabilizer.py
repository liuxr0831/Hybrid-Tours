from scipy.spatial.transform import Rotation
import numpy as np
from scipy.interpolate import BSpline, CubicSpline
from bintrees import FastRBTree

from orientation_quaternion import rotation_order
from quaternion_operations import dot, quat_angular_dist, rot_to_quat
from concatenate_utils import sample_points


class Stabilizer:
    def __init__(self, pos, rot, ts, start_percent, end_percent, sampling_interval, local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y, frame_rate, dense_ts, dense_distances_of_timestamped_pos_from_start, dense_distances_of_timestamped_rot_from_start, simulation_rate_multiplier=2, velocity_smoothing_step_percent=0.02):
        '''
        pos: n-by-3 np array
        rot: n-by-3 euler angle given in rotation_order
        ts: timestamp of each row given in a 1D numpy array
        start_percent and end_percent: range selected by trimming
        sampling_interval: every percent of total video length one sample
        local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y: define relation between how much we step for stabilized video ts and how much we step for original video ts, 1D array
        frame_rate: frame rate of the stabilized video
        '''
        # Store input to potentially reuse current stabilization result
        self.selected_range = (start_percent, end_percent)
        self.sampling_interval = sampling_interval
        self.frame_rate = frame_rate

        # Get number of velocity smoothing points
        num_velocity_smoothing_points = int((end_percent-start_percent)/velocity_smoothing_step_percent)+1
        self.velocity_smoothing_points_percents = np.linspace(0,1,num=num_velocity_smoothing_points)

        pos, rot, ts = sample_points(pos, rot, ts, start_percent, end_percent, sampling_interval)

        if np.size(pos, 0) < 4:
            raise ValueError("The number of points provided is less than 4. There must be at least 4 points.")
        self.pos = pos
        self.ts = ts
        self.local_velocity_adjustment_curve_x, self.local_velocity_adjustment_curve_y = np.array(local_velocity_adjustment_curve_x), np.array(local_velocity_adjustment_curve_y)
        if (1/frame_rate) / self.ts[-1] < 0.003333:
            self.simulation_rate_multiplier = simulation_rate_multiplier
        else:
            self.simulation_rate_multiplier = int((1/frame_rate)/(self.ts[-1]*0.003333))


        # Interpolate the positions to get the stabilized path
        # Construct the clamped cubic (degree=3, order=4) B spline knots array
        num_points_to_interpolate = np.size(self.ts)
        knots = [x/(num_points_to_interpolate-1) for x in range(num_points_to_interpolate-1)]
        knots[1] = 0.0
        knots[-1] = 1.0
        knots = [0.0,0.0] + knots + [1.0,1.0,1.0]
        # Then construct the B-spline representing the path
        self.path_bspline = BSpline(knots, self.pos, 3)

        # Calculate the stabilized speed along the path
        # Figure out the t and distance that corresponds to each sampled position
        t_corresponding_to_pos = [0.0]
        num_points_to_calculate_on_searched_seg = 32
        num_search_iteration = 2
        for pos_i in range(1, np.size(self.pos, 0)-1):
            cur_pos = self.pos[pos_i, :]
            search_seg_start = pos_i/(num_points_to_interpolate-1) - 0.5/(num_points_to_interpolate-1)
            search_seg_end = pos_i/(num_points_to_interpolate-1) + 0.5/(num_points_to_interpolate-1)
            for search_iter_i in range(num_search_iteration):
                t_of_points_to_consider = [search_seg_start + \
                                           (search_seg_end-search_seg_start) * point_i / num_points_to_calculate_on_searched_seg \
                                           for point_i in range(num_points_to_calculate_on_searched_seg+1)]
                index_of_min_distance_t = np.argmin(np.linalg.norm(cur_pos - self.path_bspline(t_of_points_to_consider), axis=1))
                min_distance_t = t_of_points_to_consider[index_of_min_distance_t]
                search_seg_start = t_of_points_to_consider[max((index_of_min_distance_t-1, 0))]
                search_seg_end = t_of_points_to_consider[min((index_of_min_distance_t+1, len(t_of_points_to_consider)-1))]
            t_corresponding_to_pos.append(min_distance_t)
        t_corresponding_to_pos.append(1.0)
            
        # Calculate the distance on spline between each consecutive pair of t's
        self.path_dist_lookup_by_dist_along_path_tree = FastRBTree()
        self.path_dist_lookup_by_t_dict = dict()
        distances_of_timestamped_pos_from_start = [0.0]
        for pos_i in range(np.size(self.pos, 0)-1):
            distances_of_timestamped_pos_from_start.append(\
                distances_of_timestamped_pos_from_start[-1]\
                      + self.__bspline_arc_length(t_corresponding_to_pos[pos_i], t_corresponding_to_pos[pos_i+1],\
                                                  is_update_distance_lookup_tree=True, \
                                                  t_start_distance=distances_of_timestamped_pos_from_start[-1]))
        
        # Use dense mapping to construct interpolation points
        to_be_interpolated_ts = []
        to_be_interpolated_distance = []
        for sampled_ts_i in range(1, len(self.ts)):
            last_ts_in_dense_index = np.argmin(np.abs(dense_ts-self.ts[sampled_ts_i-1]))
            cur_ts_in_dense_index = np.argmin(np.abs(dense_ts-self.ts[sampled_ts_i]))
            dense_version_cur_part_distance = dense_distances_of_timestamped_pos_from_start[cur_ts_in_dense_index] - dense_distances_of_timestamped_pos_from_start[last_ts_in_dense_index]
            for dense_ts_i in range(last_ts_in_dense_index, cur_ts_in_dense_index):
                to_be_interpolated_ts.append(dense_ts[dense_ts_i])
                cur_part_total_length = distances_of_timestamped_pos_from_start[sampled_ts_i] - distances_of_timestamped_pos_from_start[sampled_ts_i-1]
                cur_point_in_dense_distance = dense_distances_of_timestamped_pos_from_start[dense_ts_i] - dense_distances_of_timestamped_pos_from_start[last_ts_in_dense_index]
                cur_point_percent = cur_point_in_dense_distance/dense_version_cur_part_distance
                to_be_interpolated_distance.append(cur_point_percent*cur_part_total_length+distances_of_timestamped_pos_from_start[sampled_ts_i-1])
        last_dist = to_be_interpolated_distance[-1] + (self.ts[-1] - dense_ts[-2]) * (to_be_interpolated_distance[-1]-to_be_interpolated_distance[-2]) / (dense_ts[-2]-dense_ts[-3])
        to_be_interpolated_ts.append(self.ts[-1])
        to_be_interpolated_distance.append(last_dist)
        self.path_total_length = distances_of_timestamped_pos_from_start[-1]
        to_be_interpolated_distance = (np.array(to_be_interpolated_distance) / np.max(to_be_interpolated_distance) * self.path_total_length).tolist()


        # Use CubicSpline to interpolate the distance for all timestamps
        self.progress_along_path_spline = CubicSpline(to_be_interpolated_ts, to_be_interpolated_distance)
        self.path_dist_lookup_by_dist_along_path_tree.set_default(0.0, (0.0, self.pos[0,:]))
        self.path_dist_lookup_by_dist_along_path_tree.set_default(self.path_total_length, (1.0, self.pos[-1,:]))
        self.path_dist_lookup_by_t_dict[0.0] = (0.0, self.pos[0,:])
        self.path_dist_lookup_by_t_dict[1.0] = (self.path_total_length, self.pos[-1,:])



        # Calculate the stabilized orientation
        # Prepare the cumulative basis b spline, refer to http://graphics.cs.cmu.edu/nsp/course/15-464/Fall05/papers/kimKimShin.pdf
        # for more detail
        points_for_b_spline_cumulative_basis = np.tril(np.ones((np.size(self.pos, 0), np.size(self.pos, 0))))
        self.cumulative_basis_bspline = BSpline(knots, points_for_b_spline_cumulative_basis, 3)
        
        # Get the quaternions used to form the B-spline. Here, we make sure they are represented in a way such that each pair of
        # the quaternions are along the shortest arc
        self.omegas_for_bspline = [rot_to_quat(Rotation.from_euler(rotation_order, rot[0, :]))]
        self.interpolated_rot_quats = [rot_to_quat(Rotation.from_euler(rotation_order, rot[0, :]))]
        for rot_i in range(1, np.size(rot, 0)):
            cur_quat = rot_to_quat(Rotation.from_euler(rotation_order, rot[rot_i, :]))
            if dot(cur_quat, self.interpolated_rot_quats[-1]) < 0:
                cur_quat = -cur_quat
            self.omegas_for_bspline.append(np.log(self.interpolated_rot_quats[-1].inverse() * cur_quat))
            self.interpolated_rot_quats.append(cur_quat)

        # Figure out the t and distance that corresponds to each sampled orientation
        t_corresponding_to_rot = [0.0]
        num_points_to_calculate_on_searched_seg = 32
        num_search_iteration = 2
        for rot_i in range(1, len(self.interpolated_rot_quats)-1):
            
            cur_rot_quat = self.interpolated_rot_quats[rot_i]
            search_seg_start = rot_i/(num_points_to_interpolate-1) - 0.5/(num_points_to_interpolate-1)
            search_seg_end = rot_i/(num_points_to_interpolate-1) + 0.5/(num_points_to_interpolate-1)
            for search_iter_i in range(num_search_iteration):
                t_of_points_to_consider = [search_seg_start + \
                                           (search_seg_end-search_seg_start) * point_i / num_points_to_calculate_on_searched_seg \
                                           for point_i in range(num_points_to_calculate_on_searched_seg+1)]
                angular_distance_of_points = []
                for quat_curve_t in t_of_points_to_consider:
                    quat_at_cur_t = self.__quat_along_rot_bspline(quat_curve_t)
                    angular_distance_of_points.append(quat_angular_dist(quat_at_cur_t, cur_rot_quat))
                index_of_min_distance_t = np.argmin(angular_distance_of_points)
                min_distance_t = t_of_points_to_consider[index_of_min_distance_t]
                search_seg_start = t_of_points_to_consider[max((index_of_min_distance_t-1, 0))]
                search_seg_end = t_of_points_to_consider[min((index_of_min_distance_t+1, len(t_of_points_to_consider)-1))]
            t_corresponding_to_rot.append(min_distance_t)
        t_corresponding_to_rot.append(1.0)
            
        # Calculate the distance on spline between each consecutive pair of t's
        self.rot_angular_dist_lookup_by_dist_along_rot_path_tree = FastRBTree()
        self.rot_angular_dist_lookup_by_t_dict = dict()
        distances_of_timestamped_rot_from_start = [0.0]
        for rot_i in range(len(self.interpolated_rot_quats)-1):
            distances_of_timestamped_rot_from_start.append(\
                distances_of_timestamped_rot_from_start[-1]\
                      + self.__quat_bspline_arc_length(t_corresponding_to_rot[rot_i], t_corresponding_to_rot[rot_i+1],\
                                                       is_update_distance_lookup_tree=True,\
                                                       t_start_distance=distances_of_timestamped_rot_from_start[-1]))
        
        # Use dense mapping to construct interpolation points
        to_be_interpolated_ts = []
        to_be_interpolated_angular_distance = []
        for sampled_ts_i in range(1, len(self.ts)):
            last_ts_in_dense_index = np.argmin(np.abs(dense_ts-self.ts[sampled_ts_i-1]))
            cur_ts_in_dense_index = np.argmin(np.abs(dense_ts-self.ts[sampled_ts_i]))
            dense_version_cur_part_distance = dense_distances_of_timestamped_rot_from_start[cur_ts_in_dense_index] - dense_distances_of_timestamped_rot_from_start[last_ts_in_dense_index]
            for dense_ts_i in range(last_ts_in_dense_index, cur_ts_in_dense_index):
                to_be_interpolated_ts.append(dense_ts[dense_ts_i])
                cur_part_total_length = distances_of_timestamped_rot_from_start[sampled_ts_i] - distances_of_timestamped_rot_from_start[sampled_ts_i-1]
                cur_point_in_dense_distance = dense_distances_of_timestamped_rot_from_start[dense_ts_i] - dense_distances_of_timestamped_rot_from_start[last_ts_in_dense_index]
                cur_point_percent = cur_point_in_dense_distance/dense_version_cur_part_distance
                to_be_interpolated_angular_distance.append(cur_point_percent*cur_part_total_length+distances_of_timestamped_rot_from_start[sampled_ts_i-1])
        last_dist = to_be_interpolated_angular_distance[-1] + (self.ts[-1] - dense_ts[-2]) * (to_be_interpolated_angular_distance[-1]-to_be_interpolated_angular_distance[-2]) / (dense_ts[-2]-dense_ts[-3])
        to_be_interpolated_ts.append(self.ts[-1])
        to_be_interpolated_angular_distance.append(last_dist)
        self.rot_path_total_angular_distance = distances_of_timestamped_rot_from_start[-1]
        to_be_interpolated_angular_distance = np.array(to_be_interpolated_angular_distance) / np.max(to_be_interpolated_angular_distance) * self.rot_path_total_angular_distance

        # print(to_be_interpolated_ts)
        # print(to_be_interpolated_distance)
        # print(to_be_interpolated_angular_distance)


        # Use CubicSpline to interpolate the distance for all timestamps
        self.progress_along_rot_curve_spline = CubicSpline(to_be_interpolated_ts, to_be_interpolated_angular_distance)
        self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.set_default(0.0, (0.0, self.interpolated_rot_quats[0]))
        self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.set_default(self.rot_path_total_angular_distance, (1.0, self.interpolated_rot_quats[-1]))
        self.rot_angular_dist_lookup_by_t_dict[0.0] = (0.0, self.interpolated_rot_quats[0])
        self.rot_angular_dist_lookup_by_t_dict[1.0] = (self.rot_path_total_angular_distance, self.interpolated_rot_quats[-1])

        # Calculate the final results
        self.prev_distance_along_path = -1
        self.prev_distance_along_rotation_path = -1
        self.calculate_pos_and_rot()
        

    def get_avg_velocity(self):
        return self.path_total_length / self.ts[-1]


    def get_stabilization_params(self):
        return self.selected_range, self.sampling_interval


    def get_pos_and_rot_at_percent(self, percent):
        return self.get_pos_at_original_video_ts(percent*self.ts[-1], False), self.get_rot_at_original_video_ts(percent*self.ts[-1], False)


    def set_local_velocity_adjustment_curve(self, local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y):
        self.local_velocity_adjustment_curve_x, self.local_velocity_adjustment_curve_y = np.array(local_velocity_adjustment_curve_x), np.array(local_velocity_adjustment_curve_y)
        self.calculate_pos_and_rot()


    def calculate_pos_and_rot(self):
        self.prev_distance_along_path = -1
        self.prev_distance_along_rotation_path = -1
        stabilized_video_ts = 0.0
        original_video_ts = 0.0
        self.stabilized_pos = []
        self.stabilized_rot = []
        self.stabilized_ts = []
        self.stabilized_ts_original = []
        self.travel_along_pos_curve_distance_ts = []
        self.travel_along_pos_curve_distance_velocity = []
        last_distance = 0.0
        time_between_stabilized_video_frame_pair = 1/self.frame_rate
        time_step_for_simulation_step = time_between_stabilized_video_frame_pair / self.simulation_rate_multiplier
        while original_video_ts < self.ts[-1]:
            self.stabilized_pos.append(self.get_pos_at_original_video_ts(original_video_ts))
            self.stabilized_rot.append(self.get_rot_at_original_video_ts(original_video_ts))
            self.stabilized_ts.append(stabilized_video_ts)
            self.stabilized_ts_original.append(original_video_ts)
            for i in range(self.simulation_rate_multiplier):
                cur_advance_time_multiplier = self.get_advance_time_multiplier(original_video_ts)
                self.travel_along_pos_curve_distance_ts.append(original_video_ts)
                stabilized_video_ts += time_step_for_simulation_step
                original_video_ts += time_step_for_simulation_step * cur_advance_time_multiplier
                if original_video_ts >= self.ts[-1]:
                    break
                distance_along_path = max(0, min(self.progress_along_path_spline(original_video_ts), self.path_total_length))
                cur_velocity = np.abs((distance_along_path - last_distance)/(time_step_for_simulation_step * cur_advance_time_multiplier))
                self.travel_along_pos_curve_distance_velocity.append(cur_velocity)
                last_distance = distance_along_path
        self.travel_along_pos_curve_distance_velocity.append(self.travel_along_pos_curve_distance_velocity[-1])
            
        self.travel_along_pos_curve_distance_ts = np.array(self.travel_along_pos_curve_distance_ts) / self.travel_along_pos_curve_distance_ts[-1]
        avg_velocity = self.get_avg_velocity()
        self.velocity_smoothing_multipliers = []
        for percent in self.velocity_smoothing_points_percents:
            left_side_index = np.searchsorted(self.travel_along_pos_curve_distance_ts, percent)-1
            if left_side_index < 0:
                cur_point_velocity = self.travel_along_pos_curve_distance_velocity[0]
            if left_side_index==len(self.travel_along_pos_curve_distance_ts)-1:
                cur_point_velocity = self.travel_along_pos_curve_distance_velocity[-1]
            else:
                right_side_index = left_side_index + 1

                left_percent = self.travel_along_pos_curve_distance_ts[left_side_index]
                right_percent = self.travel_along_pos_curve_distance_ts[right_side_index]

                right_side_weight = (percent - left_percent) / (right_percent - left_percent)
                left_side_weight = (right_percent - percent) / (right_percent - left_percent)

                cur_point_velocity = right_side_weight * self.travel_along_pos_curve_distance_velocity[right_side_index] + left_side_weight * self.travel_along_pos_curve_distance_velocity[left_side_index]

            if cur_point_velocity==0:
                cur_multiplier = 1000
            else:
                cur_multiplier = avg_velocity / cur_point_velocity
            self.velocity_smoothing_multipliers.append(cur_multiplier)

    def get_advance_time_multiplier(self, original_video_ts):
        cur_original_video_ts_progress_percent = original_video_ts / self.ts[-1]

        left_side_index = np.searchsorted(self.local_velocity_adjustment_curve_x, cur_original_video_ts_progress_percent)-1
        if left_side_index < 0:
            return self.local_velocity_adjustment_curve_y[0]
        if left_side_index==len(self.local_velocity_adjustment_curve_x)-1:
            return self.local_velocity_adjustment_curve_y[-1]
        right_side_index = left_side_index + 1

        left_percent = self.local_velocity_adjustment_curve_x[left_side_index]
        right_percent = self.local_velocity_adjustment_curve_x[right_side_index]

        right_side_weight = (cur_original_video_ts_progress_percent - left_percent) / (right_percent - left_percent)
        left_side_weight = (right_percent - cur_original_video_ts_progress_percent) / (right_percent - left_percent)
        
        return left_side_weight*self.local_velocity_adjustment_curve_y[left_side_index] + right_side_weight*self.local_velocity_adjustment_curve_y[right_side_index]

    def get_stabilization_result(self):
        return self.stabilized_pos, self.stabilized_rot, self.stabilized_ts, self.stabilized_ts_original, self.velocity_smoothing_points_percents, self.velocity_smoothing_multipliers


    def get_pos_at_original_video_ts(self, time, is_bound_by_prev=True):
        '''
        time: the original video timestamp which pos should be calculated
        '''
        distance_along_path = max(0, min(self.progress_along_path_spline(time), self.path_total_length))
        if is_bound_by_prev:
            distance_along_path = max(distance_along_path, self.prev_distance_along_path)
        self.prev_distance_along_path = distance_along_path
        lower_bound_dist = self.path_dist_lookup_by_dist_along_path_tree.floor_key(distance_along_path)
        upper_bound_dist = self.path_dist_lookup_by_dist_along_path_tree.ceiling_key(distance_along_path)
        bound = (self.path_dist_lookup_by_dist_along_path_tree.get(lower_bound_dist)[0], \
                 self.path_dist_lookup_by_dist_along_path_tree.get(upper_bound_dist)[0])
        t_along_path = self.__t_given_distance(distance_along_path, bound = bound)[0]
        return self.path_bspline(t_along_path).tolist()


    def get_rot_at_original_video_ts(self, time, is_bound_by_prev=True):
        '''
        time: the original video timestamp which rot should be calculated
        '''
        distance_along_rotation_path = max(0, min(self.progress_along_rot_curve_spline(time), self.rot_path_total_angular_distance))
        if is_bound_by_prev:
            distance_along_rotation_path = max(distance_along_rotation_path, self.prev_distance_along_rotation_path)
        self.prev_distance_along_rotation_path = distance_along_rotation_path
        lower_bound_dist = self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.floor_key(distance_along_rotation_path)
        upper_bound_dist = self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.ceiling_key(distance_along_rotation_path)
        bound = (self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.get(lower_bound_dist)[0], \
                 self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.get(upper_bound_dist)[0])
        t_along_path = self.__t_given_angular_distance(distance_along_rotation_path, bound = bound)[0]
        rot_quat = self.__quat_along_rot_bspline(t_along_path)
        return Rotation.from_quat(np.array([rot_quat.x, rot_quat.y, rot_quat.z, rot_quat.w])).as_matrix().tolist()


    def __bspline_arc_length(self, t_start, t_end, length_change_threshold_percent = 0.001, \
                             initial_num_t_step_for_whole_curve = 1000, is_update_distance_lookup_tree=False,\
                             t_start_distance = -np.inf):
        '''
        Iteratively slice the curve into smaller and smaller parts to calculate curve length
        until the length change between two iterations is below a percent threshold
        bspline is a scipy.interpolate.BSpline object
        t_start and t_end between 0 and 1, t_end>t_start
        '''
        length_change_percent = np.inf
        cur_num_t_step = max((int(initial_num_t_step_for_whole_curve * (t_end-t_start)), 10))
        last_length = -np.inf
        for i in range(4):
            if length_change_percent <= length_change_threshold_percent:
                break
            distance_given_t_list = []
            last_pos = self.path_bspline(t_start)
            total_length = 0
            for t_i in range(cur_num_t_step):
                cur_t = (t_i+1) / cur_num_t_step * (t_end - t_start) + t_start
                cur_pos = self.path_bspline(cur_t)
                total_length = total_length + np.linalg.norm(last_pos - cur_pos)
                last_pos = cur_pos
                if i>0 and is_update_distance_lookup_tree:
                    distance_given_t_list.append((total_length+t_start_distance, cur_t, cur_pos))
            if i==0:
                length_change_percent == np.inf
            else:
                length_change_percent = (total_length - last_length) / last_length
            # print(cur_num_t_step, last_length, total_length, length_change)
            last_length = total_length
            cur_num_t_step = cur_num_t_step * 2
            if is_update_distance_lookup_tree:
                for distance_given_t in distance_given_t_list:
                    self.path_dist_lookup_by_dist_along_path_tree.set_default(distance_given_t[0], (distance_given_t[1], distance_given_t[2]))
                    self.path_dist_lookup_by_t_dict[distance_given_t[1]] = (distance_given_t[0], distance_given_t[2])

        return last_length


    def __t_given_distance(self, s, length_err_threshold_percent = 0.001, bound = (0,1)):
        '''
        Calculates the t between 0 and 1 that travels along the curve by distance s
        return t, actual length along curve, length error
        '''

        t_lower_bound, t_upper_bound = bound
        if t_lower_bound==t_upper_bound:
            return t_lower_bound, s, 0.0
        if t_lower_bound > t_upper_bound:
            t_lower_bound, t_upper_bound = t_upper_bound, t_lower_bound

        if s > self.path_total_length:
            raise ValueError("Input path length is longer than the total length of the path.")
        
        if t_lower_bound < 0 or t_upper_bound > 1:
            raise ValueError("Input bound exceed the range [0, 1].")

        length_err_threshold = self.path_total_length * length_err_threshold_percent
        
        upper_bound_distance = self.path_dist_lookup_by_t_dict[t_upper_bound][0]
        if upper_bound_distance < s:
            t_lower_bound = t_upper_bound
            t_upper_bound = 1

        lower_bound_distance = self.path_dist_lookup_by_t_dict[t_lower_bound][0]
        t = (t_upper_bound + t_lower_bound) / 2

        for i in range(100):
            cur_curve_length_at_t = self.__bspline_arc_length(t_lower_bound, t) + lower_bound_distance
            length_err = cur_curve_length_at_t - s
            if np.abs(length_err) < length_err_threshold:
                return t, cur_curve_length_at_t, length_err

            if length_err > 0:
                t_upper_bound = t
                t = (t_upper_bound + t_lower_bound) / 2
            else:
                t_lower_bound = t
                t = (t_upper_bound + t_lower_bound) / 2
                lower_bound_distance = cur_curve_length_at_t
        
        return t, cur_curve_length_at_t, length_err
    

    def __quat_along_rot_bspline(self, t):
        '''
        Calculate the quaternion at the given t, which is between 0 and 1
        '''
        cumulative_basis = self.cumulative_basis_bspline(t)
        result_quat = self.omegas_for_bspline[0]**cumulative_basis[0]
        to_be_multiplited_quats = np.exp(self.omegas_for_bspline[1:] * cumulative_basis[1:])
        return result_quat * np.prod(to_be_multiplited_quats)
    

    def __quat_bspline_arc_length(self, t_start, t_end,\
                                  length_change_threshold_percent = 0.0005, \
                                  initial_num_t_step_for_whole_curve=1000,\
                                  is_update_distance_lookup_tree = False, \
                                  t_start_distance = -np.inf):
        '''
        Calculate the total angular distance of the given quaternion B-spline
        '''
        length_change_percent = np.inf
        cur_num_t_step = max((int(initial_num_t_step_for_whole_curve * (t_end-t_start)),10))
        last_length = -np.inf
        for i in range(5):
            if length_change_percent <= length_change_threshold_percent:
                break
            last_quat = self.__quat_along_rot_bspline(t_start)
            total_length = 0
            distance_given_t_list = []
            for t_i in range(cur_num_t_step):
                cur_t = (t_i+1) / cur_num_t_step * (t_end - t_start) + t_start
                cur_quat = self.__quat_along_rot_bspline(cur_t)
                total_length = total_length + quat_angular_dist(last_quat, cur_quat)
                if i>0 and is_update_distance_lookup_tree:
                    distance_given_t_list.append((total_length+t_start_distance, cur_t, cur_quat))
                last_quat = cur_quat
            if i==0:
                length_change_percent = np.inf
            else:
                length_change_percent = (total_length - last_length) / last_length
            # print(cur_num_t_step, last_length, total_length, length_change)
            last_length = total_length
            cur_num_t_step = cur_num_t_step * 2
            if is_update_distance_lookup_tree:
                for distance_given_t in distance_given_t_list:
                    self.rot_angular_dist_lookup_by_dist_along_rot_path_tree.set_default(distance_given_t[0], (distance_given_t[1], distance_given_t[2]))
                    self.rot_angular_dist_lookup_by_t_dict[distance_given_t[1]] = (distance_given_t[0], distance_given_t[2])

        return last_length
    
    
    def __t_given_angular_distance(self, s, length_err_threshold_percent = 0.001, bound = (0,1)):
        '''
        Calculates the t between 0 and 1 that travels along the curve by distance s
        return t, actual length along curve, length error
        '''

        t_lower_bound, t_upper_bound = bound
        if t_lower_bound==t_upper_bound:
            return t_lower_bound, s, 0.0
        if t_lower_bound > t_upper_bound:
            t_lower_bound, t_upper_bound = t_upper_bound, t_lower_bound

        if s > self.rot_path_total_angular_distance:
            raise ValueError("Input rotation path length is longer than the total length of the rotation path.")
        
        if t_lower_bound < 0 or t_upper_bound > 1:
            raise ValueError("Input bound exceed the range [0, 1].")

        length_err_threshold = self.rot_path_total_angular_distance * length_err_threshold_percent
        
        upper_bound_distance = self.rot_angular_dist_lookup_by_t_dict[t_upper_bound][0]
        if upper_bound_distance < s:
            t_lower_bound = t_upper_bound
            t_upper_bound = 1

        lower_bound_distance = self.rot_angular_dist_lookup_by_t_dict[t_lower_bound][0]
        t = (t_upper_bound + t_lower_bound) / 2

        for i in range(100):
            cur_curve_length_at_t = self.__quat_bspline_arc_length(t_lower_bound, t) + lower_bound_distance
            length_err = cur_curve_length_at_t - s
            if np.abs(length_err) < length_err_threshold:
                return t, cur_curve_length_at_t, length_err

            if length_err > 0:
                t_upper_bound = t
                t = (t_upper_bound + t_lower_bound) / 2
            else:
                t_lower_bound = t
                t = (t_upper_bound + t_lower_bound) / 2
                lower_bound_distance = cur_curve_length_at_t
        
        return t, cur_curve_length_at_t, length_err
