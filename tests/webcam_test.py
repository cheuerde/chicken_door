import cv2
import logging
from flask import Flask, render_template_string, Response, request, redirect, url_for
import subprocess

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variables
camera = None
camera_device = 0

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Webcam Test</title>
</head>
<body>
    <h1>Webcam Test</h1>
    
    <h2>Available Cameras</h2>
    <form action="{{ url_for('set_camera_device') }}" method="post">
        <select name="device">
            {% for camera in camera_info %}
                <option value="{{ camera.id }}" {% if camera.id == current_device %}selected{% endif %}>
                    {{ camera.name }} ({{ camera.resolution }} @ {{ camera.fps }} FPS)
                </option>
            {% endfor %}
        </select>
        <input type="submit" value="Set Camera">
    </form>

    <h2>Camera Feed</h2>
    <img src="{{ url_for('video_feed') }}" width="640" height="480">
</body>
</html>
'''

def get_available_cameras():
    camera_list = []
    for i in range(10):  # Check first 10 indexes
        logging.info(f"Checking camera index {i}")
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            logging.info(f"Camera {i} opened successfully")
            ret, frame = cap.read()
            if ret:
                logging.info(f"Successfully read frame from camera {i}")
                camera_list.append(i)
            else:
                logging.warning(f"Opened camera {i}, but couldn't read frame")
        else:
            logging.info(f"Couldn't open camera {i}")
        cap.release()
    logging.info(f"Available cameras: {camera_list}")
    return camera_list

def get_camera_info(device):
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return None
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    try:
        camera_name = subprocess.check_output(['v4l2-ctl', '--device', f'/dev/video{device}', '--all'], 
                                              universal_newlines=True)
        camera_name = [line for line in camera_name.split('\n') if 'Card type' in line][0].split(':')[1].strip()
    except:
        camera_name = f"Camera {device}"
    
    cap.release()
    return {
        'id': device,
        'name': camera_name,
        'resolution': f"{width}x{height}",
        'fps': fps
    }

def get_camera():
    global camera, camera_device
    if camera is None:
        logging.info(f"Initializing camera with device {camera_device}")
        camera = cv2.VideoCapture(camera_device)
        if not camera.isOpened():
            logging.error(f"Failed to open camera device {camera_device}")
            camera = None
    return camera

def gen_frames():
    while True:
        camera = get_camera()
        if camera is None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')
            continue
        success, frame = camera.read()
        if not success:
            logging.error("Failed to read frame from camera")
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')
            continue
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def test_cameras():
    print("Testing camera availability:")
    available_cameras = get_available_cameras()
    for camera in available_cameras:
        info = get_camera_info(camera)
        print(f"Camera {camera}: {info}")

if __name__ == '__main__':
    test_cameras()
    # app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/')
def index():
    available_cameras = get_available_cameras()
    camera_info = [get_camera_info(device) for device in available_cameras]
    return render_template_string(HTML_TEMPLATE, camera_info=camera_info, current_device=camera_device)

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_camera_device', methods=['POST'])
def set_camera_device():
    global camera_device, camera
    camera_device = int(request.form['device'])
    if camera is not None:
        camera.release()
        camera = None
    logging.info(f"Camera device set to {camera_device}")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
