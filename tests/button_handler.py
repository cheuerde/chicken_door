import gpiod
from time import sleep
import signal
import sys
import json

# Pin assignments
PIN_ASSIGNMENTS = {
    'BTN_CW_PIN': 5,
    'BTN_CCW_PIN': 6,
    'BTN_STOP_PIN': 13,
    'BTN_LIGHT_PIN': 19
}

# File to communicate with the Flask app
COMMAND_FILE = '/tmp/button_commands.json'

# Initialize the chip and lines
chip = gpiod.Chip('gpiochip4')
btn_cw_line = chip.get_line(PIN_ASSIGNMENTS['BTN_CW_PIN'])
btn_ccw_line = chip.get_line(PIN_ASSIGNMENTS['BTN_CCW_PIN'])
btn_stop_line = chip.get_line(PIN_ASSIGNMENTS['BTN_STOP_PIN'])
btn_light_line = chip.get_line(PIN_ASSIGNMENTS['BTN_LIGHT_PIN'])

def cleanup():
    print("Releasing GPIO lines...")
    btn_cw_line.release()
    btn_ccw_line.release()
    btn_stop_line.release()
    btn_light_line.release()
    chip.close()
    print("GPIO lines released and chip closed. Cleanup complete.")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def write_command(action):
    with open(COMMAND_FILE, 'w') as f:
        json.dump({'action': action}, f)

try:
    # Request lines
    print("Requesting GPIO lines...")
    btn_cw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    btn_ccw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    btn_stop_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    btn_light_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    print("GPIO lines successfully requested.")

    print("Waiting for button presses...")
    while True:
        if btn_cw_line.get_value() == 0:
            print("Button for clockwise rotation pressed")
            write_command('cw')
            sleep(0.5)  # Debounce delay
        if btn_ccw_line.get_value() == 0:
            print("Button for counterclockwise rotation pressed")
            write_command('ccw')
            sleep(0.5)  # Debounce delay
        if btn_stop_line.get_value() == 0:
            print("Stop button pressed")
            write_command('stop')
            sleep(0.5)  # Debounce delay
        if btn_light_line.get_value() == 0:
            print("Light button pressed")
            write_command('toggle_light')
            sleep(0.5)  # Debounce delay
        sleep(0.1)  # Small delay to prevent excessive CPU usage

finally:
    cleanup()
