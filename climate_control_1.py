#!/usr/bin/env python3
"""
Panasonic AirCon 1 Climate Control Automation Service
Optimized for Raspberry Pi systemd deployment.

Features:
- Restricted execution entirely inside a defined schedule window.
- Wi-Fi presence detection (Ping check) before enabling climate loops.
- Consecutive cold checks (10-minute buffer delay) to protect the compressor.
- Decoupled configuration variables for easy updates and GitHub sharing.
"""

import time
from datetime import datetime, time as datetime_time
import pcomfortcloud
from pcomfortcloud import constants
import os

# ==========================================
#               SETTINGS PANEL
# ==========================================
DEVICE_INDEX = 0        # 0 = Master Room, 1 = Second Room
TEMP_LIMIT_LOW = 20.0   # Turn heating ON if it drops to or below this
TEMP_LIMIT_HIGH = 23.0  # Turn heating OFF once it reaches or exceeds this
TARGET_HEAT_TEMP = 22.0 # Target setpoint for the heater
CHECK_INTERVAL = 120    # Check every 2 minutes

START_TIME = "03:00"    # start time (24-Hour Format "HH:MM")
END_TIME = "07:30"      # end time (24-Hour Format "HH:MM")
PHONE_IP = "192.168.1.xxx"  #Checking at home or not by my phone's static IP

# Configuration
PANASONIC_USERNAME = "YOUR_EMAIL_HERE"
PANASONIC_PASSWORD = "YOUR_PASSWORD_HERE"
DEVICE_INDEX = 0  # Targets AirCon #1 in your account list
# ==========================================

# Rule 2: Force the AC to turn OFF at this exact time
SHUTOFF_TIME = END_TIME # can set a time, eg: "08:00"

# Path to the log file
LOG_FILE_PATH = "/home/admin/aircon-automation/climate1.log"

# Add this above your thresholds
cold_counter = 0
DELAY_COUNTS = 2  # Must be cold for 2 checks (10 mins) before turning ON

