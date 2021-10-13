# To access the db manually:
# sqlite3 /home/pi/rpiWebServer/testdata.db  ...Then .tables or PRAGMA table_info(table_name);
# To see what devices are using database: sudo fuser -v /home/pi/rpiWebServer/testdata.db
# To kill all processes using the file and eliminate locks: sudo fuser -k /home/pi/rpiWebServer/testdata.db
# TODO: Check if a database file even exists, and create one if necessary
import os
import threading, queue
import sqlite3 as lite
import pandas as pd
import sys
import serial
#import RPi.GPIO as GPIO
from time import sleep, strftime
from datetime import datetime
import asyncio
import websockets
import json, math
print("imports successful...")

# main() is the main (parent) thread, which starts the other thread(s)
# and maintains a socketio client to handle communication to/from the Flask server
async def main():
    # Set up queues to be shared by threads:
    q_changes = queue.Queue()  # queue to track requests from the browser
    q_outbox = queue.Queue()  # queue to track messages that should be sent to browser

    # The data_log dictionary specifies all of the variables that
    # will be logged and plotted. The keys are the database columns,
    # and the items are the SQL data types.
    data_log = {
        'timestamp': 'DATETIME',
        'elapsed_min': 'NUMERIC',
        'expt_id': 'TEXT',
        'mass1': 'NUMERIC',
        'sinedata': 'NUMERIC',
        'cosinedata': 'NUMERIC'
    }
    data_table_name = 'MyDataLog'  # The name of the table in the database

    # The device_params dictionary stores the current state of all device parameters/settings
    # This should include default settings, start values, PID settings, etc.)
    # A database table, ParamLog, will log changes to any of these variables.
    # The first 4 are mandatory: timestamp, log_interval, dev_id, device_active, expt_id. The rest can be customized.
    device_params = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'log_interval': 1.0,  # How often to log data to the database, in seconds
        'replot_interval': 5.0,
        'dev_id': 'dev01',
        'device_active': False,  # initially, device is not doing anything
        'expt_id': 'test01',
        'blue_on': True,
        'green_blink_int': 1.0,
        'blue_led_pin': 27,
        'green_led_pin': 17,
    }

    global ws_connected  # Flag to indicate whether socketio connection is active
    global dev_id, this_expt_id  # experiment id for the current experiment on this device
    sio_connected = False  # Intially, controller is not yet connected to socketio server
    this_device_id = device_params['dev_id']
    this_expt_id = device_params['expt_id']
    # Define a thread that controls the device:
    # #device_thread = threading.Thread(target=run_device,
    #                                  args=(1, q_changes, q_outbox, device_params, data_log, data_table_name)
    #                                  )

    #https://stackoverflow.com/questions/62177517/best-way-to-share-data-with-a-producer-coroutine-loop-from-the-python-websockets

    #asyncio.get_event_loop().run_until_complete(hello())


    uri = "ws://127.0.0.1:8000/ws/devices/1"
    async with websockets.connect(uri) as websocket:
        while True:
            msg = await(run_device())
            await websocket.send(msg)



# async def producer_handler():
#     uri = "ws://127.0.0.1:8000/ws/devices/1"
#     async with websockets.connect(uri) as websocket:
#         while True:
#             message = await producer()
#             await websocket.send(message)

async def send_stamp():
    uri = "ws://127.0.0.1:8000/ws/devices/1"
    async with websockets.connect(uri) as websocket:
        await asyncio.sleep(5)
        current_timestamp = datetime.now()
        print("Sending the current time: ", current_timestamp)
        return(current_timestamp)

async def hello():
    uri = "ws://127.0.0.1:8000/ws/devices/1"
    async with websockets.connect(uri) as websocket:
        name = input("What's your name? ")

        await websocket.send(name)
        print(f"Just sent> {name}")

        greeting = await websocket.recv()
        print(f"Just received> {greeting}")

async def run_device(): #thread_id, q_changes, q_out, dparams, datalog, data_table_name):
    uri = "ws://127.0.0.1:8000/ws/devices/1"
    print("New device started!")
    async with websockets.connect(uri) as websocket:
        while True:
            await asyncio.sleep(5)
            current_timestamp = datetime.now()
            print("Sending the current time: ", current_timestamp)
            return(str(current_timestamp))


if __name__ == "__main__":
    asyncio.run(main())





