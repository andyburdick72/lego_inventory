#!/bin/zsh
cd ~/Code/GitHub/andyburdick72/lego_inventory || exit
source .venv/bin/activate
python3 src/app/server.py