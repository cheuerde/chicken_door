import os
import logging
from flask import Flask, render_template, request, Response, jsonify, redirect, url_for
import cv2
import gpiod
import threading
from time import sleep
import atexit
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import schedule
import time

app = Flask(__name__)

# Define the log directory and file
log_dir = os.path.expanduser("~/logs")
log_file = os.path.join(log_dir, "motor_light_control.log")

# Create the log directory if it doesn't exist
os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# Suppress Flask request logs (like GET /logs)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Global variables
SPR = 6000  # Steps per revolution
delay = 0.001  # Delay between steps
light_on = False
stop_motor = False
camera_on = True
camera = None
camera_device = 0
holding_torque = True
door_open_direction = 'CCW'  # Can be 'CW' or 'CCW'

# Location settings for sunrise/sunset calculations
latitude = 53.5396  # Example: Berlin latitude
longitude = 10.004  # Example: Berlin longitude
location = LocationInfo("Custom", "Region", "Timezone", latitude, longitude)

# Pin assignments
PIN_ASSIGNMENTS = {
    'SLP_PIN': 17,
    'DIR_PIN': 20,
    'STEP_PIN': 21,
    'BTN_CW_PIN': 5,
    'BTN_CCW_PIN': 6,
    'BTN_STOP_PIN': 13,
    'LIGHT_PIN': 26,
    'BTN_LIGHT_PIN': 19,
    'LEVER_CW_PIN': 12,
    'LEVER_CCW_PIN': 16
}

# Initialize the chip and lines
chip = gpiod.Chip('gpiochip4')
dir_line = chip.get_line(PIN_ASSIGNMENTS['DIR_PIN'])
step_line = chip.get_line(PIN_ASSIGNMENTS['STEP_PIN'])
slp_line = chip.get_line(PIN_ASSIGNMENTS['SLP_PIN'])
light_line = chip.get_line(PIN_ASSIGNMENTS['LIGHT_PIN'])
btn_cw_line = chip.get_line(PIN_ASSIGNMENTS['BTN_CW_PIN'])
btn_ccw_line = chip.get_line(PIN_ASSIGNMENTS['BTN_CCW_PIN'])
btn_stop_line = chip.get_line(PIN_ASSIGNMENTS['BTN_STOP_PIN'])
btn_light_line = chip.get_line(PIN_ASSIGNMENTS['BTN_LIGHT_PIN'])
lever_cw_line = chip.get_line(PIN_ASSIGNMENTS['LEVER_CW_PIN'])
lever_ccw_line = chip.get_line(PIN_ASSIGNMENTS['LEVER_CCW_PIN'])

def cleanup():
    logging.info("Cleaning up GPIO lines and resources...")
    slp_line.set_value(0)  # Put the motor driver to sleep
    dir_line.release()
    step_line.release()
    slp_line.release()
    light_line.release()
    btn_cw_line.release()
    btn_ccw_line.release()
    btn_stop_line.release()
    btn_light_line.release()
    lever_cw_line.release()
    lever_ccw_line.release()
    logging.info("GPIO lines released and chip closed. Cleanup complete.")

# Request lines
logging.info("Requesting GPIO lines...")
dir_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
step_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
slp_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
light_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
btn_cw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
btn_ccw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
btn_stop_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
btn_light_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
lever_cw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
lever_ccw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
logging.info("GPIO lines successfully requested.")

def read_slp_state():
    return slp_line.get_value()

def set_holding_torque(enable):
    global holding_torque
    current_state = read_slp_state()
    if enable != (current_state == 1):
        slp_line.set_value(1 if enable else 0)
        holding_torque = enable
        logging.info(f"Holding torque {'enabled' if enable else 'disabled'}. SLP pin changed from {current_state} to {1 if enable else 0}.")
    else:
        logging.info(f"Holding torque already {'enabled' if enable else 'disabled'}. SLP pin remains at {current_state}.")

