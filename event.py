class Event:

    def __init__(self, raw: str, content=None, type=None, tags=None, author=None, channel=None):
        """

        :param raw: decoded IRC event
        :param content: content / message 
        :param type: type associated to the event
        :param tags: un-parsed event tags
        :param author: event author
        :param channel: channel where the event occured
        """
        self.raw = raw
        self.type = type
        self.tags = tags
        self.author = author
        self.channel = channel
