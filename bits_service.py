#!/usr/bin/python2
# -*- coding: utf-8 -*-


# Beta version!

# TODO:
# Non accetta messaggi dal socket di lunghezza superiore a 2048..
# Si possono collegare due fonere!!! attenzione!
# Leggere binding/config da un file di configurazione

import socket
import select
import time
import MySQLdb
import ConfigParser
from sys import exc_info
from base64 import b64encode,b64decode

DEBUG = True
DEBUG_LEVEL = 0

timestamp = lambda : time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def debugMessage(msg, level=0):
    if DEBUG and (level <= DEBUG_LEVEL):
        print("[Debug] %s" % msg)

def errorMessage(msg, fatal=True):
    print("[Error] %s" % msg)
    if fatal:
        raise SystemExit
        
        
class Database:
    def __init__(self, user, password, database, host):
        self.user = user
        self.passwd = password
        self.db_name = database
        self.host = host
        self.connection = None
        
        self.connect()
    
    def connect(self):
        try:
            self.connection = MySQLdb.connect(host = self.host, user = self.user,
                                          passwd = self.passwd, db = self.db_name)
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
        self.query("""UPDATE Presence SET logout = '%s' WHERE logout is null""" % timestamp())

    def user_enter(self, uid, enter = True): 
        if self.user_exists(uid):
            if enter:
                if not self.user_logged_in(uid):
                    self.query("""INSERT INTO Presence (userid, login, logout)
                                        VALUES (%s, %s, NULL)""", args=[
                                (uid, timestamp())
                                ], many=True)
                    return (True,True)
                else:
                    return (True,False)
            else:
                if self.user_logged_in(uid):
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
            [
            (uid, timestamp(), b64_msg)
            ])


class FoneraStatus:
    def __init__(self):
        self.connected = False
        self.status = False
    def statusString(self):
        if self.status:
            return "open"
        else:
            return "close"
    def foneraStatusString(self):
        return str(int(self.status))


