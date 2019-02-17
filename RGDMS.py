#
# Remote Garage Door Management System "RGDMS"
# Written by: Bill Klinefelter
# bill.klinefelter@gmail.com
#
from googlevoice import Voice
import traceback
#from bs4 import BeautifulSoup
import BeautifulSoup
import string
import time
import RPi.GPIO as GPIO
import datetime
import os
import sys
import sqlite3 as lite
from time import sleep
from RGDMS_Door import RGDMS_Door
from RGDMS_User import RGDMS_User
import os.path
#--------------------------------------------------------------------
# set up log and error files
stdout_fsock = open('/tmp/RGDMS.log', 'w')
stdout_fsock.close()
stderr_fsock = open('/tmp/RGDMS.err', 'w')
stderr_fsock.close()
save_stdout = sys.stdout
save_stderr = sys.stderr

def logging_open() :
    # redirect all stdout and stderr output to logfile
    save_stdout = sys.stdout
    stdout_fsock = open('/tmp/RGDMS.log', 'a')
    sys.stdout = stdout_fsock
    save_stderr = sys.stderr
    stderr_fsock = open('/tmp/RGDMS.err', 'a')
    sys.stderr = stderr_fsock

def logging_close() :
    stdout_fsock.close()
    stderr_fsock.close()
    sys.stdout = save_stdout
    sys.stderr = save_stderr
#--------------------------------------------------------------------

# global DB variables
RGDMS_DB="/DB/RGDMS_events.db"
alarm_alert_msg = ""

# if db doesn't already exist, create it
if os.path.isfile(RGDMS_DB) == False:
    # init database table 'data'
    con = lite.connect(RGDMS_DB)
    cur = con.cursor()
    cur.execute("CREATE TABLE data (id INTEGER PRIMARY KEY,e_date INTEGER,s_date TEXT,alert TEXT,alert_sent INTEGER,garage_open_sensor INTEGER,garage_closed_sensor INTEGER)")
    cur.close()

#-----------------------------------------------------------------------------------------------------
# this was the code borrowed from "SMS test via Google Voice"
#   John Nagle
#   nagle@animats.com

def extractsms(htmlsms) :
    """
    extractsms  --  extract SMS messages from BeautifulSoup tree of Google Voice SMS HTML.

    Output is a list of dictionaries, one per message.
    """
    msgitems = []                         # accum message items here
    #   Extract all conversations by searching for a DIV with an ID at top level.
    tree = BeautifulSoup.BeautifulSoup(htmlsms)        # parse HTML into tree
    conversations = tree.findAll("div",attrs={"id" : True},recursive=False)
    for conversation in conversations :
        #   For each conversation, extract each row, which is one SMS message.
        rows = conversation.findAll(attrs={"class" : "gc-message-sms-row"})
        for row in rows :                    # for all rows
            #   For each row, which is one message, extract all the fields.
            msgitem = {"id" : conversation["id"]}     # tag this message with conversation ID
            spans = row.findAll("span",attrs={"class" : True}, recursive=False)
            for span in spans :                  # for all spans in row
                cl = span["class"].replace('gc-message-sms-', '')
                msgitem[cl] = (" ".join(span.findAll(text=True))).strip()   # put text in dict
            msgitems.append(msgitem)              # add msg dictionary to list
    return msgitems
#----------------------------------------------------------------------------------------------------

#----------------------------------------------------------------------------------------------------
# Adding some robustness to the SMS send function
# Since GVoice seems to limit number of msgs over time
# Bill Klinefelter
# bill.klinefelter@gmail.com
# return 1 if success, 0 if failure

def RGDMS_send_SMS(to_phone_number, message) :
    global int_time_of_SMS_failure
    int_current_time = int(time.time())
    now = datetime.datetime.now()
    elapsed_time_since_SMS_failure = int_current_time - int_time_of_SMS_failure
    if (elapsed_time_since_SMS_failure > 300):
        try:
            voice.send_sms(to_phone_number, message)
        except Exception:
            traceback.print_exc(file=sys.stdout)
            # if failure to send SMS, wait 5 mins before trying again (to avoid flooding requests)
            int_time_of_SMS_failure = int_current_time
            print now.strftime("%a %b %d %H:%M:%S %Z %Y") + ": failed to send SMS to: " + to_phone_number + " with message: " + message
            return 0
        print now.strftime("%a %b %d %H:%M:%S %Z %Y") + ": successfully sent SMS to: " + to_phone_number + " with message: " + message
        return 1  
    else:
        print now.strftime("%a %b %d %H:%M:%S %Z %Y") + ": waiting " + (300-elapsed_time_since_SMS_failure) + " seconds to try sending SMS again..."
        return 0

