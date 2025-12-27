#!/usr/bin/sh

sudo screen -dmS mon -T xterm sh -c "python3.9 mon_rest.py"
sudo screen -dmS conf -T xterm sh -c "python3.9 conf_rest.py"
