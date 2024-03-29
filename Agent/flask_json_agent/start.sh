#!/bin/bash


# -----------------------------------------------------------------------------
# Setup:
# -----------------------------------------------------------------------------
# mkdir -p ~/agent/git
# cd agent/git
# First clone repository
# git clone https://github.com/Micronaet/micronaet-industria40

# Create Virtual Env:
# python3 -m venv ./venv

# mkdir ~/agent/flask_json_i40
# cd ~/agent/flask_json_i40
# ln -s ../git/micronaet-industria40/Agent/flask_json_agent/app.py .

# ~/agent/venv/bin/pip3 install -r ~/agent/git/micronaet-industria40/Agent/flask_json_agent/requirements.txt

# -----------------------------------------------------------------------------

# Update repo:
cd ~/agent/git/micronaet-industria40
git pull

# Run Flask JSONM Agent:
cd ~/agent/flask_json_i40

~/agent/venv/bin/python3 ./app.py

