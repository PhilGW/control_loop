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
import RPi.GPIO as GPIO
from time import sleep, strftime
from datetime import datetime
import socketio
import json, math


# main() is the main (parent) thread, which starts the other thread(s)
# and maintains a socketio client to handle communication to/from the Flask server

#def main():
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
    data_table_name = 'FermDataLog'  # The name of the table in the database

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
    param_df = pd.DataFrame.from_records(device_params, index=[0])
    dbcon = lite.connect("/home/pi/rpiWebServer/testdata.db")
    cur = dbcon.cursor()
    param_df.to_sql('ParamLog', con=dbcon, if_exists='append')  # Write to database
    # Long term, the parameters could get converted to widgets automatically in the browser form at /startup...

    global sio_connected  # Flag to indicate whether socketio connection is active
    global dev_id, this_expt_id  # experiment id for the current experiment on this device
    sio_connected = False  # Intially, controller is not yet connected to socketio server
    this_device_id = device_params['dev_id']
    this_expt_id = device_params['expt_id']
    sio = socketio.Client()  # Instantiate a new socketio client
    # Define a thread that controls the device:
    device_thread = threading.Thread(target=run_device,
                                     args=(1, q_changes, q_outbox, device_params, data_log, data_table_name)
                                     )

    @sio.on('connect')  # Special reserved event name for connection
    def on_connection():
        global sio_connected
        print("Successfully connected to socketio server.")
        # sio.emit('connected_device_info', {'dev_id': this_device_id, 'expt_id': this_expt_id, 'db_table': 'FermDataLog'})
        sio_connected = True

    @sio.on('disconnect')  # Special reserved event name for disconnect
    def on_disconnection():
        global sio_connected
        print("Disconnected from socketio server.")
        # sio.emit('disconnected_device_info', {'dev_id': this_device_id, 'expt_id': this_expt_id, 'db_table': 'FermDataLog'})
        sio_connected = False

    @sio.on('start_run')
    def begin_run(start_order):
        print("Got a start_run command from webserver!")
        device_params['device_active'] = True

    # Note: Stopping the run simply occurs when the device_thread is allowed to end

    # If the browser requests a parameter change, add it to the change queue
    @sio.on('change_params')
    def change_parameters(change_req):
        print("Got a request to change_params from webserver!")
        print("change_req: ", change_req)
        q_changes.put(change_req)  # Add the dictionary of run parameters to the queue

    while True:
        # If no socketio connection exists, make one:
        if not sio_connected:  # If not connected to socketio server, try to connect
            try:
                sio.connect('http://0.0.0.0:4000')  # Listen on channel 4000 forever
                # The docs assure: "When a client connection to the server is established... background tasks will be spawned to handle the connection. The application on the main thread is free to do any work."
            except:
                print('Socket-client thread could not connect. Will retry.')
                sleep(5)
        # If the socketio connection is up, proceed:
        else:
            # If the device is running, handle its outgoing messages:
            if device_thread.is_alive():
                # This Queue.get() is a BLOCKING call, i.e. execution stops here until the device adds a message to the queue
                msg_to_emit = q_outbox.get(block=True, timeout=None)
                print("emitting message: ", msg_to_emit)
                sio.emit(msg_to_emit[0], msg_to_emit[1])
            # If the device is not running:
            else:
                # If it SHOULD be running, start up the thread:
                for i in q_changes.queue:  # Look through the queue to see if there is a request from the browser to activate the device:
                    if 'device_active' in i and i['device_active'] == 1:
                        print("Trying to start a new device...")
                        device_thread.start()
                # Otherwise, keep waiting for the start command.
                else:
                    print("Device thread is not active. Waiting for a new start command.")
                    sio.sleep(3)

                # The function which controls lab devices:


