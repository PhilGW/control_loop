# To access the db manually:
# sqlite3 /home/pi/rpiWebServer/testdata.db  ...Then .tables or PRAGMA table_info(table_name);
# To see what devices are using database: sudo fuser -v /home/pi/rpiWebServer/testdata.db
# To kill all processes using the file and eliminate locks: sudo fuser -k /home/pi/rpiWebServer/testdata.db
# TODO: Check if a database file even exists, and create one if necessary
import os
import threading, queue
import sqlite3 as lite
import time
import pdb
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

    #Example of a class-based object for this:
    #https://stackoverflow.com/questions/65684730/what-is-the-pythonic-way-of-running-an-asyncio-event-loop-forever

    #https://stackoverflow.com/questions/62177517/best-way-to-share-data-with-a-producer-coroutine-loop-from-the-python-websockets
    print("Attempting a connection...")
    uri = "ws://127.0.0.1:8000/ws/devices/1"
    # ws = await websockets.connect(uri)
    #Open a websockets connection (make this into a function later):
    ws_connected = False
    while not ws_connected:
        try:
            ws = await websockets.connect(uri)
            ws_connected = True
        except Exception as err:
            print('Websockets could not connect. Will retry.')
            print(f"{type(err).__name__} was raised: {err}")
            time.sleep(5)

    #pdb.set_trace()
    my_controller = DeviceController(ws, 1)
    data_transmission_task = asyncio.create_task( transmit_data_periodically(ws) )
    listen_task = asyncio.create_task( listen_for_instructions(ws) )
    # data_transmission_task keeps sending out data every 5 seconds forever
    await data_transmission_task

    while True:
        # print("listening for instructions...")
        # await asyncio.sleep(3)
        new_msg = await listen_task
        print("message received in main(): ", new_msg)

    # try:
    #     loop.run_until_complete(task)
    # except asyncio.CancelledError:
    #     pass
    # except LostConnectionError:
    #     pass
        #code here for when the connection is lost... then it will automatically go back to the top

    #TODO: Use asyncio.gather to call all of the sensors at once and then send the full message
    # TODO: Write device-io functions so that they use context manager methods (__enter__() and __exit__()) and can therefor be used with 'with'
    #For import websockets, this works: Open the websocket, then keep it open:
    # async with websockets.connect(uri) as ws:
    #     while True:
    #         await asyncio.sleep(5)
    #         current_timestamp = datetime.now()
    #         print("Sending the current time: ", current_timestamp)
    #         await ws.send(str(current_timestamp))
    #         print("message sent!")
    #         await asyncio.sleep(3)
    #         response_msg = await ws.recv()
    #         print("message received!!", response_msg)

class DeviceController():
    #Initialization:
    def __init__(self, ws, device_id):
        self.device_id = device_id
        self.ws_connection = ws

    #Method to increment device_id:
    def increase_id(self, amt):
        self.device_id += amt
        print("new device_id: ", self.device_id)

async def listen_for_instructions(ws):
    response_msg = await ws.recv()
    print("message received in func: ", response_msg)
    return(response_msg)




async def transmit_data_periodically(ws):
    while True:
        print('Gathering sensor data...')
        [this_temp, this_pres] = await asyncio.gather(collect_temp_data(), collect_pres_data())
        current_timestamp = datetime.now()
        print("Sending current time and data...")
        new_data = str(current_timestamp) + " : " + str(this_temp) + " | " + str(this_pres)
        await ws.send(new_data)
        print("Just sent new data: ", new_data)
        await asyncio.sleep(5)

# def stop():
#     task.cancel()
# # async def process_incoming(ws):

async def collect_temp_data():
    time.sleep(0.3)
    return(47.2)

async def collect_pres_data():
    time.sleep(0.7)
    return(2.1)


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





