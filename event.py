import json


class Event:

    def __init__(self, raw: str, content=None, type=None, tags=None, author=None, channel=None):
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
        self.dump()

    def dump(self):
        # print(self.raw, self.type, self.tags, self.author, self.channel, self.content, sep="\r\n\t", end="\r\n")
        print("""raw : {},
        \ttype : {},
        \ttags : {},
        \tauthor : {},
        \tchannel : {},
        \tcontent : {}\r\n""".format(self.raw, self.type, self.tags, self.author, self.channel, self.content))
