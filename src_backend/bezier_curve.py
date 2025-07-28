import numpy as np

bezier_mat_3 = np.array([[-1,3,-3,1], [3,-6,3,0], [-3,3,0,0], [1,0,0,0]])
bezier_mat_4 = np.array([[1,-4,6,-4,1], [-4,12,-12,4,0], [6,-12,6,0,0], [-4,4,0,0,0], [1,0,0,0,0]])
bezier_mat_5 = np.array([[-1,5,-10,10,-5,1], [5,-20,30,-20,5,0], [-10,30,-30,10,0,0], [10,-20,10,0,0,0], [-5,5,0,0,0,0], [1,0,0,0,0,0]])


def bezier(p, t):
    '''
    p is a num_control_point-by-num_dimension array
    t between 0 and 1
    '''
    if np.size(p,0) == 4:
        return np.array([t**3, t**2, t**1, 1]) @ bezier_mat_3 @ p
    elif np.size(p,0) == 5:
        return np.array([t**4, t**3, t**2, t**1, 1]) @ bezier_mat_4 @ p
    elif np.size(p,0) == 6:
        return np.array([t**5, t**4, t**3, t**2, t**1, 1]) @ bezier_mat_5 @ p
    
def bezier_coeff(p, t):
    '''
    p is a num_control_point-by-num_dimension array
    t between 0 and 1
    '''
    if np.size(p,0) == 4:
        return np.array([t**3, t**2, t**1, 1]) @ bezier_mat_3
    elif np.size(p,0) == 5:
        return np.array([t**4, t**3, t**2, t**1, 1]) @ bezier_mat_4
    elif np.size(p,0) == 6:
        return np.array([t**5, t**4, t**3, t**2, t**1, 1]) @ bezier_mat_5

def d_bezier(p, t):
    '''
    p is a num_control_point-by-num_dimension array
    t between 0 and 1
    '''
    if np.size(p,0) == 4:
        return np.array([3*t**2, 2*t, 1, 0]) @ bezier_mat_3 @ p
    elif np.size(p,0) == 5:
        return np.array([4*t**3, 3*t**2, 2*t, 1, 0]) @ bezier_mat_4 @ p
    elif np.size(p,0) == 6:
        return np.array([5*t**4, 4*t**3, 3*t**2, 2*t, 1, 0]) @ bezier_mat_5 @ p

def d_bezier_coeff(p, t):
    '''
    p is a num_control_point-by-num_dimension array
    t between 0 and 1
    '''
    if np.size(p,0) == 4:
        return np.array([3*t**2, 2*t, 1, 0]) @ bezier_mat_3
    elif np.size(p,0) == 5:
        return np.array([4*t**3, 3*t**2, 2*t, 1, 0]) @ bezier_mat_4
    elif np.size(p,0) == 6:
        return np.array([5*t**4, 4*t**3, 3*t**2, 2*t, 1, 0]) @ bezier_mat_5
    
def dd_bezier_coeff(p, t):
    '''
    p is a num_control_point-by-num_dimension array
    t between 0 and 1
    '''
    if np.size(p,0) == 4:
        return np.array([6*t, 2, 0, 0]) @ bezier_mat_3
    elif np.size(p,0) == 5:
        return np.array([12*t**2, 6*t, 2, 0, 0]) @ bezier_mat_4
    elif np.size(p,0) == 6:
        return np.array([20*t**3, 12*t**2, 6*t, 2, 0, 0]) @ bezier_mat_5


def bezier_arc_length(p, t_start, t_end):
    '''
    Iteratively slice the curve into smaller and smaller parts to calculate curve length
    until the length change is below a threshold
    p is a num_control_point-by-num_dimension array
    t_start and t_end between 0 and 1, t_end>t_start
    '''
    length_change_threshold_percent = 0.0001
    initial_num_t_step = 200

    length_change_threshold = 1/2*(np.linalg.norm(p[0,:] - p[1,:]) + np.linalg.norm(p[2,:] - p[3,:])) \
                              *length_change_threshold_percent
    length_change = np.inf
    last_length = -np.inf
    cur_num_t_step = initial_num_t_step

    for i in range(4):
        if length_change <= length_change_threshold:
            break
        last_pos = bezier(p, t_start)
        total_length = 0
        for t_i in range(cur_num_t_step):
            next_pos = bezier(p, (t_i+1) / cur_num_t_step * (t_end - t_start) + t_start)
            total_length = total_length + np.linalg.norm(last_pos - next_pos)
            last_pos = next_pos
        length_change = total_length - last_length
        # print(cur_num_t_step, last_length, total_length, length_change)
        last_length = total_length
        cur_num_t_step = cur_num_t_step * 2

    return last_length


def t(p, s):
    '''
    Calculates the t between 0 and 1 that travels along the curve by distance s
    Based on https://medium.com/@ommand/movement-along-the-curve-with-constant-speed-4fa383941507
    p is a num_control_point-by-num_dimension array
    return t, actual length along curve, length error (np.inf if s > curve length)
    '''
    length_err_threshold_percent = 0.00001

    t_upper_bound = 1
    t_lower_bound = 0

    arc_total_length = bezier_arc_length(p, 0, 1)
    length_err_threshold = arc_total_length * length_err_threshold_percent
    if s > arc_total_length:
        return (1, arc_total_length, np.inf)
    
    t = s / arc_total_length

    for i in range(100):
        cur_curve_length_at_t = bezier_arc_length(p, 0, t)
        length_err = cur_curve_length_at_t - s
        if np.abs(length_err) < length_err_threshold:
            return t, cur_curve_length_at_t, length_err
        
        derivative = np.linalg.norm(d_bezier(p, t))
        new_t = t - length_err / derivative

        if length_err > 0:
            t_upper_bound = t
            if new_t < 0:
                t = (t_upper_bound + t_lower_bound) / 2
            else:
                t = new_t
        else:
            t_lower_bound = t
            if new_t > 1:
                t = (t_upper_bound + t_lower_bound) / 2
            else:
                t = new_t
    
    return t, cur_curve_length_at_t, length_err
