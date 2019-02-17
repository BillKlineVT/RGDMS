'''
Created on Aug 29, 2014

@author: bill
'''

class RGDMS_User(object):
    '''
    classdocs
    '''
    # init variables
    phone_number = -1
    enable = False
    user_name = "default_user"


    def __init__(self, phone_number, enable, user_name):
        '''
        Constructor
        '''
        self.phone_number = phone_number
        self.enable = enable
        self.user_name = user_name
        
    def getPhoneNumber(self):
        return self.phone_number
    def getEnabled(self):
        return self.enable
    def getUserName(self):
        return self.user_name