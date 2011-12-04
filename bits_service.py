#!/usr/bin/python2

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

timestamp = lambda : time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

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
        self.srv_port = 56344
        self.srv_bind_address = ""
        self.srv_max_wait_sock = 5
        
        
        self.php_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.php_port = 56343
        self.php_bind_address = "127.0.0.1"
        self.php_max_wait_sock = 5
        
        
        self.fonera_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fonera_port = 56345
        self.fonera_bind_address = ""
        self.fonera_max_wait_sock = 1
        self.fonera_conn = None
        
        self.runnable = True
        
        self.fonera = FoneraStatus()
        
        self.connections = []
        self.php_connections = []
        self.events = []
        
        self.mysql_host = "localhost"
        self.db_user = "bits"
        self.db_name = "bitsdb"
        self.db_passwd = "<db-password-here>"
    
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
    
    
    def db_init(self):
        try:
            self.db = MySQLdb.connect(host=self.mysql_host, user=self.db_user, 
                                      passwd=self.db_passwd, db=self.db_name)
            
            self.fonera.status = self.db_get_status()
        except:
            print "[Error] While opening database"
            raise SystemExit
            
    def db_get_status(self):
        c = self.db.cursor()
        c.execute("""SELECT  value FROM Status ORDER BY timestamp DESC LIMIT 1""")
        if c.fetchall() == ((1,),): #valutare anche il caso in cui la tabella di status e' vuota.
            return True
        else:
            return False
    
    def db_change_status(self, status, fromWebsite):
        if DEBUG: print "Changing status in database"
        
        
        c = self.db.cursor()
        c.executemany(
            """INSERT INTO Status (timestamp, value, modifiedby)
            VALUES (%s, %s, %s)""",
            [
            (timestamp(), int(status), int(fromWebsite))
            ] )
        self.db.commit()
        #Controlla se c'e' gente che non si e' sloggata e sloggala tu.
        c = self.db.cursor()
        c.execute("""UPDATE Presence SET logout = '%s' WHERE logout is null""" % timestamp())
        self.db.commit()
        
        
    def db_store_temperature(self, value, sensor):
        c = self.db.cursor()
        c.executemany(
        """INSERT INTO Temperature (timestamp, sensor, value)
        VALUES (%s, %s, %s)""",
        [
        (timestamp(), int(sensor), float(value))
        ] )
        self.db.commit()
    
    def db_check_user_existence(self, user):
        c = self.db.cursor()
        c.execute("""SELECT userid FROM Users""")
        return (user in [i[0] for i in c.fetchall()])
        
    def db_add_user_move(self, user_id, enter):
        #The userid passed as param already exists in the db
        c = self.db.cursor()
        if enter:
            c.executemany("""INSERT INTO Presence (userid, login, logout)
                            VALUES (%s, %s, NULL)""",
            [
            (user_id, timestamp())
            ])
        else:
            c.execute("""UPDATE Presence SET logout = '%s' WHERE userid = %d AND logout is null""" % (timestamp(), user_id))
        self.db.commit()
            
    def db_save_message(self, user_id, b64_msg):
        c = self.db.cursor()
        c.executemany("""INSERT INTO Message (userid, timestamp, message)
                                VALUES (%s, %s, %s)""",
                [
                (user_id, timestamp(), b64_msg)
                ])
        self.db.commit()

            
    def check_user_logged(self, user_id):
        c = self.db.cursor()
        c.execute("""SELECT userid FROM Presence WHERE logout is null""")
        return (user_id in [i[0] for i in c.fetchall()])
        
    
    def disconnect(self):
        #TODO: Broken. Fixme
        # Disconnect all push clients and close server
        for client in self.connections:
            client.close()
            
        # Brutally closes fonera's socket
        self.fonera_sock.close()
        
        # Brutally closes php socket
        self.php_sock.close()
        
        self.srv_sock.close()
        
    def fonera_disconnect(self):
        if DEBUG: print "[Debug] Disconnecting from fonera"
        self.fonera.connected = False
        self.events.remove(self.fonera_conn)
        try:
            self.fonera_conn.close()
        except:
            pass
        
    def broadcast_message(self, msg):
        msg += "\n"
        if DEBUG: print "[Debug] Sending broadcast to client"
        for c in self.connections:
            try:
                c.send(msg)
            except:
                if DEBUG: print "[Debug] FAIL a message to a client"
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
        if self.db_check_user_existence(user_id) and (enter or self.check_user_logged(user_id)) and self.db_get_status():
            self.db_add_user_move(user_id, enter)
        else:
            #TODO: Avvertire la fonera?
            if DEBUG: print "[Debug] The user id '%d' recived does not exists in the db or it is already logged out" % user_id
                
    def fonera_command_handler(self):
        msg = self.fonera_conn.recv(2048).replace("\n","").replace("\r","")
        if msg:
            if msg.startswith("status "):
                # La fonera mi avvisa del cambio di stato della sede
                try:
                    self.fonera.status = bool(int(msg.split("status ")[-1]))
                    
                    if self.db_get_status() != self.fonera.status:
                        self.db_change_status(self.fonera.status, False) # Aggiorno il database con il nuovo status inviato dalla fonera
                        self.broadcast_message(self.fonera.statusString()) #Invio a tutti i client push il nuovo status della sede ricevuto dalla fonera
                except:
                    # Se fallisce la conversione in bool o db o broadcast
                    if DEBUG: print "[Debug] FAIL to understand command: '"+str(msg)+"' with error "+str(exc_info()[0])
                
            elif msg.startswith("enter "):
                try:
                    # E' entrato tizio-caio con ID "user_id"
                    user_id = int(msg.split("enter ")[-1])
                    # TODO: Che si fa?
                    self.user_move(user_id, True)
                    if DEBUG: print "E' entrato l'utente con id: "+str(user_id)
                except:
                    if DEBUG: print "[Debug] Wrong enter message"
                    
            elif msg.startswith("leave "):
                try:
                    # Se ne va tizio-caio con ID "user_id"
                    user_id = int(msg.split("leave ")[-1])
                    # TODO: Che si fa?
                    self.user_move(user_id, False)
                    if DEBUG: print "E' uscito l'utente con id: "+str(msg.split(" ")[1])
                except:
                    if DEBUG: print "[Debug] Wrong leave message"
                
            elif msg.startswith("temperature "):
                element = msg.split(" ")[1:]
                if len(element) == 2:
                    try:
                        sensor = int(element[0])
                        value = float(element[1])
                        if DEBUG: print "Rilevata temperatura "+str(value)+" C dal sensore "+str(sensor)
                        # Aggiungo la temperatura nel database
                        self.db_store_temperature(value, sensor)
                    except:
                        if DEBUG: print "[Debug] FAIL to understand command: "+str(msg)
                else:
                    if DEBUG: print "[Debug] FAIL to understand command: "+str(msg)
                
            else:
                if DEBUG: print "[Debug] Command not implemented: "+str(msg)
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
                
                    if self.db_get_status() != status:
                        self.db_change_status(status, True) # Aggiorno il database con il nuovo status inviato da php
                        self.fonera.status = status
                        self.fonera_change_status(status) #Avviso la fonera del cambio di stato
                        self.broadcast_message(self.fonera.statusString())
                except:
                    if DEBUG: print "[Debug] Recived invalid status from php"
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("enter "):
                try:
                    user_id = int(msg.split("enter ")[-1])
                    #E' entrato tizio-caio
                    self.user_move(user_id, True)
                except:
                    if DEBUG: print "[Debug] Recived invalid enter message"
                    self.php_disconnect_client(conn)
            
            elif msg.startswith("leave "):
                try:
                    user_id = int(msg.split("leave ")[-1])
                    #E' uscito tizio-caio
                    self.user_move(user_id, False)
                except:
                    if DEBUG: print "[Debug] Recived invalid leave message"
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("message "):
                try:
                    p = msg.split(" ")
                    user_id = int(p[1])
                    b64_msg = p[2]
                    b64decode(b64_msg) #Useful for checking sql injections from fonera (if injection it fails)
                    #Mi e' arrivato il testo
                    #Salva il testo sul db
                    if self.db_check_user_existence(user_id):
                        self.db_save_message(user_id, b64_msg)
                        #Invia il testo alla fonera
                        self.fonera_display_text_plain(b64_msg)
                    else:
                        if DEBUG: print "[Debug] The specified user does not exist in the database"
                except:
                    if DEBUG: print "[Debug] Recived invalid text message '"+str(b64_msg)+"'"
                    self.php_disconnect_client(conn)
                    
            elif msg.startswith("sound "):
                try:
                    sound_id = int(msg.split("sound ")[-1])
                    #play del sound
                    self.fonera_play_sound(sound_id)
                except:
                    if DEBUG: print "[Debug] Recived invalid sound message"
                    self.php_disconnect_client(conn)
        else:
            self.php_disconnect_client(conn)
            
    def php_disconnect_client(self,conn):
        if DEBUG: print "[Debug] Disconnecting a php client"
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
        self.db_init()
        self.server()
    
        while self.runnable:
            in_ready,out_ready,except_ready = select.select(self.events,[],[])
            if DEBUG: print "[Debug] Select activated"
            
            for event in in_ready: 
            
                if event == self.srv_sock: 
                    if DEBUG: print "[Debug] Internet accept socket event"
                    conn,addr = self.srv_sock.accept()
                    self.events.append(conn)
                    self.connections.append(conn)
                    self.send_client_msg(conn, self.fonera.statusString())
                
                elif event == self.php_sock:
                    if DEBUG: print "[Debug] PHP accept socket event"
                    conn,addr = self.php_sock.accept()
                    self.events.append(conn)
                    self.php_connections.append(conn)
                    
                
                elif event == self.fonera_sock and not self.fonera.connected: 
                    if DEBUG: print "[Debug] Fonera accept socket event"
                    self.fonera_conn, addr = self.fonera_sock.accept()
                    self.events.append(self.fonera_conn)
                    self.fonera.connected = True
                    self.fonera_change_status(self.fonera.status) # Se qualcuno cambia il db durante l'esecuzione del programma, non viene avvisata la fonera

                    #self.broadcast_message(self.fonera.statusString())
                    # (non vogliamo avvisare nessuno quando la fonera si collega)
                    
                elif self.fonera.connected and event == self.fonera_conn:
                    if DEBUG: print "[Debug] Fonera recv socket event"
                    self.fonera_command_handler()
                
                elif event in self.connections:
                    if DEBUG: print "[Debug] Internet recv socket event"
                    # Disconnects clients who sends something
                    event.close()
                    self.connections.remove(event)
                    self.events.remove(event)
                    
                elif event in self.php_connections:
                    if DEBUG: print "[Debug] PHP recv socket event"
                    self.php_message_handler(event)
                
                else:
                    if DEBUG: print "[Debug] unexcepted event! -> "+str(event)
                    
        self.disconnect()
        
if __name__ == "__main__":
    bits = BitsService()
    try:
        bits.mainloop()
    except KeyboardInterrupt:
        print "Stopping all sockets"
        bits.disconnect()
         


