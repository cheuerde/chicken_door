#!/usr/bin/env python3

import requests
import time
import subprocess
import logging
import os

# Set up logging
log_dir = os.path.expanduser("~/logs")
log_file = os.path.join(log_dir, "monitor.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def check_service():
    try:
        response = requests.get('http://localhost:5000/health', timeout=5)
        return response.status_code == 200
    except:
        return False

def restart_service():
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'chicken-door.service'])
        logging.info("Service restarted")
    except Exception as e:
        logging.error(f"Failed to restart service: {str(e)}")

def main():
    while True:
        if not check_service():
            logging.warning("Service appears to be down")
            restart_service()
        time.sleep(60)

if __name__ == '__main__':
    main()