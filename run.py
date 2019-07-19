from irc import IRC
import time
from os import path
import json
import sys
from credentials import nickname, oauth
import random

client = IRC(nickname, oauth)


client.channel_join('ragnar_oock')

def generate_random_string():
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    string = ''
    for i in range(1,1):
        string = string + alphabet[random.randint(0, len(alphabet) - 1)]
    return string

while True:
    time.sleep(1)