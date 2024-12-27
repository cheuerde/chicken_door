#!/bin/bash
if ! curl -s http://localhost:5000/health > /dev/null; then
    sudo systemctl restart chicken-door.service
    echo "Service restarted at $(date)" >> /home/cheuer/logs/monitor.log
fi