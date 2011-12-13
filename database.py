#!/usr/bin/python
# -*- coding: utf-8 -*-

import MySQLdb
from common import *
from config import DatabaseConfiguration

class Database:
    def __init__(self, user, password, database, host):
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
    
    def status(self, s = None, fromWebsite = False): 
        if s == None:
            debugMessage("Getting current status from database")
            cursor = self.query("""SELECT value FROM Status ORDER BY timestamp DESC LIMIT 1""")
            if cursor.fetchall() == ((1,),): #in questo modo Se il database e' vuoto ritorna False
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

    def user_logged_in(self, uid): 
        debugMessage("Logging out all logged users")
        cursor = self.query("""SELECT COUNT(*) FROM Presence WHERE logout is null AND userid = %s""" % uid)
        return bool(cursor.fetchall()[0][0])

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

