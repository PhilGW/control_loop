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
        'update_interval': 5.0,  # How often to log data to the database, in seconds
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
    my_controller = DeviceController(ws, 1, device_params=device_params) #Instantiate the controller
    listen_task = asyncio.create_task( listen_for_instructions(ws, my_controller) )


    await my_controller.run_controller_forever()  #Create the task and run it. This will need to happen once for each controller.
    await listen_task #Listen, and relay any data to the controllers

    # TODO: Use asyncio.gather to call all of the sensors at once and then send the full message
    # TODO: Write device-io functions so that they use context manager methods (__enter__() and __exit__()) and can therefor be used with 'with'

class DeviceController():
    #Initialization:
    def __init__(self, ws, device_id, device_params):
        self.device_id = device_id
        self.ws_connection = ws
        self.params = device_params

    #Method to increment device_id:
    def increase_id(self, amt):
        self.device_id += amt
        print("new device_id: ", self.device_id)

    def set_update_interval(self, new_interval):
        self.params['update_interval'] = new_interval

    def run_controller_forever(self):
        #Return a task to run the controller, by running the collect_and_transmit_periodically() method
        return(asyncio.create_task(self.collect_and_transmit_periodically(self.ws_connection)))

    #Method to run the controller forever, sending out data periodicially:
    async def collect_and_transmit_periodically(self, ws):
        while True:
            print('Gathering sensor data...')
            [this_temp, this_pres] = await asyncio.gather(collect_temp_data(), collect_pres_data())
            current_timestamp = str(datetime.now())
            new_data = dict([('topic', 'new_data'), ('device_id', self.device_id), ('timestamp', current_timestamp), ('temp1', this_temp), ('pres1', this_pres)])
            new_data_json = json.dumps(new_data)
            #new_data = "device_id=" + str(self.device_id) + "  " + str(current_timestamp) + " : " + str(this_temp) + " | " + str(this_pres)
            await ws.send(new_data_json)
            print("Just sent new data: ", new_data_json)
            print("now sleeping for " + str(self.params['update_interval']) + " seconds...")
            await asyncio.sleep(self.params['update_interval'])

    # async def get_controller_task(self, ws):
    #     return(self.)

async def listen_for_instructions(ws, device):
    while True:
        msg_as_text = await ws.recv()
        msg = json.loads(msg_as_text)
        print("New message received: ", msg)
        topic = msg.pop('topic')
        if topic == 'receipt_confirmation':
            print('Receipt of data confirmed by server!')
        elif topic == 'hi':
            print("just sayin hey")
        elif topic == 'param_update':
            print('Got the request!')
            #TODO: make sure the update interval is actually valid
            if msg['param_name'] == 'update_interval':
                device.set_update_interval(float(msg['param_value']))

        #device.increase_id(3)


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

if __name__ == "__main__":
    # main()
    asyncio.run(main())


# try:
    #     loop.run_until_complete(task)
    # except asyncio.CancelledError:
    #     pass
    # except LostConnectionError:
    #     pass
        #code here for when the connection is lost... then it will automatically go back to the top


