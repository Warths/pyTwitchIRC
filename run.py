from irc import IRC
import time
from os import path
import json
import sys
from credentials import nickname, oauth
import random
import requests

client = IRC(nickname, oauth, log_settings=[0,0,0,0], throttle=100)

how_many_hundred = 20
start_at = 0

def get_streams(hundred: int):
    usernames = []
    pagination = ''
    headers = {"Client-ID": 'qab2o1rz2l780rdbn7myuk5iyg4wra'}
    while hundred > 0:
        r = requests.get("https://api.twitch.tv/helix/streams?first=100{}".format(pagination), headers=headers)
        for stuff in r.json()['data']:
            usernames.append(stuff['user_name'].lower())
        pagination = '&after={}'.format(r.json()['pagination']['cursor'])
        time.sleep(5)
        hundred -= 1
    return usernames

def degager_vieux_stream(irc, liste):
    for channels in irc.channels:
        if channels not in liste:
            irc.channel_part(channels)

def mettre_nouveau_stream(irc, liste):
    for channels in liste:
        if channels not in irc.channels:
            irc.channel_join(channels)

def update_irc(irc, liste):
    degager_vieux_stream(irc, liste)
    mettre_nouveau_stream(irc, liste)


while True:
    liste_stream = get_streams(start_at)
    print("=========================================")
    print("Client {} connected channels: {}/{}".format(nickname, len(client.channels), start_at * 100))
    print("=========================================")
    if start_at < how_many_hundred:
        start_at += 1
    update_irc(client, liste_stream)



