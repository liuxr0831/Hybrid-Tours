from scipy.spatial.transform import Rotation
import numpy as np
from scipy.interpolate import BSpline, CubicSpline
from bintrees import FastRBTree

from orientation_quaternion import rotation_order
from quaternion_operations import dot, quat_angular_dist, rot_to_quat
from concatenate_utils import sample_points

class Stabilize_Helper:
    def __init__(self, pos, rot, ts, start_percent, end_percent, sampling_interval):
        '''
        pos: n-by-3 np array
        rot: n-by-3 euler angle given in rotation_order
        ts: timestamp of each row given in a 1D numpy array
        start_percent and end_percent: range selected by trimming
        sampling_interval: every percent of total video length one sample
        local_velocity_adjustment_curve_x, local_velocity_adjustment_curve_y: define relation between how much we step for stabilized video ts and how much we step for original video ts, 1D array
        frame_rate: frame rate of the stabilized video
        '''
        # First just interpolate with all


        # Store input to potentially reuse current stabilization result
        self.selected_range = (start_percent, end_percent)
        self.sampling_interval = sampling_interval

        pos, rot, ts = sample_points(pos, rot, ts, start_percent, end_percent, sampling_interval)

        if np.size(pos, 0) < 4:
            raise ValueError("The number of points provided is less than 4. There must be at least 4 points.")
        self.pos = pos
        self.ts = ts


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
        

        self.distances_of_timestamped_pos_from_start = distances_of_timestamped_pos_from_start



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
        
        # Use CubicSpline to interpolate the distance for all timestamps
        self.distances_of_timestamped_rot_from_start = distances_of_timestamped_rot_from_start



    def get_original_ts_to_distance_dense_mapping(self):
        return self.ts, self.distances_of_timestamped_pos_from_start, self.distances_of_timestamped_rot_from_start



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
