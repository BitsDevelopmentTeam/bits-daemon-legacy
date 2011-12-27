#!/usr/bin/python
# -*- coding: utf-8 -*-


class MainConfiguration:
    class Php:
        port = 56343
        bind_address = "127.0.0.1"
        max_wait_sock = 5
    
    class Fonera:
        port = 56345
        bind_address = "10.0.0.1"
        max_wait_sock = 1
    
    
class DatabaseConfiguration:
    user = "bits"
    passwd = "<insert-db-passwd-here>"
    dbname = "bitsdb"
    host = "localhost"
    
class PushConfiguration:
    class Standard:
        bind_address = ""
        port = 3389
        maxlisten = 5
        maxconn = 300
        useThreads = False
        
    class Websockets:
        bind_address = ""
        port = 8081
        maxlisten = 5
        maxconn = 300
        useThreads = False
    
    class Websockets_beta4:
        port = 8080