#----------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------
# Parse text file for valid users list
# Bill Klinefelter
# bill.klinefelter@gmail.com
# return list of users
def parse_user_list():
    user_file = open ("/home/pi/RGDMS/valid_users_list.txt", "r")
    user_list = []
    for line in user_file:
        if '#' in line:
            continue
        else:
            user_name, phone_number = line.split(',', 1)
            new_user = RGDMS_User(phone_number.strip(), 1, user_name.strip())
            user_list.append(new_user)
            DEBUG("new user created!")
            DEBUG("user name: "+ new_user.getUserName())
            DEBUG("user phone number: "+ new_user.getPhoneNumber())
    user_file.close()
    return user_list

#----------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------
# Scan DB and see if any alert messages are queued to send to users
# Bill Klinefelter
# bill.klinefelter@gmail.com
# query alarm alert database to see if any new alerts occurred

def send_queued_alerts(user_list):
    con = lite.connect(RGDMS_DB)
    with con:
        con.row_factory = lite.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM data WHERE alert_sent='0'")

        rows = cur.fetchall()
        alarm_alert_msg = ""
        for row in rows:
            print "%s %s" % (row["s_date"], row["alert"])
            if alarm_alert_msg == "": 
                alarm_alert_msg = row["s_date"] + " : " + row["alert"]
            else:
                alarm_alert_msg += "\n" + row["s_date"] + " : " + row["alert"]
                # Once the alerts have been sent to those that have it enabled, mark the row in the db that it has been sent
            cur.execute("UPDATE data SET alert_sent = 1 WHERE id = ?", (row["id"],))
            con.commit()

        send_success=0

        for user in user_list:
            if user.getEnabled() and (alarm_alert_msg != ""):
                send_success=RGDMS_send_SMS(user.getPhoneNumber(), alarm_alert_msg)
                time.sleep(5)
            else:
                send_success=1


        # consider it successfully sent if any receivers got it (to avoid a duplicate send)
        # if none were successful, keep the alarm_alert_msg buffer for the next time this part of code is reached.
        # TBD: possibly clean up this logic
        if (send_success == 1):
            # Once the alerts have been sent to those that have it enabled, remove the list of message from the queue to send
            alarm_alert_msg = ""
#----------------------------------------------------------------------------------------------------
#debug_enabled = True
debug_enabled = False
def DEBUG(text):
    if debug_enabled == True:
      print text


logging_open()

DEBUG("start")
# store pid of process in /tmp to control if this script hangs
pid = str(os.getpid())
pidfile = "/tmp/RGDMS.pid"
file(pidfile, 'w').write(pid)

DEBUG("setup RPi GPIO outputs")
#setup RPi GPIO outputs
GPIO.setmode(GPIO.BCM)

DEBUG("create list of doors")
# create list of doors
Doors = []
# add Garage Door objects
Door_A = RGDMS_Door(4, 24, 25, 'Main')
Doors.append(Door_A)
#Door_B = RGDMS_Door(17, 25, 22, 'B')
#Doors.append(Door_B)

DEBUG("create valid users list")
# create valid users list
valid_users = []
DEBUG("read in users file to populate valid users list")
# read in users file to populate valid users list
valid_users = parse_user_list()

#init global SMS fail variable
int_time_of_SMS_failure=-1

# Init of script
# wait until internet is responding before trying to connect
print "pinging google.com until there is a response..."
hostname = "google.com"
response = os.system("ping -c 1 " + hostname + ">/null")
while (response !=0):
    time.sleep(2)
    print "google.com is not responding"
    response = os.system("ping -c 1 " + hostname + ">/null")
print "got a response!"

# connect to Google Voice    
voice = Voice()
print "logging into Google Voice..."
voice.login()
print "login success"

logging_close()