def rotate_motor(direction, steps, delay):
    global stop_motor
    stop_motor = False
    logging.info(f"Starting motor rotation: {'Clockwise' if direction == 1 else 'Counterclockwise'} for {steps} steps with {delay}s delay.")
    logging.info(f"Before rotation: Holding torque is {'enabled' if holding_torque else 'disabled'}, SLP pin state is {read_slp_state()}")
    
    # Ensure motor driver is awake
    set_holding_torque(True)
    
    dir_line.set_value(direction)
    for step in range(steps):
        if stop_motor or btn_stop_line.get_value() == 0 or \
           (direction == 1 and lever_cw_line.get_value() == 0) or \
           (direction == 0 and lever_ccw_line.get_value() == 0):
            logging.info("Motor rotation stopped.")
            break
        step_line.set_value(1)
        sleep(delay)
        step_line.set_value(0)
        sleep(delay)
    
    logging.info("Rotation completed or stopped. Maintaining holding torque.")
    set_holding_torque(True)
    logging.info(f"After rotation: Holding torque is {'enabled' if holding_torque else 'disabled'}, SLP pin state is {read_slp_state()}")

def toggle_light():
    global light_on
    light_on = not light_on
    light_line.set_value(1 if light_on else 0)
    logging.info(f"Light turned {'on' if light_on else 'off'}")

def handle_button_presses():
    global stop_motor
    while True:
        if btn_cw_line.get_value() == 0 and lever_cw_line.get_value() == 1:
            logging.info("Clockwise rotation button pressed.")
            rotate_motor(1, SPR, delay)
            sleep(0.5)  # Debounce delay
        if btn_ccw_line.get_value() == 0 and lever_ccw_line.get_value() == 1:
            logging.info("Counterclockwise rotation button pressed.")
            rotate_motor(0, SPR, delay)
            sleep(0.5)  # Debounce delay
        if btn_stop_line.get_value() == 0:
            logging.info("Stop button pressed.")
            stop_motor = True
            set_holding_torque(True)
            sleep(0.5)  # Debounce delay
        if btn_light_line.get_value() == 0:
            logging.info("Light toggle button pressed.")
            toggle_light()
            sleep(0.5)  # Debounce delay
        sleep(0.1)  # Small delay to prevent excessive CPU usage

def get_sun_times():
    s = sun(location.observer, date=datetime.now(), tzinfo=location.timezone)
    return s['sunrise'], s['sunset']

def open_door():
    logging.info("Automatic door opening triggered")
    if door_open_direction == 'CW':
        rotate_motor(1, SPR, delay)
    else:
        rotate_motor(0, SPR, delay)

def close_door():
    logging.info("Automatic door closing triggered")
    if door_open_direction == 'CW':
        rotate_motor(0, SPR, delay)
    else:
        rotate_motor(1, SPR, delay)

def schedule_door_events():
    sunrise, sunset = get_sun_times()
    
    schedule.every().day.at(sunrise.strftime("%H:%M")).do(open_door)
    schedule.every().day.at((sunset - timedelta(minutes=30)).strftime("%H:%M")).do(toggle_light)
    schedule.every().day.at(sunset.strftime("%H:%M")).do(close_door)
    schedule.every().day.at((sunset + timedelta(minutes=15)).strftime("%H:%M")).do(toggle_light)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

@app.route('/')
def index():
    logging.info("Accessed index page.")
    return render_template('index.html', spr=SPR, delay=delay, pin_assignments=PIN_ASSIGNMENTS, door_open_direction=door_open_direction)

@app.route('/control/<action>')
def control(action):
    global stop_motor
    if action == 'cw':
        if lever_cw_line.get_value() == 1:
            logging.info("Received web command: Rotate clockwise.")
            rotate_motor(1, SPR, delay)
            return jsonify({'message': 'Rotating clockwise'})
        else:
            logging.info("Clockwise rotation blocked by lever switch.")
            return jsonify({'message': 'Clockwise rotation blocked'})
    elif action == 'ccw':
        if lever_ccw_line.get_value() == 1:
            logging.info("Received web command: Rotate counterclockwise.")
            rotate_motor(0, SPR, delay)
            return jsonify({'message': 'Rotating counterclockwise'})
        else:
            logging.info("Counterclockwise rotation blocked by lever switch.")
            return jsonify({'message': 'Counterclockwise rotation blocked'})
    elif action == 'stop':
        logging.info("Received web command: Stop motor.")
        stop_motor = True
        set_holding_torque(True)
        return jsonify({'message': 'Motor stopped'})
    elif action == 'toggle_light':
        logging.info("Received web command: Toggle light.")
        toggle_light()
        return jsonify({'message': f'Light toggled {"on" if light_on else "off"}'})
    logging.warning(f"Received invalid web command: {action}.")
    return jsonify({'error': 'Invalid action'}), 400