def run_device(thread_id, q_changes, q_out, dparams, datalog, data_table_name):
    print("New device started!")
    # TODO: Check to make sure database connection is sound before writing to database (more important if/when database is on another device or in the cloud)
    dparams['device_active'] = True  # Indicate that the device is now running
    params_changed = True  # flag to track whether any parameter changes need to be logged

    setup_hardware(dparams)
    serial0 = serial.Serial("/dev/ttyS0", 9600,
                            timeout=0.2)  # Open serial connection to balance. NOTE: This ttyS0 port is not activated by default. In terminal, type sudo raspi-config and go to "5 Interfacing options" -> "P6 Serial" -> NOT accessible over serial, turn port ON
    # Open a connection to the sqlite database:
    dbcon = lite.connect("/home/pi/rpiWebServer/testdata.db")
    cur = dbcon.cursor()

    # Create an empty table in the database, if one doesn't exist already:
    datalog_df = pd.DataFrame(columns=datalog.keys())  # Create an empty dataframe
    datalog_df.loc[0, 'timestamp'] = datetime.now()
    datalog_df.to_sql(data_table_name, con=dbcon, dtype=datalog, if_exists='append')

    now = datetime.now()
    time0 = now.timestamp()  # Log starting time (seconds since 1970-01-01)
    t_last_log = time0
    t_last_replot = time0
    # The main loop that takes inputs from the sensors, performs any
    # necessary processing, and logs output variables to the database:
    while dparams['device_active']:
        try:  # This try-except block closes down the database connection gracefully

            # Check the queue to see if any parameter changes have been requested in the browser:
            while not q_changes.empty():
                params_changed = True
                change_req = q_changes.get()
                print(change_req)
                for k in change_req.keys():  # Loop through all the keys in the change request
                    dparams[k] = change_req[k]  # Update device_params with the new value

            # Make adjustments to hardware i/o here:
            mass = get_mass(serial0)
            GPIO.output(dparams['blue_led_pin'],
                        dparams['blue_on'])  # Set the blue LED to whatever the value of 'blue_on' is:

            # This section handles datalogging:
            now = datetime.now()
            elapsed_min = (now.timestamp() - time0) / 60.0  # elapsed time in minutes
            # If it's been more than ['log_interval'] seconds, log data to the database
            # NOTE: Multiple threads are another approach that would work here, but would add additional complexity
            if (now.timestamp() - t_last_log) > dparams['log_interval']:
                t_last_log = now.timestamp()
                # Flip the state of the green led pin every time data are logged:
                GPIO.output(dparams['green_led_pin'], not GPIO.input(dparams['green_led_pin']))
                new_row_df = pd.DataFrame(columns=datalog.keys())  # Create an empty dataframe
                # Here we load up new_row_df with all data that will be saved to the database:
                new_row_df.loc[0, 'timestamp'] = now
                new_row_df.loc[0, 'expt_id'] = dparams['expt_id']
                new_row_df.loc[0, 'elapsed_min'] = elapsed_min
                new_row_df.loc[0, 'mass1'] = mass
                new_row_df.loc[0, 'sinedata'] = 10.0 * math.sin(elapsed_min) + 11.0
                new_row_df.loc[0, 'cosinedata'] = 10.0 * math.cos(elapsed_min) + 11.0
                print(new_row_df)
                new_row_df.to_sql('DataLog', con=dbcon, dtype=datalog, if_exists='append')
                # If any parameters have been changed via the web app, log the change to the database (ParamLog table)
                dbcon.commit()  # Commit changes to database. TODO: Is this needed for pd.to_sql?
            # Send a command to refresh all browsers:
            if (now.timestamp() - t_last_replot) > dparams['replot_interval']:
                t_last_replot = now.timestamp()
                q_out.put(['datalog_updated', {'data': '1'}])  # Format: ['sio event name', {'key': 'data'}]
            if params_changed:
                print("params changed, writing to database...")
                param_df = pd.DataFrame.from_records(dparams,
                                                     index=[0])  # Write all parameters as another row to the database
                param_df['timestamp'] = now  # The timestamp is updated just prior to writing
                param_df.to_sql('ParamLog', con=dbcon, if_exists='append')
                params_changed = False  # Remains false until the next change
                dbcon.commit()  # Commit changes to database
                q_out.put(['params_updated', {'data': '1'}])  # Format: ['sio event name', {'key': 'data'}]
                if not dparams['device_active']:
                    print("Device shutting down.")
                    return ('Device shut down.')  # End this thread
        # To prevent database lockouts, close the program with Ctrl-C in the terminal window. This closes the database.
        except KeyboardInterrupt:
            print("Closing sqlite database connection.")
            dbcon.close()


# Set up hardware according to device-parameters dictionary:
def setup_hardware(dparams):
    # Hardware setup for LEDs:
    GPIO.setmode(GPIO.BCM)  # Set pin-numbering scheme
    GPIO.setwarnings(False)
    GPIO.setup(dparams['green_led_pin'], GPIO.OUT)
    GPIO.setup(dparams['blue_led_pin'], GPIO.OUT)
    # Initialize LEDs (green on, blue off)
    GPIO.output(dparams['green_led_pin'], GPIO.HIGH)
    GPIO.output(dparams['blue_led_pin'], GPIO.LOW)


# Query the EJ-6100 balance for the current mass and return it as a float
# TODO: Handle situation where balance is not on or not responsive
def get_mass(serial_port):
    serial_port.write(b"Q\r\n")  # Query the balance for the current mass by sending a Q
    new_line = serial_port.readline().decode('utf-8')  # Read one line
    # Make sure the 3rd-to-last character is a 'g', to confirm the units are correct
    # and the entire message came in. If not, return None:
    try:
        if new_line[-3] == "g":
            return (float(new_line[3:12]))  # Return mass as float
        else:
            return (None)
    except:
        return (None)


def tare_balance(serial_port):
    serial_port.write(b"Z\r\n")  # Tare the balance by sending a Z
    # wait for a zero reading to indicate tare is complete:
    zeroed = False
    while zeroed is False:
        mass = get_mass(serial_port)
        if mass < 0.2 and mass > -0.2: zeroed = True
        sleep(0.1)


if __name__ == "__main__":
    main()





