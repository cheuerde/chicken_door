import os
import logging
import gpiod
from time import sleep

# Setup logging
log_file = os.path.expanduser("~/logs/holding_torque_test.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

# Pin assignments
SLP_PIN = 17  # Sleep pin
RESET_PIN = 27  # Reset pin (connect as required)

# Initialize the chip and lines
chip = gpiod.Chip('gpiochip4')
slp_line = chip.get_line(SLP_PIN)
reset_line = chip.get_line(RESET_PIN)

def cleanup():
    logging.info("Cleaning up GPIO lines...")
    slp_line.release()
    reset_line.release()
    logging.info("GPIO lines released and chip closed. Cleanup complete.")

# Request the SLP and RESET lines
logging.info("Requesting GPIO lines for SLP and RESET...")
slp_line.request(consumer='holding_torque_test', type=gpiod.LINE_REQ_DIR_OUT)
reset_line.request(consumer='holding_torque_test', type=gpiod.LINE_REQ_DIR_OUT)
logging.info("GPIO lines successfully requested.")

def apply_holding_torque(holding_torque):
    if holding_torque:
        logging.info("Applying holding torque.")
        slp_line.set_value(1)  # Keep the motor energized by keeping SLP high
        sleep(0.1)  # Allow time for the motor to stabilize
        logging.info("Holding torque applied. SLP line set to high.")
    else:
        logging.info("Putting motor driver to sleep.")
        slp_line.set_value(0)
        sleep(0.1)
        logging.info("Motor driver put to sleep. SLP line set to low.")

def enable_motor_driver():
    logging.info("Enabling motor driver by setting RESET high.")
    reset_line.set_value(1)  # Set RESET high to enable the driver
    sleep(0.1)

def disable_motor_driver():
    logging.info("Disabling motor driver by setting RESET low.")
    reset_line.set_value(0)  # Set RESET low to disable the driver
    sleep(0.1)

if __name__ == '__main__':
    try:
        # Ensure the motor driver is enabled
        enable_motor_driver()

        # Apply holding torque
        apply_holding_torque(holding_torque=True)
        logging.info("Holding torque applied. Motor should be holding position.")

        # Keep the script running to maintain the holding torque
        while True:
            sleep(1)  # Keep the application running to maintain the holding torque
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Exiting...")
    finally:
        cleanup()
        disable_motor_driver()  # Optionally disable the motor driver on exit
