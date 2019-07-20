import json
import time
from sys import path

import requests

from credentials import nickname, oauth
from irc import IRC

client = IRC(nickname, oauth, log_settings=[0, 1, 0, 0], throttle=100)

how_many_hundred = 20
start_at = 0


def get_streams(hundred: int):
    username_list = []
    pagination = ''
    headers = {"Client-ID": 'qab2o1rz2l780rdbn7myuk5iyg4wra'}
    while hundred > 0:
        r = requests.get("https://api.twitch.tv/helix/streams?first=100{}".format(pagination), headers=headers)
        for stuff in r.json()['data']:
            username_list.append(stuff['user_name'].lower())
        pagination = '&after={}'.format(r.json()['pagination']['cursor'])
        time.sleep(5)
        hundred -= 1
    return username_list


def pop_old_stream(irc, lst):
    chn = irc.channels
    for channels in chn:
        if channels not in lst:
            irc.channel_part(channels)


def add_new_stream(irc, lst):
    for channels in lst:
        if channels not in irc.channels:
            irc.channel_join(channels)


def update_irc(irc, lst):
    pop_old_stream(irc, lst)
    add_new_stream(irc, lst)


with open(path.join("samples", "log.txt"), 'r', encoding='utf-8') as file:
    sample = file.read()

i = 0
for shit in sample.split('\n'):

    print(json.dumps(client.parse(shit).__dict__, indent=2))

# while True:
#     stream_list = get_streams(start_at)
#     update_irc(client, stream_list)
#     print("=========================================")
#     print("Client {} connected channels: {}/{}".format(nickname, len(client.channels), start_at * 100))
#     print("=========================================")
#     if start_at < how_many_hundred:
#         start_at += 1
