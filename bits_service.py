#!/usr/bin/python2
# -*- coding: utf-8 -*-


# Beta version!

# TODO:
# Non accetta messaggi dal socket di lunghezza superiore a 2048..
# Leggere binding/config da un file di configurazione

import socket
import select
from sys import exc_info
from base64 import b64encode,b64decode

import pushserver
import database
import twitter_listener
from common import *
from config import MainConfiguration


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
        conf = MainConfiguration()
        
        phpconf = conf.Php()
        self.php_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.php_port = phpconf.port
        self.php_bind_address = phpconf.bind_address
        self.php_max_wait_sock = phpconf.max_wait_sock
        
        foneraconf = conf.Fonera()
        self.fonera_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fonera_port = foneraconf.port
        self.fonera_bind_address = foneraconf.bind_address
        self.fonera_max_wait_sock = foneraconf.max_wait_sock
        
        self.fonera_conn = None
        
        self.runnable = True
        
        self.fonera = FoneraStatus()
        
        self.php_connections = []
        self.events = []
        
        self.number_last_temperatures = conf.number_last_temperatures
        
        self.db = database.Database()
        self.fonera.status = self.db.status()
        
        self.push_srv = pushserver.PushService(self.data_dict())
        self.push_srv.starting()
        
        self.twitter = twitter_listener.Twitter(self.push_message_incoming)
        self.twitter.start()
        
    def data_dict(self):
        d = {}
        data = self.db.status(showtimestamp=True) #[True, "1970-01-01 00:00:00"]

        if data[0]:
            data[0] = "open"
        else:
            data[0] = "close"
            
        d["status"] = {}
        d["status"]["value"] = data[0]
        if data[1] != None and data[2] != None:
            if data[1] == 0:
                d["status"]["modifiedby"] = "bits"
            else:
                d["status"]["modifiedby"] = "manual"
            d["status"]["timestamp"] = data[2]
        
        data = self.db.get_last_temperature(self.number_last_temperatures) #ex: {0:[(21.9, '2012-03-03 14:47:10'), (21.9, '2012-03-03 14:37:04'), (21.9, '2012-03-03 14:26:58')]}
        if data == None:
            data = {}
        

        if (0 in data):
            d["tempint"] = {}
            d["tempint"]["value"] = data[0][0][0]
            d["tempint"]["timestamp"] = data[0][1][1]
            
            d["tempinthist"] = [{"value":a, "timestamp":b} for a,b in data[0]]
        
        if (1 in data):
            d["tempext"] = {}
            d["tempext"]["value"] = data[1][0][0]
            d["tempext"]["timestamp"] = data[1][1][1]
            
            d["tempexthist"] = [{"value":a, "timestamp":b} for a,b in data[1]]
        
        

        
        data = self.db.get_last_message()
        if data != None:
            d["msg"] = {}
            d["msg"]["user"] = data[0]
            d["msg"]["timestamp"] = data[1]
            d["msg"]["value"] = data[2]
            
        d["version"] = 3
        
        return d
        
    
    def server(self):
        debugMessage("Starting PHP socket server")
        
        self.php_sock.bind((self.php_bind_address, self.php_port))
        self.php_sock.listen(self.php_max_wait_sock)
        self.php_sock.setblocking(0)
        self.events.append(self.php_sock)
        
        debugMessage("Starting Fonera socket")
        self.fonera_sock.bind((self.fonera_bind_address, self.fonera_port))
        self.fonera_sock.listen(self.fonera_max_wait_sock)
        self.fonera_sock.setblocking(0)
        self.events.append(self.fonera_sock)
            
    def disconnect(self):   
        # Brutally closes fonera's socket
        if self.fonera.connected:
            self.fonera_disconnect()
            
        self.events.remove(self.fonera_sock)
        
        try:
            self.fonera_sock.close()
        except:
            pass
        
        for conn in self.php_connections:
            conn.close()
        # Brutally closes php socket
        self.php_sock.close()
        for event in self.events:
            try:
                event.close()
            except:
                pass
        #killing push services
        self.push_srv.stopping()
        
        self.twitter._Thread__stop()
        
    def fonera_disconnect(self):
        debugMessage("Disconnecting from fonera")
        self.fonera.connected = False
        self.events.remove(self.fonera_conn)
        try:
            self.fonera_conn.close()
        except:
            pass
        
    def push_update(self):
        self.push_srv.change_dictionary(self.data_dict())
                
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
        try:
            msg = self.fonera_conn.recv(2048).replace("\n","").replace("\r","")
        except:
            msg = None
            
        if msg:
            if msg.startswith("status "):
                # La fonera mi avvisa del cambio di stato della sede
                try:
                    status = bool(int(msg.split("status ")[-1]))
                    
                    if self.db.status(status, False): #Se ritorna True lo stato è stato cambiato in quello scelto
                        self.fonera.status = status
                        self.push_update()
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
                        self.push_update()
                    except:
                        debugMessage("Failed to understand command: %s" % msg)
                else:
                    debugMessage("Failed to understand command: %s" % msg)
                
            else:
                debugMessage("Failed to understand command: %s" % msg)
        else:
            self.fonera_disconnect()
            
    def php_message_handler(self, conn):
        try:
            msg = conn.recv(2048).replace("\n","").replace("\r","")
        except:
            msg = None

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
                        self.push_update()
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
                    b64_msg = None #Fa funzionare il print dell'except anche se fallisce prima di assegnare
                    p = msg.split(" ")
                    uid = int(p[1])
                    b64_msg = p[2]
                    plainmsg = b64decode(b64_msg) #b64_msg could contain a padding, like "bG9sCg== ; drop database bitsdb; --"
                    b64_msg = b64encode(plainmsg) #Goodbye injection padding
                    #Mi e' arrivato il testo
                    #Salva il testo sul db
                    if self.db.user_exists(uid):
                        self.db.store_msg(uid, b64_msg)
                        self.push_update()
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
    
    def push_message_incoming(self, text, author):
        debugMessage("Reciving a twit from "+str(author)+" with message "+str(text))
    
    
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
            in_ready, out_ready, except_ready = select.select(self.events,[],[])
            debugMessage("Select activated")
            
            for event in in_ready: 

                if event == self.php_sock:
                    debugMessage("PHP accept socket event")
                    conn,addr = self.php_sock.accept()
                    self.events.append(conn)
                    self.php_connections.append(conn)
                    
                
                elif event == self.fonera_sock: 
                    if not self.fonera.connected:
                        debugMessage("Fonera accept socket event")
                        self.fonera_conn, addr = self.fonera_sock.accept()
                        self.events.append(self.fonera_conn)
                        self.fonera.connected = True
                        self.fonera_change_status(self.fonera.status) # Se qualcuno cambia il db durante l'esecuzione del programma, non viene avvisata la fonera
                    else:
                        debugMessage("Attempt to another fonera connection, disconnecting first connection")
                        conn, addr = self.fonera_sock.accept() 
                        self.events.remove(self.fonera_conn)
                        self.fonera_conn.close()
                        self.fonera_conn = conn
                        self.events.append(self.fonera_conn)
                        self.fonera_change_status(self.fonera.status)

                    #self.broadcast_message(self.fonera.statusString())
                    # (non vogliamo avvisare nessuno quando la fonera si collega)
                    
                elif self.fonera.connected and event == self.fonera_conn:
                    debugMessage("Fonera recv socket event")
                    self.fonera_command_handler()
                
                    
                elif event in self.php_connections:
                    debugMessage("PHP recv socket event")
                    self.php_message_handler(event)
                
                else:
                    debugMessage("unexcepted event! -> %s" % str(event))
                    try:
                        self.events.remove(event)
                        del event
                        debugMessage("Unexcepted event: deleted forced")
                    except:
                        pass
                        
                    
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
         


