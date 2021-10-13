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
# def main():

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

    # Define a thread that controls the device:
    # #device_thread = threading.Thread(target=run_device,
    #                                  args=(1, q_changes, q_outbox, device_params, data_log, data_table_name)
    #                                  )

    #https://stackoverflow.com/questions/62177517/best-way-to-share-data-with-a-producer-coroutine-loop-from-the-python-websockets

    #asyncio.get_event_loop().run_until_complete(hello())
    #await hello()
    # q_outbox = asyncio.Queue()
    uri = "ws://127.0.0.1:8000/ws/devices/1"
    # async with websockets.connect(uri) as websocket:
    #     while True:
    #         msg = await(run_device())
    #         await websocket.send(msg)
    async with websockets.connect(uri) as ws:
        while True:
            await asyncio.sleep(5)
            current_timestamp = datetime.now()
            print("Sending the current time: ", current_timestamp)
            await ws.send(str(current_timestamp))
            print("message sent!")
            await asyncio.sleep(3)
            response_msg = await ws.recv()
            print("message received!!", response_msg)

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
    async with websockets.connect(uri) as websocket: #Connection/handshake occurs here
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
    # main()
    asyncio.run(main())





