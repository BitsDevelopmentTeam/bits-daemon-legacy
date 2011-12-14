#!/usr/bin/python
# -*- coding: utf-8 -*-

import time


DEBUG = True
DEBUG_LEVEL = 0

timestamp = lambda : time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def debugMessage(msg, level=0):
    if DEBUG and (level <= DEBUG_LEVEL):
        print("[Debug - %s] %s" % (str(timestamp()), msg))

def errorMessage(msg, fatal=True):
    print("[Error] %s" % msg)
    if fatal:
        raise SystemExit
        

