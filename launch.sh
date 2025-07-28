#!/bin/bash
cd "$(dirname "$0")"
python3 ota_updater.py
python3 bot.py
