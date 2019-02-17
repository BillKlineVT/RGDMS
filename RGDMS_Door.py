import RPi.GPIO as GPIO
import time
import datetime
import sqlite3 as lite

class RGDMS_Door:
    # class variables
    OUTPUT_Trigger_Pin = -1
    INPUT_Closed_Pin = -1
    INPUT_Open_Pin = -1
    open_alert_sent = True
    closed_alert_sent = True
    PD_status = 'null'
    open_since = -1
    ten_min_alert_sent = True
    PD_file = 'null'
    name = 'default'
    # global DB variables
    RGDMS_DB="/DB/RGDMS_events.db"
    
    # class functions
    def __init__(self, output_trigger_pin, input_closed_pin, input_open_pin, name):
        print ("output_pin= %d input_closed= %d input_open_pin= %d" %(output_trigger_pin,input_closed_pin,input_open_pin))
        self.name = name
        # pin that triggers relay to open/close the garage
        self.OUTPUT_Trigger_Pin = output_trigger_pin
        # pin that reads status of "closed" sensor for the garage
        self.INPUT_Closed_Pin = input_closed_pin
        # setup pin that reads status of "open" sensor for the garage
        self.INPUT_Open_Pin = input_open_pin
        
        #configure GPIO pins for i/o
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.OUTPUT_Trigger_Pin, GPIO.OUT)
        GPIO.output(self.OUTPUT_Trigger_Pin, GPIO.HIGH)
        GPIO.setup(self.INPUT_Closed_Pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.INPUT_Open_Pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # create PD file
        self.PD_file = open('/home/pi/'+self.name+'_status','w')
        self.PD_file.write('unknown')
        self.PD_file.close()

        
        
    # test GPIO sensor inputs
    # "False" means that the sensor is latched i.e. closed_sensor=False means door is in closed position
    def test_GPIO_inputs(self):
        if GPIO.input(self.INPUT_Closed_Pin) == False:
        #check to see if state needs to be updated
            if self.PD_status != 'CLOSED':
                self.PD_file = open('/home/pi/'+self.name+'_status','w')
                self.PD_file.write('CLOSED')
                self.PD_file.close()
                self.open_alert_sent=False
                # reset "open since" timer to avoid false alarms
                self.open_since=-1

        if GPIO.input(self.INPUT_Open_Pin) == False:
            #check to see if state needs to be updated
            if self.PD_status != 'OPEN':     
                self.PD_file = open('/home/pi/'+self.name+'_status','w')
                self.PD_file.write('OPEN')
                self.PD_file.close()
                self.closed_alert_sent=False
                
    def read_PD_file(self):
        # read persistent data open/close state files
        self.PD_file = open('/home/pi/'+self.name+'_status','r')
        self.PD_status = self.PD_file.read()
        self.PD_file.close()
        
    def write_PD_file(self, status):    
        self.PD_file = open('/home/pi/'+self.name+'_status','w')
        self.PD_file.write(status)
        self.PD_file.close()
        
    def check_for_state_change(self):
        # connect to DB
        con_db = lite.connect(self.RGDMS_DB)
        cur_db = con_db.cursor()
        # door opened from another source (the garage door opener button or remote)
        if (GPIO.input(self.INPUT_Closed_Pin)==True and self.PD_status=='CLOSED' and self.open_alert_sent==False):
            now = datetime.datetime.now()
            str_date = now.strftime("%a %b %d %H:%M:%S %Z %Y")
            int_date = int(time.time())
            # add new entry into alarm database that will be sent via SMS
            cur_db.execute("insert into data (e_date,s_date,alert,alert_sent,garage_open_sensor,garage_closed_sensor) values(?,?,?,?,?,?)", (int_date,str_date,self.name+" side opened from another source",'0',GPIO.input(self.INPUT_Open_Pin),GPIO.input(self.INPUT_Closed_Pin)))
            self.open_alert_sent=True
            # capture time when opened so we can track if it is left open too long (test at beginning of loop)
            self.open_since = int_date
            self.ten_min_alert_sent=False
    
        # door closed from another source (the garage door opener button or remote)
        if (GPIO.input(self.INPUT_Open_Pin)==True and self.PD_status=='OPEN' and self.closed_alert_sent==False):
            now = datetime.datetime.now()
            str_date = now.strftime("%a %b %d %H:%M:%S %Z %Y")
            int_date = int(time.time())
            # add new entry into alarm database that will be sent via SMS
            cur_db.execute("insert into data (e_date,s_date,alert,alert_sent,garage_open_sensor,garage_closed_sensor) values(?,?,?,?,?,?)", (int_date,str_date,self.name+" side closed from another source",'0',GPIO.input(self.INPUT_Open_Pin),GPIO.input(self.INPUT_Closed_Pin)))
            self.closed_alert_sent=True
            self.open_since = -1
            
        # commit any new entries into db and close
        con_db.commit()
        cur_db.close()
        
    def getName(self):
        return self.name
    
    def getPDStatus(self):
        self.test_GPIO_inputs()
        print("PD_status reads "+self.PD_status) 
        return self.PD_status
    
    def trigger_open(self):
        GPIO.output(self.OUTPUT_Trigger_Pin, GPIO.LOW)
        time.sleep(2)
        GPIO.output(self.OUTPUT_Trigger_Pin, GPIO.HIGH)
        # poll door sensors until door is fully open
        while GPIO.input(self.INPUT_Open_Pin) != False:
            time.sleep(0.5)
        self.write_PD_file('OPEN')
        # capture time when opened so we can track if it is left open too long (test at beginning of loop)
        int_date = int(time.time())
        self.open_since = int_date
        self.ten_min_alert_sent=False
    def trigger_close(self):
        GPIO.output(self.OUTPUT_Trigger_Pin, GPIO.LOW)
        time.sleep(2)
        GPIO.output(self.OUTPUT_Trigger_Pin, GPIO.HIGH)
        # poll door sensors until door is fully closed
        while GPIO.input(self.INPUT_Closed_Pin) != False:
            time.sleep(0.5)
        self.write_PD_file('CLOSED')
        # reset "open since" timer to avoid false alarms
        self.open_since = -1
        
