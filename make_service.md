# Setting up Chicken Door Control as a System Service

This guide describes how to set up the Chicken Door Control application as a systemd service that starts automatically on boot and recovers from crashes.

## 1. Create the Service File

Create the systemd service file:

```bash
sudo nano /etc/systemd/system/chicken-door.service
```

Add the following content (replace `${USER}` with your username):

```ini
[Unit]
Description=Chicken Door Control Web Application
After=network.target

[Service]
User=${USER}
Group=video
WorkingDirectory=/home/${USER}/chicken_door/web_app
ExecStart=/usr/bin/python3 /home/${USER}/chicken_door/web_app/app.py
Restart=always
RestartSec=10
StandardOutput=append:/home/${USER}/logs/chicken_door_service.log
StandardError=append:/home/${USER}/logs/chicken_door_service.log

# Make sure the log directory exists
ExecStartPre=/bin/mkdir -p /home/${USER}/logs
# Ensure proper permissions
ExecStartPre=/bin/chown ${USER}:${USER} /home/${USER}/logs

[Install]
WantedBy=multi-user.target
```

## 2. Set Up Directory Structure and Permissions

```bash
# Create necessary directories
mkdir -p ~/chicken_door/web_app
mkdir -p ~/logs

# Set proper permissions
chmod 755 ~/chicken_door
chmod 755 ~/chicken_door/web_app
chmod 755 ~/logs

# Add user to video group for camera access
sudo usermod -a -G video ${USER}
```

## 3. Set Up Log Rotation

Create a log rotation configuration:

```bash
sudo nano /etc/logrotate.d/chicken-door
```

Add the following content (replace `${USER}` with your username):

```
/home/${USER}/logs/motor_light_control.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ${USER} ${USER}
}

/home/${USER}/logs/chicken_door_service.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 ${USER} ${USER}
}
```

## 4. Create Monitoring Script

Create a monitoring script:

```bash
nano ~/chicken_door/monitor.py
```

Add the following content:

```python
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
```

Make the script executable:

```bash
chmod +x ~/chicken_door/monitor.py
```

## 5. Create Monitor Service

Create a service file for the monitor:

```bash
sudo nano /etc/systemd/system/chicken-door-monitor.service
```

Add the following content (replace `${USER}` with your username):

```ini
[Unit]
Description=Chicken Door Monitor Service
After=chicken-door.service

[Service]
User=${USER}
WorkingDirectory=/home/${USER}/chicken_door
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/usr/bin/python3 /home/${USER}/chicken_door/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 6. Set Up Permissions for Service Restart

Allow the user to restart the service without a password by adding a sudoers entry:

```bash
sudo visudo -f /etc/sudoers.d/chicken-door
```

Add the following content (replace `${USER}` with your username):

```
${USER} ALL=NOPASSWD: /bin/systemctl restart chicken-door.service
```

## 7. Enable and Start Services

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable chicken-door.service
sudo systemctl enable chicken-door-monitor.service

# Start services
sudo systemctl start chicken-door.service
sudo systemctl start chicken-door-monitor.service
```

## 8. Verify Installation

```bash
# Check service status
sudo systemctl status chicken-door.service
sudo systemctl status chicken-door-monitor.service

# Check if application is listening on port 5000
sudo netstat -tulpn | grep 5000

# Monitor logs
tail -f ~/logs/motor_light_control.log
tail -f ~/logs/chicken_door_service.log
tail -f ~/logs/monitor.log
```

## 9. Backup Configuration

Create backups of your working configuration:

```bash
# Backup service files
sudo cp /etc/systemd/system/chicken-door.service /etc/systemd/system/chicken-door.service.backup
sudo cp /etc/systemd/system/chicken-door-monitor.service /etc/systemd/system/chicken-door-monitor.service.backup

# Backup application
cd ~/chicken_door
tar -czf chicken_door_backup.tar.gz web_app/
```

## Troubleshooting

1. If the service fails to start, check the logs:
```bash
sudo journalctl -u chicken-door.service -n 50 --no-pager
```

2. If the monitor fails to start, check its logs:
```bash
sudo journalctl -u chicken-door-monitor.service -n 50 --no-pager
```

3. Common issues:
   - Permission problems: Make sure all directories and files have correct ownership
   - GPIO access: Ensure the user is in the correct groups
   - Camera access: Check video group membership
   - Port conflicts: Make sure nothing else is using port 5000

## Maintenance

1. To update the application:
```bash
# Stop services
sudo systemctl stop chicken-door-monitor.service
sudo systemctl stop chicken-door.service

# Update files
# ... update your files ...

# Start services
sudo systemctl start chicken-door.service
sudo systemctl start chicken-door-monitor.service
```

2. To view logs:
```bash
# View application logs
tail -f ~/logs/motor_light_control.log

# View service logs
tail -f ~/logs/chicken_door_service.log

# View monitor logs
tail -f ~/logs/monitor.log
```