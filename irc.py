import threading
import socket
import time
import event
import datetime


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
            (":tmi.twitch.tv CAP * ACK :twitch.tv/membership", self.__cap_ack, ("MEMBERSHIP")),
            (":tmi.twitch.tv CAP * ACK :twitch.tv/commands", self.__cap_ack, ("COMMANDS")),
            (":tmi.twitch.tv CAP * ACK :twitch.tv/tags", self.__cap_ack, ("TAGS")),
            ("PING :tmi.twitch.tv", self.__send_pong, None)
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
                if self.message_buffer[0] == c[0]:
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

    def __cap_ack(self, capability):
        print("Cap {} got acknowledge.".format(capability[0]))
        self.cap_ack[capability[0]] = True

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
        if message in ['PING :tmi.twitch.tv', 'PONG :tmi.twitch.tv', 'RECONNECT :tmi.twitch.tv']:
            return event.Event(message, event_type=message.split()[0])
        else:
            tags = self.__parse_tags(message)
            return event.Event(message, event_type='UNKNOWN', tags=tags)

    def __parse_tags(self, message):
        # Checking if there is tags
        if message[0] == '@':
            # Isolating tags (beetween "@" and " :")
            tags = message[1:].split(' :')[0]
            tags = self.__parse_tags_dict(tags, ';', '=')
            # Parsing subdict (separator : "/" and ",")
            for key in tags:
                if '/' in tags[key]:
                    try:
                        tags[key] = self.__parse_tags_dict(tags[key], ',', '/')
                    except ValueError:
                        tags[key] = self.__parse_tags_dict(tags[key], '/', ':')
            return tags


    def __parse_tags_dict(self, tag_dict_string, separator_a, separator_b):
        # Separating tags (separator : ";" )
        tag_list = tag_dict_string.split(separator_a)
        tag_dict = {}
        # Appending key/value pair in a dict
        for tag in tag_list:
            print(tag)
            key, value = tag.split(separator_b)
            tag_dict[key] = value
        return tag_dict


    def get_message(self) -> list:
        pass