class BitsService:

    def __init__(self):
        #config = ConfigParser.RawConfigParser()
        #config.read('bits_service.conf')
        #print config.get('push-server', 'port')
        
        self.srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv_port = 3389        #Scelta perche' aperta dal politecnico
        self.srv_bind_address = ""
        self.srv_max_wait_sock = 5
        self.src_max_conn = 300
        
        
        self.php_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.php_port = 56343
        self.php_bind_address = "127.0.0.1"
        self.php_max_wait_sock = 5
        
        
        self.fonera_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fonera_port = 56345
        self.fonera_bind_address = "10.0.0.1"
        self.fonera_max_wait_sock = 1
        self.fonera_conn = None
        
        self.runnable = True
        
        self.fonera = FoneraStatus()
        
        self.connections = []
        self.php_connections = []
        self.events = []
        
        self.db = Database("bits", "<db-password-here>", "bitsdb", "localhost")
        self.fonera.status = self.db.status()
    
    def server(self):
        
        self.srv_sock.bind((self.srv_bind_address, self.srv_port))
        self.srv_sock.listen(self.srv_max_wait_sock)
        self.srv_sock.setblocking(0)
        self.events.append(self.srv_sock)
        
        self.php_sock.bind((self.php_bind_address, self.php_port))
        self.php_sock.listen(self.php_max_wait_sock)
        self.php_sock.setblocking(0)
        self.events.append(self.php_sock)
        
        self.fonera_sock.bind((self.fonera_bind_address, self.fonera_port))
        self.fonera_sock.listen(self.fonera_max_wait_sock)
        self.fonera_sock.setblocking(0)
        self.events.append(self.fonera_sock)
    
        
    
    def disconnect(self):
        #TODO: Broken. Fixme
        # Disconnect all push clients and close server
        for client in self.connections:
            try:
                client.close()
            except:
                pass
            
        # Brutally closes fonera's socket
        self.fonera_sock.close()
        
        # Brutally closes php socket
        self.php_sock.close()
        
        self.srv_sock.close()
        
        for event in self.events:
            try:
                event.close()
            except:
                pass
        
    def fonera_disconnect(self):
        debugMessage("Disconnecting from fonera")
        self.fonera.connected = False
        self.events.remove(self.fonera_conn)
        try:
            self.fonera_conn.close()
        except:
            pass
        
    def broadcast_message(self, msg):
        msg += "\n"
        debugMessage("Sending broadcast to client")
        for c in self.connections:
            try:
                c.send(msg)
            except:
                errorMessage("Failed a message to a client", False)
                c.close()
                self.connections.remove(c)
                self.events.remove(c)
    
    def send_client_msg(self, conn, msg):
        try:
            conn.send(msg+"\n")
        except:
            self.events.remove(conn)
            self.connections.remove(conn)
            try:
                conn.close()
            except:
                pass
                
    def send_fonera_msg(self, msg):
        try:
            self.fonera_conn.send(msg)
            return True
        except:
            self.fonera_disconnect()
            return False
    
    def user_move(self, user_id, enter):
        out = self.db.user_enter(user_id, enter)
        if not out[0]: debugMessage("The user id '%d' does not exists in the db")
        if out[0] and (not out[1]):
            if enter:
                debugMessage("The user id '%d' already logged in")
            else:
                debugMessage("The user id '%d' already logged out")

            #TODO: Avvertire la fonera?

                
    def fonera_command_handler(self):
        msg = self.fonera_conn.recv(2048).replace("\n","").replace("\r","")
        if msg:
            if msg.startswith("status "):
                # La fonera mi avvisa del cambio di stato della sede
                try:
                    status = bool(int(msg.split("status ")[-1]))
                    
                    if self.db.status(status, False): #Se ritorna True lo stato è stato cambiato in quello scelto
                        self.fonera.status = status
                        self.broadcast_message(self.fonera.statusString())
                    else:
                        #Siamo già nello stato in cui vuoi cambiare!
                        debugMessage("Fonera trying to change to actual status instead of new one")
                        #TODO: Avvisare la fonera?
                except:
                    # Se fallisce la conversione in bool o db o broadcast
                    debugMessage("Failed to understand command: '"+msg+"' with error '"+str(exc_info()[0])+"'")
                
            elif msg.startswith("enter "):
                try:
                    uid = int(msg.split("enter ")[-1])
                    # TODO: Che si fa?
                    self.user_move(uid, True)
                    debugMessage("User enter: %s" % uid)
                except:
                    debugMessage("Recived invalid enter message from Fonera")
                    
            elif msg.startswith("leave "):
                try:
                    uid = int(msg.split("leave ")[-1])
                    # TODO: Che si fa?
                    self.user_move(uid, False)
                    debugMessage("User leave: %s" % uid)
                except:
                    debugMessage("Recived invalid leave message from Fonera")
                
            elif msg.startswith("temperature "):
                element = msg.split(" ")[1:]
                if len(element) == 2:
                    try:
                        sensor = int(element[0])
                        value = float(element[1])
                        debugMessage("Detected temperature %f °C from sensor %d" % (value, sensor))
                        # Aggiungo la temperatura nel database
                        self.db.store_temperature(value, sensor)
                    except:
                        debugMessage("Failed to understand command: %s" % msg)
                else:
                    debugMessage("Failed to understand command: %s" % msg)
                
            else:
                debugMessage("Failed to understand command: %s" % msg)
        else:
            self.fonera_disconnect()
            
    def php_message_handler(self, conn):
        msg = conn.recv(2048).replace("\n","").replace("\r","")
        if msg:
            # Messaggi da visualizzare a display inviati da php,
            # Avvisi che sta arrivando qualcuno mandati da php
            if msg.startswith("status "):
                try:
                    status = bool(int(msg.split("status ")[-1]))
                
                    if self.db.status() != status:
                        self.db.status(status, True) # Aggiorno il database con il nuovo status inviato da php
                        self.fonera.status = status
                        self.fonera_change_status(status) #Avviso la fonera del cambio di stato
                        self.broadcast_message(self.fonera.statusString())
                except:
                    debugMessage("Recived invalid status message from PHP")
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("enter "):
                try:
                    uid = int(msg.split("enter ")[-1])
                    self.db.user_enter(uid, True)
                    #TODO: Mandare feedback a PHP se non esiste l'utente o è già loggato? In tal caso creare un'altra funzione come fatto per la fonera
                except:
                    debugMessage("Recived invalid enter message from PHP")
                    self.php_disconnect_client(conn)
            
            elif msg.startswith("leave "):
                try:
                    uid = int(msg.split("leave ")[-1])
                    self.db.user_enter(uid, False)
                    #TODO: Vedi sopra
                except:
                    debugMessage("Recived invalid enter message from PHP")
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("message "):
                try:
                    p = msg.split(" ")
                    uid = int(p[1])
                    b64_msg = p[2]
                    plainmsg=b64encode(b64decode(b64_msg)) #b64_msg could contain a padding, like "bG9sCg== ; drop database bitsdb; --"
                    b64_msg=b64encode(plainmsg) #Goodbye injection padding
                    #Mi e' arrivato il testo
                    #Salva il testo sul db
                    if self.db.user_exists(uid):
                        self.db.store_msg(uid, b64_msg)
                        #Invia il testo alla fonera
                        self.fonera_display_text_plain(b64_msg)
                    else:
                        debugMessage("The specified user '%d' does not exist in the database" % uid)
                except:
                    debugMessage("Recived invalid text message '%s'" % b64_msg)
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("sound "):
                try:
                    sound_id = int(msg.split("sound ")[-1])
                    #play del sound
                    self.fonera_play_sound(sound_id)
                except:
                    debugMessage("Recived invalid sound message")
                    self.php_disconnect_client(conn)
        else:
            self.php_disconnect_client(conn)
            
    def php_disconnect_client(self,conn):
        debugMessage("Disconnecting a php client")
        self.php_connections.remove(conn)
        self.events.remove(conn)
        try:
            conn.close()
        except:
            pass
            
    def fonera_display_text(self, text):
        if self.fonera.connected:
            return self.send_fonera_msg("message "+b64encode(text)+"\n")
        else:
            return False
    
    def fonera_display_text_plain(self, text):
        if self.fonera.connected:
            return self.send_fonera_msg("message "+text+"\n")
        else:
            return False
            
    def fonera_play_sound(self, num):
        if self.fonera.connected:
            self.send_fonera_msg("sound "+str(num)+"\n")
        else:
            return False
    
    def fonera_change_status(self, status):
        if self.fonera.connected:
            if status:
                self.send_fonera_msg("status 1\n")
            else:
                self.send_fonera_msg("status 0\n")
                
        else:
            return False
        
    def mainloop(self):
        self.server()
    
        while self.runnable:
            in_ready,out_ready,except_ready = select.select(self.events,[],[])
            debugMessage("Select activated")
            
            for event in in_ready: 
            
                if event == self.srv_sock: 
                    debugMessage("Internet accept socket event")
                    conn, addr = self.srv_sock.accept()
                    if len(self.connections) < self.src_max_conn:
                        self.events.append(conn)
                        self.connections.append(conn)
                        self.send_client_msg(conn, self.fonera.statusString())
                    else:
                        conn.close()
                
                elif event == self.php_sock:
                    debugMessage("PHP accept socket event")
                    conn,addr = self.php_sock.accept()
                    self.events.append(conn)
                    self.php_connections.append(conn)
                    
                
                elif event == self.fonera_sock and not self.fonera.connected: 
                    debugMessage("Fonera accept socket event")
                    self.fonera_conn, addr = self.fonera_sock.accept()
                    self.events.append(self.fonera_conn)
                    self.fonera.connected = True
                    self.fonera_change_status(self.fonera.status) # Se qualcuno cambia il db durante l'esecuzione del programma, non viene avvisata la fonera

                    #self.broadcast_message(self.fonera.statusString())
                    # (non vogliamo avvisare nessuno quando la fonera si collega)
                    
                elif self.fonera.connected and event == self.fonera_conn:
                    debugMessage("Fonera recv socket event")
                    self.fonera_command_handler()
                
                elif event in self.connections:
                    debugMessage("Internet recv socket event")
                    # Disconnects clients who sends something
                    event.close()
                    self.connections.remove(event)
                    self.events.remove(event)
                    
                elif event in self.php_connections:
                    debugMessage("PHP recv socket event")
                    self.php_message_handler(event)
                
                else:
                    debugMessage("unexcepted event! -> %s" % str(event))
                    
        self.disconnect()
        

if __name__ == "__main__":
    bits = BitsService()
    try:
        bits.mainloop()
    except KeyboardInterrupt:
        debugMessage("\nStopping all sockets")
        bits.disconnect()
        debugMessage("Cleaning up")
        del bits
        debugMessage("Good bye!")
         


