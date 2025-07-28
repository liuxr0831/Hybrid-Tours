from argparse import ArgumentParser
import os
import json
import cv2
import base64
import pickle

parser = ArgumentParser("Prepare JPEG frames from frontend")
parser.add_argument("--project_path", "-s", required=True, type=str)
args = parser.parse_args()

tbc_path = os.path.join(args.project_path, 'to_be_concatenated')
with open(os.path.join(tbc_path, 'extract_config.json'), 'r') as file:
    extract_config = json.load(file)
to_be_concatenated_file_names = sorted(list(extract_config['tbc_file_extracted_frames'].keys()))

frontend_frame_dir = os.path.join(tbc_path, 'for_frontend')
os.makedirs(frontend_frame_dir, exist_ok=True)
for tbc_video_name in to_be_concatenated_file_names:
    video_capture = cv2.VideoCapture(os.path.join(tbc_path, tbc_video_name))
    width = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    num_total_frame = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for frame_i in range(num_total_frame):
        ret, frame = video_capture.read()
        frame = cv2.resize(frame, (int(width/4), int(height/4)))
        ret, buffer = cv2.imencode('.jpg', frame)
        frames.append(base64.b64encode(buffer.tobytes()).decode('utf-8'))
    with open(os.path.join(frontend_frame_dir, tbc_video_name+'.pickle'), 'wb') as file:
        pickle.dump(frames, file)