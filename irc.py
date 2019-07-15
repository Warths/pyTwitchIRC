import threading
import socket
import time
import event
import re

class IRC:
    """
    Map of all supported event.
    Key list :
    - format_string (str) :  parse pattern
    - type          (str) :  event type
    - tags          (int) :  index of tags
    - author        (int) :  index of author
    - channel       (int) :  index of channel
    """

    mapping = [
        # JOIN
        {
            'format_string': ':{}!{}@{}.tmi.twitch.tv JOIN #{}',
            'type': 'JOIN',
            'tags': None,
            'author': 0,
            'channel': 3
        },
        # PART
        {
            'format_string': ':{}!{}@{}.tmi.twitch.tv PART #{}',
            'type': 'PART',
            'tags': None,
            'author': 0,
            'channel': 3
        },
        # MODE - Moderator Added
        {
            'format_string': ':jtv MODE #{} +o {}',
            'type': 'MODE',
            'tags': None,
            'author': 0,
            'channel': 3
        },
        # MODE - Moderator Removed
        {
            'format_string': ':jtv MODE #{} -o {}',
            'type': 'MODE',
            'tags': None,
            'author': 0,
            'channel': 3
        },

    ]

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
        self.last_ping = None
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
            ("CAP", self.__cap_ack, (self.message_buffer, "membership")),
            ("CAP", self.__cap_ack, (self.message_buffer, "commands")),
            ("CAP", self.__cap_ack, (self.message_buffer, "tags")),
            ("PING", self.__send_pong, None)
        ]

        # Starting a parallel thread to keep the IRC client running
        thread = threading.Thread(target=self.__run, args=())
        thread.daemon = True
        thread.start()

    def __check_callback(self):
        # while there is messages in the messages buffer
        while len(self.message_buffer) > 0:
            # run through the callback list
            for c in self.callbacks:
                # if the first message is a callback run the associated method
                if self.parse(self.message_buffer[0]).type == c[0]:
                    # if the method doesn't need parameters
                    if c[2] is None:
                        c[1]()
                    # if the method does need parameters
                    else:
                        c[1](c[2])
            # pop out the message from the messages buffer and append it to the received messages
            self.received_messages.append(self.message_buffer.pop(0))

    def __run(self):
        self.__connect()
        self.channel_join("warths")
        while True:
            self.__receive_data()
            self.__check_callback()
            time.sleep(0.1)
            pass

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
        message = array[0][0]
        target = array[1]
        message_type = self.__parse_type(message)
        channel = self.__parse_channel(message, message_type)
        content = self.__parse_content(message, channel, message_type)
        if content.split(target) != content:
            self.__notice("Cap {} got acknowledge.".format(array[1]))
            self.cap_ack[target.uppercase()] = True
            return True
        else:
            self.__notice("not a CAP ACK")
            return False

    def __open_socket(self) -> None:
        if self.socket:
            raise Exception('Socket already exists')
        self.socket = socket.socket()

    def __connect_socket(self) -> bool:
        try:
            self.socket.connect((self.host, self.port))
            print('Connected to {0[0]}:{0[1]}'.format(self.socket.getpeername()))
            return True
        except socket.gaierror:
            print('Unable to connect.')
            return False

    def __send_pong(self) -> None:
        print("Ping received. PONG sent.")
        self.socket.send('PONG :tmi.twitch.tv\r\n'.encode("UTF-8"))

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

    def __check_heartbeat(self):
        pass

    def __receive_data(self):
        # get up to 1024 from the buffer and the socket then split the messages
        self.buffer += self.socket.recv(1024)
        messages = self.buffer.split(b'\r\n')
        self.buffer = messages.pop()

        # print all the messages
        for message in messages:
            decoded = message.decode("utf-8")
            print(decoded)
            parsed = self.parse(decoded)
            print(parsed.dump())
            self.message_buffer.append(decoded)

    # send a channel connection request
    def channel_join(self, channel: str):
        self.socket.send('JOIN #{}\r\n'.format(channel).encode('utf-8'))

    # leave a channel
    def channel_part(self, channel: str):
        if channel in self.connected_channels:
            self.socket.send('PART #{}\r\n'.format(channel).encode('utf-8'))
            self.connected_channels.remove(channel)

    # rejoin all known channels
    def channel_join_all(self):
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
        return event.Event(message, type=message_type, tags=tags, channel=channel, author=author)

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
    def __parse_content(message, channel, message_type):
        target = channel + " " + message_type
        content = message.split(target)
        if content != message:
            return content
        else:
            return None

    def get_message(self) -> list:
        pass

    @staticmethod
    def __notice(text: str):
        print('\33[32m' + text + '\33[0m')

    @staticmethod
    def __warning(text: str):
        print('\33[31m' + text + '\33[0m')
