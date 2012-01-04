#!/usr/bin/python

import twitter
from time import sleep
from config import TwitterConfiguration


class Twitter(threading.Thread):

    def __init__(self, callback):
        threading.Thread.__init__(self)     
           
        self.config = TwitterConfiguration()
        
        self.api = twitter.Api(consumer_key = self.config.consumer_key,
                  consumer_secret = self.config.consumer_secret,
                  access_token_key = self.config.access_token_key,
                  access_token_secret = self.config.access_token_secret)
                  
        self.sleeptime = self.config.sleeptime     
        
        self.callback = callback
        self.last_reply = None
        self.enabled = True

    def run(self):
        self.check_replies(first=True)
        while self.enabled:
            self.check_replies()
            sleep(self.sleeptime)
            
    def check_replies(self, first=False):
        try:
            status = api.GetReplies()
        except:
            self.enabled = False
            return
            
        reply_id = str(status[0].id)
        
        if first:
            self.last_reply = reply_id
            
        elif self.last_reply != reply_id:
            self.last_reply = reply_id
            
            msg = " ".join(status[0].text.split(" ")[1:])
            sender = status[0].user.screen_name
            
            self.callback(msg, sender)
            
    def stop(self):
        self.enabled = False
        

