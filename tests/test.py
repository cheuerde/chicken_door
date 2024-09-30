import gpiod
from time import sleep
import signal
import sys
import threading

# Define GPIO pins
SLP_PIN = 17    # SLEEP GPIO Pin
DIR_PIN = 20    # Direction GPIO Pin
STEP_PIN = 21   # Step GPIO Pin
BTN_CW_PIN = 5  # Button for Clockwise Rotation
BTN_CCW_PIN = 6 # Button for Counterclockwise Rotation
BTN_STOP_PIN = 13  # New: Button to stop motor
LIGHT_PIN = 26  # New: Pin to control the light
BTN_LIGHT_PIN = 19  # New: Button to toggle light
CW = 1          # Clockwise Rotation
CCW = 0         # Counterclockwise Rotation
SPR = 588       # Steps per Revolution (360 / 7.5)

# Initialize the chip and lines
chip = gpiod.Chip('gpiochip4')
dir_line = chip.get_line(DIR_PIN)
step_line = chip.get_line(STEP_PIN)
slp_line = chip.get_line(SLP_PIN)
btn_cw_line = chip.get_line(BTN_CW_PIN)
btn_ccw_line = chip.get_line(BTN_CCW_PIN)
btn_stop_line = chip.get_line(BTN_STOP_PIN)  # New: Stop button line
light_line = chip.get_line(LIGHT_PIN)  # New: Light control line
btn_light_line = chip.get_line(BTN_LIGHT_PIN)  # New: Light button line

# Global variables
stop_motor = False
light_on = False

def cleanup():
    print("Releasing GPIO lines...")
    dir_line.release()
    step_line.release()
    slp_line.release()
    btn_cw_line.release()
    btn_ccw_line.release()
    btn_stop_line.release()  # New: Release stop button line
    light_line.release()  # New: Release light control line
    btn_light_line.release()  # New: Release light button line
    chip.close()
    print("GPIO lines released and chip closed. Cleanup complete.")

def signal_handler(sig, frame):
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

try:
    # Request lines
    print("Requesting GPIO lines...")
    dir_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
    step_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
    slp_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)
    btn_cw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    btn_ccw_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
    btn_stop_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)  # New: Request stop button line
    light_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_OUT)  # New: Request light control line
    btn_light_line.request(consumer='test', type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)  # New: Request light button line
    print("GPIO lines successfully requested.")

    # Function to control stepper motor rotation
    def rotate_motor(direction, steps, delay):
        global stop_motor
        stop_motor = False
        if slp_line.get_value() == 0:
            print("Waking up motor driver...")
            slp_line.set_value(1)
            sleep(0.1)
        
        print(f"Setting direction: {'Clockwise' if direction == CW else 'Counterclockwise'}")
        dir_line.set_value(direction)
        for step in range(steps):
            if stop_motor:
                print("Motor stopped by user")
                break
            step_line.set_value(1)
            sleep(delay)
            step_line.set_value(0)
            sleep(delay)
            print(f"Step {step + 1}/{steps} completed.")
        
        print("Putting motor driver to sleep...")
        slp_line.set_value(0)

    # New: Function to control light
    def toggle_light():
        global light_on
        light_on = not light_on
        light_line.set_value(1 if light_on else 0)
        print(f"Light turned {'on' if light_on else 'off'}")

    # New: Function to handle software commands
    def command_handler():
        global stop_motor
        while True:
            command = input("Enter command (cw, ccw, stop, light): ").strip().lower()
            if command == "cw":
                print("Software command: clockwise rotation")
                rotate_motor(CW, SPR, delay)
            elif command == "ccw":
                print("Software command: counterclockwise rotation")
                rotate_motor(CCW, SPR, delay)
            elif command == "stop":
                print("Software command: stop motor")
                stop_motor = True
            elif command == "light":
                print("Software command: toggle light")
                toggle_light()
            else:
                print("Unknown command")

    # Start the command handler in a separate thread
    threading.Thread(target=command_handler, daemon=True).start()

    delay = 0.0028

    print("Waiting for button presses...")
    while True:
        if btn_cw_line.get_value() == 0:
            print("Button for clockwise rotation pressed")
            threading.Thread(target=rotate_motor, args=(CW, SPR, delay)).start()
            sleep(0.5)  # Debounce delay
        
        if btn_ccw_line.get_value() == 0:
            print("Button for counterclockwise rotation pressed")
            threading.Thread(target=rotate_motor, args=(CCW, SPR, delay)).start()
            sleep(0.5)  # Debounce delay

        if btn_stop_line.get_value() == 0:
            print("Stop button pressed")
            stop_motor = True
            sleep(0.5)  # Debounce delay

        if btn_light_line.get_value() == 0:
            print("Light button pressed")
            toggle_light()
            sleep(0.5)  # Debounce delay

finally:
    cleanup()
