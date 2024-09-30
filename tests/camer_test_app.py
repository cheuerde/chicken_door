from flask import Flask, Response, request
import cv2
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

camera = None
camera_device = 0

@app.route('/', methods=['GET', 'POST'])
def index():
    global camera, camera_device

    if request.method == 'POST':
        camera_device = int(request.form.get('device', 0))
        if camera:
            camera.release()
        camera = None

    camera_list = get_camera_list()
    camera_info = get_camera_info(camera_device)

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Debug</title>
    </head>
    <body>
        <h1>Camera Debug Interface</h1>
        
        <h2>Camera Selection</h2>
        <form method="post">
            <label for="device">Select Camera Device:</label>
            <select name="device" id="device">
                {' '.join(f'<option value="{i}"{" selected" if i == camera_device else ""}>{i}</option>' for i in range(10))}
            </select>
            <input type="submit" value="Set Camera">
        </form>

        <h2>Camera Information</h2>
        <pre>{camera_info}</pre>

        <h2>Available Cameras</h2>
        <pre>{camera_list}</pre>

        <h2>Live Feed</h2>
        <img src="/video_feed" width="640" height="480" />

        <h2>Debug Log</h2>
        <pre id="log"></pre>

        <script>
            function updateLog() {{
                fetch('/log')
                    .then(response => response.text())
                    .then(data => {{
                        document.getElementById('log').textContent = data;
                    }});
            }}
            setInterval(updateLog, 1000);
        </script>
    </body>
    </html>
    '''

def get_camera_list():
    cameras = []
    for i in range(10):  # Check first 10 indexes
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cameras.append(str(i))
            cap.release()
    return "Available cameras: " + ", ".join(cameras)

def get_camera_info(device):
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return f"Failed to open camera device {device}"
    
    info = f"Camera device: {device}\n"
    props = [
        ('CV_CAP_PROP_FRAME_WIDTH', cv2.CAP_PROP_FRAME_WIDTH),
        ('CV_CAP_PROP_FRAME_HEIGHT', cv2.CAP_PROP_FRAME_HEIGHT),
        ('CV_CAP_PROP_FPS', cv2.CAP_PROP_FPS),
        ('CV_CAP_PROP_FOURCC', cv2.CAP_PROP_FOURCC),
        ('CV_CAP_PROP_BRIGHTNESS', cv2.CAP_PROP_BRIGHTNESS),
        ('CV_CAP_PROP_CONTRAST', cv2.CAP_PROP_CONTRAST),
        ('CV_CAP_PROP_SATURATION', cv2.CAP_PROP_SATURATION),
        ('CV_CAP_PROP_HUE', cv2.CAP_PROP_HUE),
        ('CV_CAP_PROP_GAIN', cv2.CAP_PROP_GAIN),
        ('CV_CAP_PROP_EXPOSURE', cv2.CAP_PROP_EXPOSURE),
    ]
    
    for prop_name, prop_id in props:
        value = cap.get(prop_id)
        info += f"{prop_name}: {value}\n"
    
    cap.release()
    return info

def gen_frames():
    global camera, camera_device
    while True:
        if camera is None:
            camera = cv2.VideoCapture(camera_device)
        
        success, frame = camera.read()
        if not success:
            logging.error(f"Failed to read from camera device {camera_device}")
            if camera:
                camera.release()
            camera = None
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/log')
def get_log():
    with open('app.log', 'r') as f:
        return f.read()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
