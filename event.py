class Event:

    def __init__(self, raw: str, content, event_type, tags, author, channel):
        """

        :param raw: decoded IRC event
        :param content: content / message 
        :param event_type: type associated to the event
        :param tags: un-parsed event tags
        :param author: event author
        :param channel: channel where the event occured
        """
        self.raw = raw
        self.type = event_type
        self.tags = tags
        self.author = author
        self.channel = channel

    def parse_tags(self, tags):
        pass