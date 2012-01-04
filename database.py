#!/usr/bin/python
# -*- coding: utf-8 -*-

import MySQLdb
from common import *
from config import DatabaseConfiguration
from base64 import b64encode,b64decode

class Database:
    def __init__(self):
        self.config = DatabaseConfiguration()
        
        self.user = self.config.user
        self.passwd = self.config.passwd
        self.db_name = self.config.dbname
        self.host = self.config.host
        self.connection = None
        
        self.connect()
    
    def connect(self):
        try:
            self.connection = MySQLdb.connect(host = self.host, user = self.user,
                                          passwd = self.passwd, db = self.db_name)
            debugMessage("(Re)connected to MySQL database")
        except:
            errorMessage("Connection to MySQL database fail")
        
    def query(self, sql, retry = False, params = None, many = False): 
        try:
            cursor = self.connection.cursor()
            if not many:
                cursor.execute(sql)
            else:
                cursor.executemany(sql, params)
            self.connection.commit()
        except (AttributeError, MySQLdb.OperationalError):
            if not retry:
                self.connect()
                self.query(sql, retry=True)
            else:
                errorMessage("SQL query fail")
                raise SystemExit
        return cursor
    
    def status(self, s = None, fromWebsite = False, showtimestamp = False): 
        if s == None:
            debugMessage("Getting current status from database")
            if showtimestamp:
                data = self.query("""SELECT value, modifiedby, timestamp FROM Status ORDER BY timestamp DESC LIMIT 1""").fetchall()
                if len(data) == 0:
                    return (False, None, None) #closed if no data in db
                else:
                    data = list(data[0])
                    data[0] = bool(data[0])
                    data[2] = str(data[1])
                    return data #ex: [True, 0, "1970-01-01 00:00:00"]
            else:
                cursor = self.query("""SELECT value FROM Status ORDER BY timestamp DESC LIMIT 1""")
                if cursor.fetchall() == ((1,),): #closed if no data in db
                    return True
                else:
                    return False
        else:
            curr_status = self.status()
            if curr_status != s:
                debugMessage("Changing status in database")
                self.query(
                    """INSERT INTO Status (timestamp, value, modifiedby)
                    VALUES (%s, %s, %s)""",
                    params=[
                    (timestamp(), int(s), int(fromWebsite))
                    ], many=True)
                
                if s == False:
                    self.force_logout_all()
                return True
            else:
                return False

    def force_logout_all(self): 
        debugMessage("Forcing logout for all logged-in users")
        self.query("""UPDATE Presence SET logout = '%s' WHERE logout is null""" % timestamp())

    def user_enter(self, uid, enter = True): 
        if self.user_exists(uid):
            if enter:
                if not self.user_logged_in(uid):
                    debugMessage("User %s logging in" % uid)
                    self.query("""INSERT INTO Presence (userid, login, logout)
                                        VALUES (%s, %s, NULL)""", args=[
                                (uid, timestamp())
                                ], many=True)
                    return (True,True)
                else:
                    return (True,False)
            else:
                if self.user_logged_in(uid):
                    debugMessage("User %s logging out" % uid)
                    self.query(
                        """UPDATE Presence SET logout = '%s' WHERE userid = %d AND logout is null"""
                        % (timestamp(), uid))
                    return (True,True)
                else:
                    return (True,False)
        else:
            return (False,None)       
                
            
    def user_exists(self, uid): 
        cursor = self.query("""SELECT COUNT(*) FROM Users WHERE userid = %s""" % uid)
        return bool(cursor.fetchall()[0][0])
    
    def userid_to_nick(self, uid):
        data = self.query("""SELECT username FROM Users WHERE userid = %s""" % uid).fetchall()
        if len(data) == 0:
            return None
        else:
            return data[0][0]

    def user_logged_in(self, uid): 
        debugMessage("Logging out all logged users")
        cursor = self.query("""SELECT COUNT(*) FROM Presence WHERE logout is null AND userid = %s""" % uid)
        return bool(cursor.fetchall()[0][0])
        
    def get_last_temperature(self):
        debugMessage("Getting last temperature from database")
        
        data = self.query("""SELECT DISTINCT sensor FROM Temperature""").fetchall()
        if len(data) == 0:
            return None
            
        sensors = [s[0] for s in data] #ex: [0, 1]
        
        datadict = {}
        
        for sensor in sensors:        
            data = self.query("""SELECT value,timestamp FROM Temperature WHERE sensor=%d ORDER BY timestamp DESC LIMIT 1""" % sensor).fetchall()
            #data style: ((19.968800000000002, datetime.datetime(2012, 1, 4, 14, 3, 11)),)
            if len(data) != 0:
                data = list(data[0])
                data[1] = str(data[1]) #convert date to string format
                datadict[sensor] = data
        
        return datadict #ex: {0:[19.9, "1970-01-01 00:00:00"]}
    
    def get_last_message(self):
        debugMessage("Getting last message from database")
        data = self.query("""SELECT userid,timestamp,message FROM Message ORDER BY timestamp DESC LIMIT 1""").fetchall()
        if len(data) == 0:
            return None
        else:
            data = list(data[0]) #data[0] is like (2L, datetime.datetime(2011, 12, 14, 15, 31, 42), 'dGVzdGluZwo=')
            data[0] = self.userid_to_nick(data[0])
            data[1] = str(data[1])
            data[2] = b64decode(data[2]) #be careful for XSS!
            return data
            
        

    def store_temperature(self, value, sensor_id): 
        cursor = self.query(
            """INSERT INTO Temperature (timestamp, sensor, value)
            VALUES (%s, %s, %s)""",
            params=[
            (timestamp(), int(sensor_id), float(value))
            ], many=True )

    def store_msg(self, uid, b64_msg): 
        self.query(
            """INSERT INTO Message (userid, timestamp, message)
                            VALUES (%s, %s, %s)""",
            params=[
            (uid, timestamp(), b64_msg)
            ], many=True)

