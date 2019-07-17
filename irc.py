import threading
import socket
import time
import event
import re
import select

class IRC:

    def __init__(self, nickname: str, oauth: str, host='irc.chat.twitch.tv', port=6667):
        """

        :param nickname: lowercase twitch username of the bot
        :param oauth: chat authentication key. Can be found on twitchapps.com/tmi
        :param host: twitch server to connect with
        :param port: twitch server port to connect with
        """

        self.nickname = nickname.lower()
        self.oauth = oauth
        self.host = host
        self.port = port

        self.socket = None
        self.buffer = b''
        self.last_ping = time.time()
        self.channels = {}
        self.message_buffer = []
        self.received_messages = []
        self.status = 0

        self.cap_ack = {
            "twitch.tv/tags": False,
            "twitch.tv/commands": False,
            "twitch.tv/membership": False
        }

        # Map of events with callback method
        self.callbacks = [
            {
                'type': 'PING',
                'method': self.__send_pong
            },
            {
                'type': 'CAP',
                'method': self.__on_cap_handler,
                'args': ['message']
            },
            {
                'type': '376',
                'method': self.__set_status,
                'args': [1]
            },
            {
                'type': 'JOIN',
                'method': self.on_join_handler,
                'args': ['message']
            },
            {
                'type': 'PART',
                'method': self.on_part_handler,
                'args': ['message']
            },
            {
                'type': '353',
                'method': self.on_353_handler,
                'args': ['message']
            }
        ]

        # Starting a parallel thread to keep the IRC client running
        thread = threading.Thread(target=self.__run, args=())
        thread.daemon = True
        thread.start()

    def __check_callback(self, message):
        for handlers in self.callbacks:
            if message.type == handlers['type']:
                if 'args' in handlers:
                    if handlers['args'][0] == 'message':
                        handlers['method'](message)
                    else:
                        handlers['method'](*handlers['args'])
                else:
                    handlers['method']()

    def __set_status(self, status):
        self.status = status

    def __run(self):
        while True:
            try:
                self.__connect()
                self.channel_join("warths")
                while True:
                    self.__receive_data()
                    while len(self.message_buffer) > 0:
                        message = self.parse(self.message_buffer.pop(0))
                        self.__check_callback(message)
                        self.received_messages.append(message)

            except socket.gaierror:
                print("GaiError Raised. Trying to reconnect.")
                self.socket = None
                time.sleep(5)
            except socket.timeout:
                print("Timeout error raised. Trying to reconnect.")
                self.socket = None
                time.sleep(5)

    def __connect(self):
        self.__open_socket()
        self.__connect_socket()
        self.__send_pass()
        self.__send_nickname()

        # request all the IRC capabilities
        self.__request_capabilities("commands")
        self.__request_capabilities("tags")
        self.__request_capabilities("membership")

    def __on_cap_handler(self, message):
        try:
            self.cap_ack[message.content] = True
        except KeyError:
            self.__warning("Unsupported Cap Ack received : {}".format(message.content))

    def on_353_handler(self, message):
        for chatter in message.content.split(' '):
            self.channels[message.channel].append(chatter)

    def __open_socket(self) -> None:
        if self.socket:
            raise Exception('Socket already exists')
        self.socket = socket.socket()

    def __connect_socket(self) -> bool:
        try:
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(0)
            self.__notice('Connected to {0[0]}:{0[1]}'.format(self.socket.getpeername()))
            return True
        except socket.gaierror:
            self.__warning('Unable to connect.')
            return False

    def __send_pong(self) -> None:
        self.last_ping = time.time()
        self.__send('PONG :tmi.twitch.tv\r\n')
        self.__notice('Ping Received. Pong sent.')

    def __send(self, packet, hide_after_index = None):
        self.socket.send(packet.encode('UTF-8'))
        if hide_after_index:
            packet_hidden = '*' * (len(packet) - hide_after_index)
            packet = packet[0:hide_after_index] + packet_hidden
        self.__packet_sent(packet)

    def __init_room(self):
        pass

    def __send_nickname(self):
        self.__send('NICK {}\r\n'.format(self.nickname))

    def __send_pass(self):
        self.__send('PASS {}\r\n'.format(self.oauth), hide_after_index=11)

    def __request_capabilities(self, arg: str):
        self.__send('CAP REQ :twitch.tv/{}\r\n'.format(arg))

    def __is_loading_complete(self):
        pass

    def __is_timed_out(self):
        return time.time() - self.last_ping > 300

    def __receive_data(self):
        ready = select.select([self.socket], [], [], 0.1)
        if not ready[0]:
            return
        # get up to 1024 from the buffer and the socket then split the messages
        self.buffer += self.socket.recv(1024)
        messages = self.buffer.split(b'\r\n')
        self.buffer = messages.pop()

        # print all the messages
        for message in messages:
            decoded = message.decode("utf-8")
            self.__packet_received(decoded)
            self.message_buffer.append(decoded)

    def channel_join(self, channel: str):
        # send a channel connection request
        self.__send('JOIN #{}\r\n'.format(channel))

    def on_join_handler(self, message):
        if message.author == self.nickname:
            self.__notice('Successfuly connected to {}'.format(message.channel))
            self.channels[message.channel] = []
        else:
            self.channels[message.channel].append(message.author)

    def on_part_handler(self, message):
        if message.author == self.nickname:
            self.__notice('Successfuly disconnected from {}'.format(message.channel))
            try:
                self.channels.pop(message.channel)
            except KeyError:
                self.__warning('Channel {author} disconnected, '
                               'but wasn\'t connected'.format(**message.__dict__))
        else:
            try:
                self.channels[message.channel].remove(message.author)
            except ValueError:
                self.__warning('User {author} disconnected from {channel}, '
                               'but wasn\'t connected'.format(**message.__dict__))

    def channel_part(self, channel: str):
        # leave a channel
        if channel in self.channels:
            self.__send('PART #{}\r\n'.format(channel))

    def channel_join_all(self):
        # rejoin all known channels
        for channel in self.channels:
            self.channel_join(channel)

    # leave all connected channels
    def channel_part_all(self):
        for channel in self.channels:
            self.channel_part(channel)

    # send a message
    def send_message(self, message: str):
        pass

    def parse(self, message):
        tags = self.__parse_tags(message)
        message_type = self.__parse_type(message)
        channel = self.__parse_channel(message, message_type)
        author = self.__parse_author(message)
        content = self.__parse_content(message, channel)
        return event.Event(message, type=message_type, tags=tags, channel=channel, author=author, content=content)

    def __parse_tags(self, message):
        # Checking if there is tags
        if message[0] == '@':
            # Isolating tags (between '@' and ' :')
            tags = message[1:].split(' :')[0]
            tags = self.__parse_tags_dict(tags, ';', '=')
            # Parsing sub dict (separator : '/' and ',')
            for key in tags:
                # undocumented tag, not processed #twitch
                if key == 'flags':
                    pass
                # if the tag contain ':' it's a dict containing lists
                elif ':' in tags[key]:
                    tags[key] = self.__parse_tags_dict(tags[key], '/', ':')
                    for sub_key in tags[key]:
                        tags[key][sub_key] = self.__parse_list(tags[key][sub_key], ',')
                        for i in range(0, len(tags[key][sub_key])):
                            tags[key][sub_key][i] = self.__parse_list(tags[key][sub_key][i], '-')
                # if the tag contain '/' it's a dict containing ints
                elif '/' in tags[key]:
                    tags[key] = self.__parse_tags_dict(tags[key], ',', '/')
            return tags

    @staticmethod
    def __parse_tags_dict(tag_dict_string, separator_a, separator_b):
        # Separating tags (separator : ";" )
        tag_list = tag_dict_string.split(separator_a)
        tag_dict = {}
        # Appending key/value pair in a dict
        for tag in tag_list:
            key, value = tag.split(separator_b)
            tag_dict[key] = value
        return tag_dict

    @staticmethod
    def __parse_list(list_string, separator):
        return list_string.split(separator)

    @staticmethod
    def __parse_type(message):
        split = message.split()
        for word in split:
            if word.upper() == word:
                return word

    def __parse_channel(self, message, message_type):
        # Channel in a whisper is always the client nickname
        if message_type == 'WHISPER':
            return self.nickname
        else:
            try:
                # Channel is prefixed by ' #' and followed by a space
                return message.split(' #')[1].split()[0]
            except IndexError:
                # Some events don't belong to any channels
                return None

    @staticmethod
    def __parse_author(message):
        # author is formatted like : ':author!author@author.'
        try:
            return message.split('!')[1].split('@')[0]
        except IndexError:
            return None

    @staticmethod
    def __parse_author_regex(message):
        # 2 hours to create search string:
        try:
            return re.search(r':(.*?)!(\1)@(\1)\.', message).group(1)
        except IndexError:
            return None

    @staticmethod
    def __parse_content(message, channel):
        target = " :"
        if channel:
            target = channel + target
        content = message.split(target, maxsplit=1)
        return content[1] if len(content) > 1 else None

    def get_message(self) -> list:
        messages = self.received_messages
        self.received_messages = []
        return messages

    @staticmethod
    def __notice(text: str):
        print('\33[32m' + text + '\33[0m')

    @staticmethod
    def __warning(text: str):
        print('\33[31m' + text + '\33[0m')

    @staticmethod
    def __packet_received(text: str):
        print('\33[36m<' + text + '\33[0m')

    @staticmethod
    def __packet_sent(text: str):
        print('\33[34m>' + text.strip("\n") + '\33[0m')