#!/usr/bin/python
# -*- coding: utf-8 -*-

import socket
import select
import threading
from common import *
from config import PushConfiguration

pushconf = PushConfiguration()

class PushService:
    def __init__(self, start_status):
        self.push_services = [StandardPush]
        
        self.status = start_status
        self.push_istances = []
        
    def starting(self):
        for service in self.push_services:
            s = service(start_status = self.status)
            s.start()
            self.push_istances.append(s)
            
    def stopping(self):
        for service in self.push_istances:
            service.stop()
            service._Thread__stop()
    
    def change_status(self, status):
        self.status = status
        for service in self.push_istances:
            service.change_status(status)
    
    def send_message(self, msg):
        for service in self.push_istances:
            service.send_message(msg)
    

class StandardPush(threading.Thread):
    def __init__(self, start_status=None):
    
        threading.Thread.__init__(self)
        
        stdconf = pushconf.Standard()
        
        self.srv_address =  stdconf.bind_address
        self.srv_port = stdconf.port
        self.srv_maxlisten = stdconf.maxlisten
        self.srv_max_conn = stdconf.maxconn
        self.useThreads = stdconf.useThreads
        self.status = start_status
        
        self.srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP socket
        self.events = []
        self.connections = []
        
        self.running = True
        
        
    def init_service(self):
        debugMessage("Starting push server")
        self.srv_sock.bind((self.srv_address, self.srv_port))
        self.srv_sock.listen(self.srv_maxlisten)
        
        if not self.useThreads:
            self.srv_sock.setblocking(0) 
            self.events.append(self.srv_sock)
    
    def change_status(self, status):
        self.status = status
        self.broadcast_message(self.statusString())
    
    def statusString(self):
        if self.status:
            return "open"
        else:
            return "close"
        

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

    def broadcast_message(self, msg):
        msg += "\n"
        debugMessage("Sending broadcast to client")
        for connection in self.connections:
            try:
                connection.send(msg)
            except:
                errorMessage("Failed a message to a client", False)
                connection.close()
                self.connections.remove(connection)
                self.events.remove(connection)
    
    def client_handler(self, conn):
        #disconnects clients who sends something
        conn.close()
        self.connections.remove(conn)
        self.events.remove(conn)
    
    def server_full(self, conn):
        try:
            conn.close()
        except:
            pass
            
    def stop(self):
        self.disconnect_all()
        
        
    def disconnect_all(self):
        debugMessage("Stopping StandardPush service")
        self.running = False
        for conn in self.connections:
            try:
                conn.close()
            except:
                pass
        for conn in self.events:
            try:
                conn.close()
            except:
                pass

    
    def run(self):
        self.init_service()
        
        while self.running:
            if self.useThreads:
                raise NotImplemented
            else:
                in_ready, out_ready, except_ready = select.select(self.events,[],[])
                
                for event in in_ready: 
                    
                    if event == self.srv_sock: 
                        debugMessage("Internet accept socket event")
                        conn, addr = self.srv_sock.accept()
                        if len(self.connections) < self.srv_max_conn:
                            debugMessage("Connected with push client %s" % addr[0])
                            self.events.append(conn)
                            self.connections.append(conn)
                            self.send_client_msg(conn, self.statusString())
                        else:
                            debugMessage("New connection from %s recived but queue full" % addr[0])
                            self.server_full(conn)
                            
                    elif event in self.connections:
                        debugMessage("Internet recv socket event")
                        self.client_handler(event)
                
        debugMessage("StandardPush main cicle stopped")
        
        
class Websockets(threading.Thread):
    def __init__(self, bind_address, port=1723, maxlisten = 5, maxconn = 300,
                 useThreads = False):
        threading.Thread.__init__(self)
        self.srv_address = bind_address
        self.srv_port = port
        self.srv_maxlisten = maxlisten
        self.srv_maxconn = maxconn
        self.useThreads = useThreads
        
        
        handshake = """\
HTTP/1.1 101 Web Socket Protocol Handshake\r\n\
Upgrade: WebSocket\r\n\
Connection: Upgrade\r\n\
WebSocket-Origin: http://localhost:8888\r\n\
WebSocket-Location: ws://localhost:9999/\r\n\r\n\
"""
        
        
        self.srv_socket = None
        self.events = []
        
        self.running = True
        
        
    def init_service(self):
        self.srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #TCP socket
        self.srv_sock.bind((self.srv_address, self.srv_port))
        self.srv_sock.listen(self.srv_maxlisten)
        
        if not self.useThreads:
            self.srv_sock.setblocking(0) 
            self.events.append(self.srv_sock)
    
    def run(self):
        self.init_service()
        
        while self.running:
            if self.useThreads:
                raise NotImplemented
            else:
                in_ready, out_ready, except_ready = select.select(self.events,[],[])
                
                for event in in_ready: 
                    pass

