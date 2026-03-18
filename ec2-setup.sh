#!/bin/bash
# Run this script ONCE on a fresh EC2 Ubuntu 22.04 instance
# Usage: bash ec2-setup.sh

set -e

echo "=== Installing system packages ==="
sudo apt-get update -y
sudo apt-get install -y git python3-pip python3-venv nginx certbot python3-certbot-nginx

echo "=== Cloning repo ==="
# Replace with your actual GitHub repo URL
git clone https://github.com/Tanusri12/Awesist.git /home/ubuntu/awesist
cd /home/ubuntu/awesist

echo "=== Creating Python virtual environment ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r app/requirements.txt

echo "=== Creating .env file ==="
echo "Paste your environment variables into /home/ubuntu/awesist/app/.env"
echo "You can edit it with: nano /home/ubuntu/awesist/app/.env"

echo "=== Creating systemd service ==="
sudo tee /etc/systemd/system/awesist.service > /dev/null <<EOF
[Unit]
Description=Awesist WhatsApp Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/awesist/app
EnvironmentFile=/home/ubuntu/awesist/app/.env
ExecStart=/home/ubuntu/awesist/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable awesist
sudo systemctl start awesist

echo ""
echo "=== Setup complete! ==="
echo "Check status with: sudo systemctl status awesist"
echo "View logs with:    sudo journalctl -u awesist -f"