# main loop
while (1==1):
    logging_open()
    DEBUG ("inside loop")
    # update process heartbeat
    heartbeat = datetime.datetime.now().strftime('%s')
    heartbeatfile = "/tmp/RGDMS.heartbeat"
    file(heartbeatfile, 'w').write(heartbeat)
    
    # attempt to read any new txt msgs from google voice
    DEBUG("attempt to read any new txt msgs from google voice")
    try:
        voice.sms()
    except Exception:
        traceback.print_exc(file=sys.stdout)
        sys.exit(0)
    msgitems = extractsms(voice.sms.html)
    num_msgs=len(msgitems)

    DEBUG("connect to db")
    # connect to db
    con_db = lite.connect(RGDMS_DB)
    cur_db = con_db.cursor()

    # check if each door of the garage has been open for more than 10 minutes
    for door in Doors:
        if door.open_since > 0:
            if GPIO.input(door.INPUT_Closed_Pin) == False:
                now = datetime.datetime.now()
                print now.strftime("%a %b %d %H:%M:%S %Z %Y") + ": resetting open_since timer for door \"" + door.name + "\", because it is closed"
                door.open_since=-1
            else:
                # get current time
                int_current_time = int(time.time())
                now = datetime.datetime.now()
                str_current_time = now.strftime("%a %b %d %H:%M:%S %Z %Y")
                # calculate elapsed time (seconds)
                elapsed_time = int_current_time - door.open_since
	        DEBUG("current time = "+str(int_current_time)+", "+door.name+ " open_since= "+ str(door.open_since)+ ", elapsed_time= "+ str(elapsed_time))
                # if time elapsed since door opened is > 10 mins (600 sec) and we haven't alerted this yet, send an alert
                if elapsed_time > 600 and door.ten_min_alert_sent == False:
                    str_alert_msg = "FYI: Door \"" + door.name + "\" of the garage has been open for more than 10 minutes"
                    print "%s : %s" % (str_current_time, str_alert_msg)
                    cur_db.execute("insert into data (e_date,s_date,alert,alert_sent) values(?,?,?,?)", (int_current_time,str_current_time,str_alert_msg,0))
                    door.ten_min_alert_sent=True
        # test GPIO sensor inputs
        door.test_GPIO_inputs()
        # read persistent data open/close state files
        door.read_PD_file()
        # check to see if an outside source has changed the state of the door
        door.check_for_state_change()
        
    # commit any new entries into db and close
    con_db.commit()
    cur_db.close()
    
    # query alarm alert database to see if any new alerts occurred
    send_queued_alerts(valid_users)
    
    # Start User Input section (parse incoming txt msgs for commands)
    if os.path.isfile('/home/pi/last_msg_count'):
        last_msg_count = open('/home/pi/last_msg_count','r')
        prev_msg_count = last_msg_count.read()
        map(prev_msg_count, string.split(last_msg_count.readline()))
        last_msg_count.close()
    else:
        last_msg_count = 0
        prev_msg_count = 0
    if num_msgs > 0:
        msg = msgitems[num_msgs-1]
        last_msg_count = open('/home/pi/last_msg_count','w')
        last_msg_count.write ('%d'%(num_msgs))
    
        # error check case statement below
        command_matched=False
    
        for RGDMS_User in valid_users:
            DEBUG("message from: " + msg['from'])
            DEBUG("compare with valid user: " + RGDMS_User.getPhoneNumber())
            if (msg['from'] == '+'+RGDMS_User.getPhoneNumber()+':'):
                print 'From valid user: ' + RGDMS_User.getUserName()
                # this command will show status for all of the doors in the list
                if string.lower(msg['text']) == 'status all':
                    command_matched = True
                    for door in Doors:
                        #read from state file
                        status = door.getPDStatus()
                        print "RGDMS STATUS: Door " + door.getName() + " current status is: %s" %(status)
                        RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "RGDMS STATUS: Door " + door.getName() + " current status is: %s" %(status))
                if string.lower(msg['text']) == 'help':
                    command_matched = True
                    build_list_of_commands="RGDMS HELP: List of valid commands: status all, help"
                    for door in Doors:
                        build_list_of_commands+=', open '+ string.lower(door.getName())
                        build_list_of_commands+=', close '+ string.lower(door.getName())
                        build_list_of_commands+=', status '+ string.lower(door.getName())
                    RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), build_list_of_commands)
                # these commands are specific to a particular door, so loop through the list one door at a time     
                for door in Doors:
                    DEBUG("Door name: " + door.getName())
                    DEBUG("message: " + string.lower(msg['text']))
                    #parse message
                    if string.lower(msg['text']) == 'open '+ string.lower(door.getName()):
                        command_matched = True
                        print "RGDMS: OPEN " + door.getName()
                        #check to see if it's already open
                        if door.getPDStatus() == 'OPEN':
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "\"" + door.getName() + "\" door is already open")
                        else:
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "OPENING \"" + door.getName() + "\" door")
                            #trigger opener for door
                            door.trigger_open()
                            print(door.getName() + " door is OPEN");
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "\"" +door.getName() + "\" door is now OPEN")
    
                    elif string.lower(msg['text']) == 'close '+ string.lower(door.getName()):
                        command_matched = True
                        print "RGDMS: CLOSE " + door.getName()
                        # check to see if it's already closed
                        if door.getPDStatus() == 'CLOSED':
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "\"" + door.getName() + "\" door is already closed")
                        else:
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "CLOSING " +"\""+ door.getName() + "\" door")
                            #trigger door closed
                            door.trigger_close()         
                            print(door.getName() + " door is CLOSED");
                            RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "\"" + door.getName() + "\" door is now CLOSED")
          

                    elif string.lower(msg['text']) == 'status '+ string.lower(door.getName()):
                        command_matched = True
                        #read from state file
                        status = door.getPDStatus()
                        print "RGDMS STATUS: Door " + door.getName() + " current status is: %s" %(status)
                        RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "RGDMS STATUS: Door \"" + door.getName() + "\" current status is: %s" %(status))

                    else:
                        # add logic to "latch" true if it has already been met
                        if command_matched == True:
                            continue
                        else:
                            command_matched = False

                if command_matched == False:
                    print "invalid message"
                    RGDMS_send_SMS(RGDMS_User.getPhoneNumber(), "Invalid message, try again...")

            else:
                print 'message from a non-valid user'
                print msg['from']
    
        # delete existing messages to avoid a double command response
        for message in voice.sms().messages:
            message.delete()
    logging_close()