def log_activity(message):
    """Helper function to write timestamps and actions to a local log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}\n"

    # Print to console (so systemd/journalctl still catches it)
    print(log_entry.strip())

    # Append to the log file
    try:
        with open(LOG_FILE_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to log file: {e}")

def is_phone_home(phone_ip):
    # Sends 1 ping packet. Returns True if phone responds.
    response = os.system(f"ping -c 1 -W 1 {phone_ip} > /dev/null 2>&1")
    return response == 0

def is_time_between(start_str, end_str, now_time):
    """Helper to check if 'now_time' falls between start and end (handles overnight wraps)"""
    start = datetime.strptime(start_str, "%H:%M").time()
    end = datetime.strptime(end_str, "%H:%M").time()

    if start <= end:
        return start <= now_time <= end
    else: # Overnight window (e.g., 21:00 to 06:00)
        return now_time >= start or now_time <= end


def run_automation():
    # 1. Initialize client here at the very start of the function
    print("Starting Panasonic Scheduled Heater Automation (Quiet Mode)...")
    try:
        session = pcomfortcloud.Session(USERNAME, PASSWORD)
        session.login()
        client = pcomfortcloud.ApiClient(session)
    except Exception as e:
        log_activity(f"CRITICAL -> Initial login failed: {e}")
        return

    cold_counter = 0
    log_activity(f"SYSTEM -> Service initialized. Target Active Window: {START_TIME} - {END_TIME}")

    while True:
        now = datetime.now()
        current_time = now.time()
        stop_time = datetime.strptime(END_TIME, "%H:%M").time()

        # --- STEP 1: TIME GUARD CLAUSE ---
        if not is_time_between(START_TIME, END_TIME, current_time):
            if now.minute == 0:
                log_activity(f"IDLE -> Outside operational window ({START_TIME}-{END_TIME}). Processing suspended.")
            cold_counter = 0
            time.sleep(CHECK_INTERVAL)
            continue

        # --- STEP 2: ACTIVE MONITORING ZONE ---
        try:
            # 2. Safety Check: If the client dropped or failed to init, try re-logging in
            if client is None:
                client = login_to_panasonic()
                if client is None:
                    log_activity("ERROR -> API client is still undefined. Retrying next cycle.")
                    time.sleep(60)
                    continue

            user_home = is_phone_home(PHONE_IP)

            # --- Fetch your real live AC data here ---
            devices = client.get_devices()
            device_id = devices[DEVICE_INDEX]['id']
            status = client.get_device(device_id)

            is_on = status['parameters']['power'] == pcomfortcloud.constants.Power.On
            current_temp = status['parameters']['temperatureInside']
            is_heating = status['parameters']['mode'] == pcomfortcloud.constants.OperationMode.Heat

            # =========================================================
            # 3. MORNING HARD STOP (Moved inside the try block for device_id safety)
            # =========================================================
            if now.hour == stop_time.hour and now.minute <= (stop_time.minute + 5):
                if device_id:
                    log_activity(f"ACTION -> Morning Hard Stop reached. Forcing Total AC Power OFF.")
                    client.set_device(device_id, power=constants.Power.Off)
                cold_counter = 0
                time.sleep(300)
                continue
                
            user_home = is_phone_home(PHONE_IP)

            # --- Fetch your real live AC data here ---
            devices = client.get_devices()
            device_id = devices[DEVICE_INDEX]['id']
            status = client.get_device(device_id)

            is_on = status['parameters']['power'] == pcomfortcloud.constants.Power.On
            current_temp = status['parameters']['temperatureInside']
            is_heating = status['parameters']['mode'] == pcomfortcloud.constants.OperationMode.Heat

            # =========================================================
            # 3. MORNING HARD STOP (Moved inside the try block for device_id safety)
            # =========================================================
            if now.hour == stop_time.hour and now.minute <= (stop_time.minute + 5):
                if device_id:
                    log_activity(f"ACTION -> Morning Hard Stop reached. Forcing Total AC Power OFF.")
                    client.set_device(device_id, power=constants.Power.Off)
                cold_counter = 0
                time.sleep(300)
                continue
            
            # =========================================================
            # 4. CHOOSE CASE A OR CASE B BASED ON TEMP
            # =========================================================

            # --- CASE A: Room is Cold -> Turn Heat back ON ---
            if current_temp <= TEMP_LIMIT_LOW:
                if user_home:
                    if not is_on or not is_heating:
                        cold_counter += 1
                        log_activity(f"CHECK -> Phone detected. Temp is low ({current_temp}°C). Delay: {cold_counter}/{D>

                        if cold_counter >= DELAY_COUNTS:
                            log_activity(f"ACTION -> Sustained cold. Switching COMMAND -> HEATER ON (Quiet Mode).")
                            client.set_device(
                                device_id,
                                power=pcomfortcloud.constants.Power.On,
                                mode=pcomfortcloud.constants.OperationMode.Heat,
                                temperature=TARGET_HEAT_TEMP,
                                fanspeed=pcomfortcloud.constants.FanSpeed.Auto,
                                eco=pcomfortcloud.constants.EcoMode.Quiet,
                                # Keep your perfect Heat Mode position
                                airSwingVertical=pcomfortcloud.constants.AirSwingUD.Mid
                            )
                            cold_counter = 0
                else:
                    log_activity(f"INFO -> Target Temp cold ({current_temp}°C), but user phone is AWAY. Skipping activat>
                    cold_counter = 0

            # --- CASE B: Room Reached Ceiling Temperature -> IDLE ---

            elif current_temp >= TEMP_LIMIT_HIGH and is_on:
                if is_heating:
                    log_activity(f"ACTION -> Target reached ({current_temp}°C >= {TEMP_LIMIT_HIGH}°C). Switching to IDLE>
                    client.set_device(
                        device_id,
                        power=pcomfortcloud.constants.Power.On,
                        mode=pcomfortcloud.constants.OperationMode.Fan,
                        fanspeed=pcomfortcloud.constants.FanSpeed.Auto,
                        eco=pcomfortcloud.constants.EcoMode.Quiet,
                        # --- THE FIX: Drop it 1 step lower to counter the automatic firmware rise ---
                        airSwingVertical=pcomfortcloud.constants.AirSwingUD.UpMid
                    )
                cold_counter = 0

            else:
                current_temp > TEMP_LIMIT_LOW
                cold_counter = 0
                                                                                                                       
        except Exception as e:
            log_activity(f"ERROR -> Exception caught in dynamic loop runtime: {e}")
            # If an explicit authentication error occurs, flag client as None to trigger a login retry
            if "login" in str(e).lower() or "auth" in str(e).lower():
                client = None
            time.sleep(60)
            continue

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        run_automation()
    except KeyboardInterrupt:
        log_activity("SYSTEM STOP: Automation stopped manually by user.")
