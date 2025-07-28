import numpy as np
import quaternion


def dot(q1, q2):
    return q1.w*q2.w + q1.x*q2.x + q1.y*q2.y + q1.z*q2.z

def quat_angular_dist(q1, q2):
    return 2*np.arccos(np.clip(np.abs((q1*np.conjugate(q2)).w), 0.0, 1.0))

def rot_to_quat(r):
    return np.quaternion(*(r.as_quat(canonical=True)[[3,0,1,2]]))