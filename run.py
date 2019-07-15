from irc import IRC
import time
from os import path
import json
from credentials import nickname, oauth

client = IRC(nickname, oauth)


with open(path.join("samples", "samples1.txt"), 'r', encoding='utf-8') as file:
    sample = file.read()

pouet = {}

for stuff in sample.split('\n'):
    if client.parse(stuff).type in pouet:
        pouet[client.parse(stuff).type] += 1
    else:
        pouet[client.parse(stuff).type] = 1



for stuff in sample.split('\n'):
    print(json.dumps(client.parse(stuff).type))
    print(json.dumps(client.parse(stuff).author))

print(json.dumps(pouet, indent=2))

while True:
    time.sleep(0.1)