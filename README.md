# pyTwitchIRC
An open source Python library to interact with the Twitch chat

# Install with pip
```pip install pytwitchirc```

# Configuration
retreive your IRC Oauth at [https://twitchapps.com/tmi/](https://twitchapps.com/tmi/)

### Example:
```
from pytwitchirc.irc import IRC

client = IRC('username', 'Oauth')

client.join('channel')
client.send('channel', 'message')
client.part('channel')
```

### Additionals optionals parameters:
| **NAME** | **USE** | **DEFAULT** | **TYPE** |
|--------------|------------------------------------------------------------------------------------------------------------------------------|--------------------|----------|
| host | the IRC server address | irc.chat.twitch.tv | str |
| port | the IRC server port | 6667 | int |
| log_settings | enable or disable log by event type following the pattern, (notice, warning, received, send), all log is disabled by default | (0, 0, 0, 0) | tuple |
| throttle | maximum number of message per 30s | 20 | int |
| log_file | path to the desired log file, if ``None`` the log is not saved,  no log file set by default | None | str |
| how_many | maximum new connection per run loop | 5 | int |
| max_try | maximum try before abort joining a channel | 5 | int |

# Related
* see the [Twitch IRC documentation](https://dev.twitch.tv/docs/irc/)
