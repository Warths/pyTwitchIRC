import threading
import socket
import time
import event
import datetime


class IRC:
    """
    Map of all supported event.
    Key list :
    - format_string : parse pattern (str)
    - type : event type (str)
    - tags : index of tags (int / None)
    - author : index of author (int / None)
    - channel : index of channel (int / None)
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
        self.state = 0

        self.cap_ack_membership = False
        self.cap_ack_commands = False
        self.cap_ack_tags = False


        # Map of events with callback method

        self.callbacks = [
            (":tmi.twitch.tv CAP * ACK :twitch.tv/commands", self.__cap_ack_commands),
            (":tmi.twitch.tv CAP * ACK :twitch.tv/tags", self.__cap_ack_tags),
            (":tmi.twitch.tv CAP * ACK :twitch.tv/membership", self.__cap_ack_membership),
            ("PING :tmi.twitch.tv", self.__send_pong),
        ]

        # Starting a parallel thread to keep the IRC client running
        thread = threading.Thread(target=self.__run, args=())
        thread.daemon = True
        thread.start()

    def __check_callback(self):
        while len(self.message_buffer) > 0:
            for tuples in self.callbacks:
                if self.message_buffer[0] == tuples[0]:
                    tuples[1]()
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
        self.__request_capabilities("commands")
        self.__request_capabilities("tags")
        self.__request_capabilities("membership")

    def __cap_ack_membership(self):
        print("Cap MEMBERSHIP got acknowledge.")
        self.cap_ack_membership = True

    def __cap_ack_tags(self):
        print("Cap TAGS got acknowledge.")
        self.cap_ack_tags = True

    def __cap_ack_commands(self):
        print("Cap COMMANDS got acknowledge.")
        self.cap_ack_commands = True

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
        self.buffer += self.socket.recv(1024)
        messages = self.buffer.split(b'\r\n')
        self.buffer = messages.pop()
        for message in messages:
            print(message.decode('utf-8'))
            self.message_buffer.append(message.decode('utf-8'))

    def channel_join(self, channel: str):
        self.socket.send('JOIN #{}\r\n'.format(channel).encode('utf-8'))

    def channel_part(self, channel: str):
        if channel in self.connected_channels:
            self.socket.send('PART #{}\r\n'.format(channel).encode('utf-8'))
            self.connected_channels.remove(channel)

    def channel_join_all(self):
        for channel in self.connected_channels:
            self.channel_join(channel)

    def channel_part_all(self):
        for channel in self.connected_channels:
            self.channel_part(channel)

    def send_message(self, message: str):
        pass

    def __parse(self, message):
        if message == 'PING :tmi.twitch.tv':
            return event.Event(message, 'PING')
        else:
            return event.Event(message, 'UNKNOWN')

    def get_message(self) -> list:
        pass
