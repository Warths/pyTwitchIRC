import json


class Event:

    def __init__(self, raw=None, content=None, type=None, tags=None, author=None, channel=None):
        """

        :param raw: decoded IRC event
        :param content: content / message 
        :param type: type associated to the event
        :param tags: un-parsed event tags
        :param author: event author
        :param channel: channel where the event occurred
        """
        self.raw = raw
        self.type = type
        self.tags = tags
        self.author = author
        self.channel = channel
        self.content = content

    def dump(self):
        # print(self.raw, self.type, self.tags, self.author, self.channel, self.content, sep="\r\n\t", end="\r\n")
        print("""raw : {},
        \ttype : {},
        \ttags : {},
        \tauthor : {},
        \tchannel : {},
        \tcontent : {}\r\n""".format(self.raw, self.type, self.tags, self.author, self.channel, self.content))

    def show(self):
        print("> {author} - {channel} : {content}".format(**self.__dict__))

    def emphasis(self):
        content = self.content[7:-1]
        print("> {author} - {channel} : \33[34m{}\33[0m".format(content, **self.__dict__))


class CurrentEvent(Event):

    def __init__(self, raw=None, content=None, type=None, tags=None, author=None, channel=None):
        Event.__init__(self, raw, content, type, tags, author, channel)

    def update(self, event):
        self.type = event.type
        self.tags = event.tags
        self.author = event.author
        self.channel = event.channel
        self.content = event.content


