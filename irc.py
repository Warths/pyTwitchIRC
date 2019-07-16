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
        self.connected_channels = []
        self.message_buffer = []
        self.received_messages = []
        self.status = 0

        self.cap_ack = {
            "MEMBERSHIP": False,
            "COMMANDS": False,
            "TAGS": False
        }

        # Map of events with callback method
        self.callbacks = [
            {
                'type': 'PING',
                'method': self.__send_pong
            },
            {
                'type': 'CAP',
                'method': self.cap_ack,
                'args': ['message']
            },
            {
                'type': '376',
                'method': 'self.__set_status',
                'args': [1]
            },
            {
                'type': '366',
                'method': 'self.__add_connected_channel',
                'args': ['message']
            }
        ]

        # Starting a parallel thread to keep the IRC client running
        thread = threading.Thread(target=self.__run, args=())
        thread.daemon = True
        thread.start()

    def __check_callback(self, message):
        pass

    def __run(self):
        i = 0
        while True:
            try:
                self.__connect()
                self.channel_join("warths")
                while True:
                    i += 1
                    print(i)
                    self.__receive_data()
                    if i == 100:
                        self.channel_part("warths")
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

    def __cap_ack(self, array):
        pass

    def __open_socket(self) -> None:
        if self.socket:
            raise Exception('Socket already exists')
        self.socket = socket.socket()

    def __connect_socket(self) -> bool:
        try:
            self.socket.connect((self.host, self.port))
            self.socket.setblocking(0)
            print('Connected to {0[0]}:{0[1]}'.format(self.socket.getpeername()))
            return True
        except socket.gaierror:
            print('Unable to connect.')
            return False

    def __send_pong(self) -> None:
        self.last_ping = time.time()
        self.socket.send('PONG :tmi.twitch.tv\r\n'.encode("UTF-8"))
        self.__notice('Ping Received. Pong sent.')

    def __init_room(self):
        pass

    def __send_nickname(self):
        self.socket.sendall('NICK {}\r\n'.format(self.nickname).encode('utf-8'))

    def __send_pass(self):
        self.socket.send('PASS {}\r\n'.format(self.oauth).encode('utf-8'))

    def __request_capabilities(self, arg: str):
        self.socket.send('CAP REQ :twitch.tv/{}\r\n'.format(arg).encode('utf-8'))

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
            print(decoded)
            self.message_buffer.append(decoded)

    def channel_join(self, channel: str):
        # send a channel connection request
        self.socket.send('JOIN #{}\r\n'.format(channel).encode('utf-8'))


    def on_join_handler(self, message):
        if message.author == self.nickname:
            self.__notice('Successfuly connected to {}'.format(message.channel))
            self.connected_channels.append(message.channel)
        else:
            # TODO MANAGE CHATTER LIST
            pass

    def on_part_handler(self, message):
        if message.author == self.nickname:
            self.__notice('Successfuly disconnected from {}'.format(message.channel))
            try:
                self.connected_channels.remove(message.channel)
            except ValueError:
                self.__warning('Tried to disconnect from a non-connected channel')
        else:
            # TODO MANAGE CHATTER LIST
            pass

    def channel_part(self, channel: str):
        # leave a channel
        if channel in self.connected_channels:
            self.socket.send('PART #{}\r\n'.format(channel).encode('utf-8'))
            self.connected_channels.remove(channel)

    def channel_join_all(self):
        # rejoin all known channels
        for channel in self.connected_channels:
            self.channel_join(channel)

    # leave all connected channels
    def channel_part_all(self):
        for channel in self.connected_channels:
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
        except:
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