@app.route('/update_variables', methods=['POST'])
def update_variables():
    global SPR, delay
    data = request.json
    SPR = int(data['spr'])
    delay = float(data['delay'])
    logging.info(f"Updated variables: SPR={SPR}, Delay={delay}.")
    return jsonify({'message': f'Variables updated - SPR: {SPR}, Delay: {delay}'})

@app.route('/update_pins', methods=['POST'])
def update_pins():
    global PIN_ASSIGNMENTS
    new_assignments = request.json
    
    for key, value in new_assignments.items():
        if not isinstance(value, int) or value < 0 or value > 27:
            logging.warning(f"Invalid pin assignment attempted: {key}={value}.")
            return jsonify({'error': f'Invalid value for {key}'}), 400
    
    PIN_ASSIGNMENTS = new_assignments
    logging.info(f"Updated pin assignments: {PIN_ASSIGNMENTS}. Restart required for changes to take effect.")
    return jsonify({'message': 'Pin assignments updated. Restart required for changes to take effect.'})

@app.route('/toggle_holding_torque')
def toggle_holding_torque():
    global holding_torque
    current_state = holding_torque
    set_holding_torque(not current_state)
    return jsonify({'message': f'Holding torque {"enabled" if holding_torque else "disabled"}'})

@app.route('/logs')
def view_logs():
    logging.debug("Accessed logs page.")
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            log_content = f.read()
        return log_content
    else:
        return "Log file not found", 404

def get_camera():
    global camera, camera_on, camera_device
    if camera_on and camera is None:
        logging.info(f"Initializing camera with device {camera_device}.")
        camera = cv2.VideoCapture(camera_device)
    return camera

def gen_frames():
    while camera_on:
        camera = get_camera()
        if camera is None:
            break
        success, frame = camera.read()
        if not success:
            logging.error("Failed to read from camera.")
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    logging.info("Accessed video feed.")
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_camera')
def toggle_camera():
    global camera_on, camera
    camera_on = not camera_on
    if not camera_on and camera is not None:
        camera.release()
        camera = None
    logging.info(f"Camera turned {'on' if camera_on else 'off'}")
    return redirect(url_for('index'))

@app.route('/set_camera_device', methods=['POST'])
def set_camera_device():
    global camera_device, camera
    camera_device = int(request.form['device'])
    if camera is not None:
        camera.release()
        camera = None
    logging.info(f"Camera device set to {camera_device}")
    return redirect(url_for('index'))

@app.route('/get_status')
def get_status():
    logging.debug("Status request received.")
    return jsonify({
        'spr': SPR,
        'delay': delay,
        'light_on': light_on,
        'camera_on': camera_on,
        'camera_device': camera_device,
        'pin_assignments': PIN_ASSIGNMENTS,
        'holding_torque': holding_torque,
        'lever_cw_pressed': lever_cw_line.get_value() == 0,
        'lever_ccw_pressed': lever_ccw_line.get_value() == 0,
        'door_open_direction': door_open_direction
    })

@app.route('/scheduled_events')
def scheduled_events():
    sunrise, sunset = get_sun_times()
    return jsonify({
        'next_open': sunrise.strftime("%H:%M"),
        'next_close': sunset.strftime("%H:%M"),
        'next_light_on': (sunset - timedelta(minutes=30)).strftime("%H:%M"),
        'next_light_off': (sunset + timedelta(minutes=15)).strftime("%H:%M")
    })

@atexit.register
def cleanup_resources():
    logging.info("Cleaning up resources at exit.")
    cleanup()
    if camera:
        camera.release()

if __name__ == '__main__':
    logging.info(f"Starting application with door open direction: {door_open_direction}")
    
    initial_slp_state = read_slp_state()
    logging.info(f"Initial SLP pin state: {initial_slp_state}")

    set_holding_torque(True)
    
    logging.info(f"After initialization: Holding torque is {'enabled' if holding_torque else 'disabled'}, SLP pin state is {read_slp_state()}")

    button_thread = threading.Thread(target=handle_button_presses, daemon=True)
    button_thread.start()

    schedule_door_events()
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    logging.info("Starting Flask app.")
    app.run(host='0.0.0.0', port=5000, threaded=True)
