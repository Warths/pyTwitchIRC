from irc import IRC
import time
from os import path
import json
import sys
from credentials import nickname, oauth

client = IRC(nickname, oauth)


# with open(path.join("samples", "samples1.txt"), 'r', encoding='utf-8') as file:
#     sample = file.read()
#
# i = 0
# for shit in sample.split('\n'):
#     i += 1
#     print(json.dumps(client.parse(shit).__dict__, indent=2))
#     if i == 30:
#         break

while True:
    time.sleep(0.1)