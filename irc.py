import datetime
import re
import select
import socket
import threading
import time

from event import Event, CurrentEvent


class IRC:

    def __init__(self, nickname: str, oauth: str, host='irc.chat.twitch.tv', port=6667,
                 log_settings=(0, 0, 0, 0), throttle=20, log_file=None, how_many=5, max_try=5):
        """

        :param nickname: lowercase twitch username of the bot
        :param oauth: chat authentication key. Can be found on twitchapps.com/tmi
        :param host: twitch server to connect with
        :param port: twitch server port to connect with
        :param log_settings: [notice, warning, received, send] set the logging fashion
        :param how_many: maximum new connection per run loop
        :param max_try: maximum try before abort joining a channel
        """

        self.__nickname = nickname.lower()
        self.__oauth = oauth
        self.__host = host
        self.__port = port
        self.__log_settings = log_settings
        self.__throttle = throttle
        self.__log_file = log_file
        self.__how_many = how_many
        self.__max_try = max_try

        self.__socket = None
        self.__buffer = b''
        self.__last_ping = time.time()

        self.__event = CurrentEvent()
        self.__event_sent_date = []
        self.__event_buffer = []
        self.__received_event = []
        self.__status = -1

        self.channels = {}
        self.__channels_to_part = []
        self.__channels_to_join = []
        self.__to_join = []
        self.__to_part = []

        self.__capabilities_acknowledged = {
            "twitch.tv/tags": False,
            "twitch.tv/commands": False,
            "twitch.tv/membership": False
        }

        # Map of events with callback method
        self.__callbacks = [
            {
                'type': 'PING',
                'method': self.__send_pong,
                'args': []
            },
            {
                'type': 'CAP',
                'method': self.__on_cap_handler,
                'args': [self.__event]
            },
            {
                'type': '376',
                'method': self.__set_status,
                'args': [1]
            },
            {
                'type': 'JOIN',
                'method': self.__on_join_handler,
                'args': [self.__event]
            },
            {
                'type': 'PART',
                'method': self.__on_part_handler,
                'args': [self.__event]
            },
            {
                'type': '353',
                'method': self.__on_353_handler,
                'args': [self.__event]
            },
            {
                'type': 'RECONNECT',
                'method': self.__init_connection,
                'args': []
            }
        ]

        # Starting a parallel thread to keep the IRC client running
        __thread = threading.Thread(target=self.__run, args=())
        __thread.daemon = True
        __thread.start()

        time.sleep(1)

    def __run(self):
        while True:
            try:
                self.__init_connection()

                while True:
                    # check connection status
                    if self.__is_timed_out():
                        self.__warning('Client didn\'t receive ping for too long')
                        raise socket.timeout

                    self.process_socket()

            except socket.gaierror:
                self.__reset_connection("Gaierror raised. Trying to reconnect.")
            except socket.timeout:
                self.__reset_connection("Timeout Error raised. Trying to reconnect.")
            except ConnectionResetError:
                self.__reset_connection("ConnectionResetError raised. Trying to reconnect.")
            except BrokenPipeError:
                self.__reset_connection("BrokenPipeError raised. Trying to reconnect.")
            except OSError as e:
                self.__reset_connection("OSError raised : {} . Trying to reconnect.".format(e.strerror))
                print(e.args)

    def process_socket(self):
        self.__receive_data()
        while len(self.__event_buffer) > 0:
            tmp = self.__event_buffer.pop(0)

            try:
                event = self.parse(tmp)
                self.__event.update(event)
                self.__check_callback()
                if self.__status == 3:
                    self.__received_event.append(event)

            except Exception as e:
                print(tmp, file=open("errors.txt", "a"))
                print(e)
                print(e.args)
                self.__warning("appended an error to error.txt")

        if self.__status == 3:
            # connect scheduled channels
            if len(self.__to_join) > 0:
                item = self.__to_join.pop(0)
                channel = item[0]
                counter = item[1]
                timestamp = item[2]
                if time.time() - timestamp < 5:
                    self.__to_join.append((channel, counter, timestamp))
                elif counter < self.__max_try:
                    self.__request_join(channel)
                    counter += 1
                    self.__to_join.append((channel, counter, time.time()))
            # connect scheduled channels
            if len(self.__to_part) > 0:
                item = self.__to_part.pop(0)
                channel = item[0]
                counter = item[1]
                timestamp = item[2]
                if time.time() - timestamp < 5:
                    self.__to_part.append((channel, counter, timestamp))
                elif counter < self.__max_try:
                    self.__request_part(channel)
                    counter += 1
                    self.__to_part.append((channel, counter, time.time()))

    def __init_connection(self, warn=None):
        # emptying the buffer
        self.__buffer = b''

    def __init_connection(self):
        self.__connect()
        self.list_all_channels_to_reconnect()

    def __reset_connection(self, warn=None):
        # print the warning if needed
        if warn:
            self.__warning(warn)
        # emptying the buffer
        self.__buffer = b''
        # emptying the channel list
        self.channels = []
        # reset status variables
        self.__last_ping = time.time()
        self.__socket = None
        for key in self.__capabilities_acknowledged:
            self.__capabilities_acknowledged[key] = False
        self.__set_status(-1)

    def __connect(self):
        # setup the connection
        self.__open_socket()
        self.__connect_socket()
        self.__send_pass()
        self.__send_nickname()
        self.__set_status(2)

        # request all the IRC capabilities
        self.__request_capabilities("twitch.tv/commands")
        self.__request_capabilities("twitch.tv/tags")
        self.__request_capabilities("twitch.tv/membership")

    def __check_callback(self):
        for handlers in self.__callbacks:
            if self.__event.type == handlers['type']:
                handlers['method'](*handlers['args'])

    def __set_status(self, status):
        if status == -1 and self.__status != -1:
            self.__warning('STATUS : -1 - No socket')
        elif status == -1 and self.__status == 3:
            self.__warning('STATUS : -1 - Socket died')
        elif status == 0:
            self.__notice('STATUS : 0 - Socket opened')
        elif status == 1:
            self.__notice('STATUS : 1 - Socket connected')
        elif status == 2:
            self.__notice('STATUS : 2 - Socket authenticated')
        elif status == 3:
            self.__notice('STATUS : 3 - Socket ready, buffering messages')
        self.__status = status

    # get all received event and clear event buffer
    def get_event(self) -> list:
        events = self.__received_event
        self.__received_event = []
        return events

    """
    Handlers
    """

    def __on_cap_handler(self, event):
        try:
            self.__capabilities_acknowledged[event.content] = True

            if self.__capabilities_acknowledged['twitch.tv/membership'] and \
                    self.__capabilities_acknowledged['twitch.tv/tags'] and \
                    self.__capabilities_acknowledged['twitch.tv/commands']:
                self.__set_status(3)

            if not self.__log_settings[3]:
                self.__notice('Capability {} got acknowledged'.format(event.content))

        except KeyError:
            self.__warning('Unsupported Cap Ack received : {}'.format(event.content))

    # fetch chatter names
    def __on_353_handler(self, event) -> None:
        for chatter in event.content.split(' '):
            self.channels[event.channel].append(chatter)

    # notify a successful connection or a chatter joining
    def __on_join_handler(self, event):
        # if the author is the client
        if event.author == self.__nickname:
            self.__notice('Successfully connected to {}'.format(event.channel))
            self.channels[event.channel] = []
            for i in range(0, len(self.__to_join)):
                if self.__to_join[i][0] == event.channel:
                    self.__to_join.pop(i)
                    break
        # if the author is a chatter
        else:
            self.channels[event.channel].append(event.author)

    # notify a channel disconnection or a chatter leaving
    def __on_part_handler(self, event):
        # if trigger by the client
        if event.author == self.__nickname:
            try:
                self.channels.pop(event.channel)
                self.__notice('Successfully disconnected from {}'.format(event.channel))
            except KeyError:
                self.__notice('Channel {author} disconnected, '
                              'but wasn\'t connected'.format(**event.__dict__))
        # if trigger by other chatter
        else:
            try:
                self.channels[event.channel].remove(event.author)
            except ValueError:
                self.__notice('User {author} disconnected from {channel}, '
                              'but wasn\'t connected'.format(**event.__dict__))

    """
    socket
    """

    def __open_socket(self) -> None:
        self.__socket = socket.socket()
        self.__set_status(0)

    def __connect_socket(self) -> bool:
        try:
            self.__socket.connect((self.__host, self.__port))
            self.__socket.setblocking(0)
            self.__notice('Connected to {0[0]}:{0[1]}'.format(self.__socket.getpeername()))
            self.__set_status(1)
            return True

        except socket.gaierror:
            self.__warning('Unable to connect.')
            return False

    # fetch data from the socket
    def __receive_data(self):
        # try to retrieve data from socket, timeout if nothing for .1 second
        ready = select.select([self.__socket], [], [], 0.1)
        if not ready[0]:
            return

        # get up to 1024 from the buffer and the socket then split the events
        self.__buffer += self.__socket.recv(4096)
        events = self.__buffer.split(b'\r\n')
        self.__buffer = events.pop()

        # append all the events to the event buffer
        for event in events:
            decoded = event.decode("utf-8")
            self.__packet_received(decoded)
            self.__event_buffer.append(decoded)

    """
    channels management
    """

    # send a channel connection request
    def __request_join(self, channel: str):
        if self.__wait_for_status():
            self.__send('JOIN #{}\r\n'.format(channel))

    # send a channel disconnection request
    def __request_part(self, channel: str):
        if channel in self.channels and self.__wait_for_status():
            self.__send('PART #{}\r\n'.format(channel))

    # rejoin all known channels
    def list_all_channels_to_reconnect(self):
        channels_to_reconnect = []
        for channel in self.__to_join:
            channels_to_reconnect.append((channel[0], 0, time.time() - 5))
        for channel in self.channels:
            channels_to_reconnect.append((channel, 0, time.time() - 5))
        self.__to_join = channels_to_reconnect
        self.channels = {}

    # request channel join
    def join(self, channel: str):
        channels = list(self.channels)
        if channel not in channels:
            self.__to_join.append((channel, 0, time.time()))
        else:
            self.__warning('Already connected to channel {}, connection aborted'.format(channel))

    # request channel join
    def part(self, channel: str):
        channels = list(self.channels)
        if channel in channels:
            self.__to_part.append((channel, 0, time.time()))
        else:
            self.__warning('Not connected to channel {}, unable to disconnect'.format(channel))

    """
    sending methods
    """

    # Lock __send if throttling
    def __anti_throttle(self):
        # while len(self.__event_sent_date) >= self.__throttle:
        #     t = time.time()
        #     # check if event is older than 30 seconds
        #     if t - self.__event_sent_date[0] > 30:  # seconds
        #         self.__event_sent_date.pop(0)
        #
        #     # Wait until next event can be popped out
        #     else:
        #         wait = 30 - (t - self.__event_sent_date[0])
        #         if 0 < wait < 30:
        #             if wait > 0.5:
        #                 self.__warning('Waiting {}s to avoid throttling [{} send / 30s]'.format(round(wait, 2),
        #                                                                                         self.__throttle))
        #             time.sleep(wait)
        if len(self.__event_sent_date) > 0 and 30 - (time.time() - self.__event_sent_date[0]) > 0:
            return False
        else:
            return True

    def __send(self, packet, obfuscate_after=None, ignore_throttle=0):
        # verify throttling status
        if self.__anti_throttle() or ignore_throttle:
            # verify socket instance
            if self.__wait_for_status(0):
                self.__socket.send(packet.encode('UTF-8'))
                self.__event_sent_date.append(time.time())
            # creating '**..' string with the length required
            if obfuscate_after:
                packet_hidden = '*' * (len(packet) - obfuscate_after)
                packet = packet[0:obfuscate_after] + packet_hidden
            # print to log
            self.__packet_sent(packet)

    # send a packet and log it[, obfuscate after a certain index]
    def __send_pong(self) -> None:
        # update last ping time
        self.__last_ping = time.time()
        # send new ping
        self.__send('PONG :tmi.twitch.tv\r\n', ignore_throttle=1)
        # log
        if not self.__log_settings[2]:
            self.__notice('Ping Received. Pong sent.')

    def __send_nickname(self):
        self.__send('NICK {}\r\n'.format(self.__nickname), ignore_throttle=1)

    def __send_pass(self):
        self.__send('PASS {}\r\n'.format(self.__oauth), 11, ignore_throttle=1)

    # send a message to a channel and prevent sending to disconnected channels
    def send_message(self, channel: str, message: str):
        if self.__wait_for_status():
            # if channel not connected, try to connect
            if channel not in self.channels:
                self.join(channel)
                i = 10
                while channel not in self.channels:
                    self.__warning('Channel {} not connected, wait {}s until abort'.format(channel, i))
                    i -= 1
                    time.sleep(1)
                    if i < 0:
                        break

            packet = "PRIVMSG #{} : {}\r\n".format(channel, message)
            self.__send(packet)

    # send a IRC capability request
    def __request_capabilities(self, arg: str):
        self.__send('CAP REQ :{}\r\n'.format(arg), ignore_throttle=1)

    # check IRC time out state
    def __is_timed_out(self):
        return time.time() - self.__last_ping > 300

    def __wait_for_status(self, target=3, timeout=10) -> bool:
        # if client not ready wait until ready
        if self.__status < target:
            while self.__status < target:
                self.__warning('Client not ready, current status is {} expect {},'.format(self.__status, target) +
                               ' wait {}s until abort'.format(timeout))
                if self.__status == 2 and target == 3:
                    for capabilities in self.__capabilities_acknowledged:
                        if not self.__capabilities_acknowledged[capabilities]:
                            self.__request_capabilities(capabilities)
                timeout -= 1
                time.sleep(1)
                if timeout < 0:
                    return False
        return True

    """
    parsing methods
    """

    # wrapper for parsing methods
    def parse(self, event):
        try:
            tags = self.__parse_tags(event)
            event_type = self.__parse_type(event)
            channel = self.__parse_channel(event, event_type)
            author = self.__parse_author(event)
            content = self.__parse_content(event, channel)
            return Event(event, type=event_type, tags=tags, channel=channel, author=author, content=content)
        except Exception as e:
            print(e.args)
            print(event)

    def __parse_tags(self, event):
        # Checking if there is tags
        if event[0] == '@':
            # Isolating tags (between '@' and ' :')
            tags = event[1:].split(' :')[0]
            tags = self.__parse_tags_dict(tags, ';', '=')
            # Parsing sub dict (separator : '/' and ',')
            for key in tags:
                # undocumented tag, not processed #twitch
                if key == 'flags':
                    pass
                elif key == 'msg-param-sub-plan-name':
                    tags[key] = tags[key].replace('\\s', ' ')
                # if the tag contain ':' it's a dict containing lists
                elif ':' in tags[key] and '://' not in tags[key]:
                    tags[key] = self.__parse_tags_dict(tags[key], '/', ':')
                    for sub_key in tags[key]:
                        tags[key][sub_key] = self.__parse_list(tags[key][sub_key], ',')
                        for i in range(0, len(tags[key][sub_key])):
                            tags[key][sub_key][i] = self.__parse_list(tags[key][sub_key][i], '-')

                # if the tag contain '/' it's a dict containing ints
                elif '/' in tags[key] and '//' not in tags[key]:
                    tags[key] = self.__parse_tags_dict(tags[key], ',', '/')
            return tags

    @staticmethod
    def __parse_tags_dict(tag_dict_string: str, separator_a: str, separator_b: str) -> dict:
        # Separating tags (separator : ";" )
        tag_list = tag_dict_string.split(separator_a)
        tag_dict = {}
        # Appending key/value pair in a dict
        for tag in tag_list:
            key, value = tag.split(separator_b, 1)
            # potentials escaped spaces
            value = value.replace('\\s', ' ')
            tag_dict[key] = value
        return tag_dict

    @staticmethod
    def __parse_list(list_string, separator):
        return list_string.split(separator)

    @staticmethod
    def __parse_type(event):
        split = event.split()
        for word in split:
            if word.upper() == word:
                return word

    def __parse_channel(self, event, event_type):
        # Channel in a whisper is always the client nickname
        if event_type == 'WHISPER':
            return self.__nickname
        else:
            try:
                # Channel is prefixed by ' #' and followed by a space
                return event.split(' #')[1].split()[0]
            except IndexError:
                # Some events don't belong to any channels
                return None

    @staticmethod
    def __parse_author(event):
        # author is formatted like : ':author!author@author.'
        try:
            return event.split('!')[1].split('@')[0]
        except IndexError:
            return None

    # unused dev purposes
    @staticmethod
    def __parse_author_regex(event):
        # 2 hours to create search string:
        try:
            return re.search(r':(.*?)!(\1)@(\1)\.', event).group(1)
        except IndexError:
            return None

    @staticmethod
    def __parse_content(event, channel):
        target = " :"
        if channel:
            target = channel + target
        content = event.split(target, maxsplit=1)
        return content[1] if len(content) > 1 else None

    """logging methods"""

    def __notice(self, text: str) -> None:
        if self.__log_settings[0]:
            print('\33[32m' + text + '\33[0m')
            self.__log_to_file(text, "NOTE")

    def __warning(self, text: str) -> None:
        if self.__log_settings[1]:
            print('\33[31m' + text + '\33[0m')
            self.__log_to_file(text, "WARN")

    def __packet_received(self, text: str) -> None:
        if self.__log_settings[2]:
            print('\33[36m<' + text + '\33[0m')
            self.__log_to_file(text, "RCEV")

    def __packet_sent(self, text: str) -> None:
        if self.__log_settings[3]:
            print('\33[34m>' + text.strip("\n") + '\33[0m')
            self.__log_to_file(text, "SENT")

    def __log_to_file(self, text, type):
        if self.__log_file:
            print("[{}][{}]:{}".format(datetime.datetime.now(), type, text), file=open(self.__log_file, "a+"))
