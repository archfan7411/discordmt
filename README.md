## Minetest-Discord Relay `[discordmt]`

A feature-filled Discord relay for Minetest, supporting:

- Relaying server chat to Discord, and Discord chat to the server
- Allowing anyone to get the server status via a command
- Logging into the server from Discord *(configurable)*
- Running commands from Discord *(configurable)*
- A simple API

## Great! How do I use it?

Easy! `discordmt` works by running a Python program which converses with a serverside mod using HTTP requests. Don't have or want Python? No problem! Binaries are also available.

If you want to run the source, however, Python 3.6.3+, `aiohttp` 3.5+ and `discord.py` 1.2.5+ are required.

### Basic setup

1. Download the mod and binary executable (or the source code and its dependencies.)
2. Create an application at the [Discord Developer Dashboard](https://discordapp.com/developers/applications/) and enable it as a bot (in the Bot tab.)
3. Copy the token from your newly-created bot, and use it to finish setting up `relay.conf`.

Example `relay.conf`: *(The token shown below has been regenerated)*
```
[BOT]
token = NjEwODk0MDU4ODY4NzAzMjMz.XVL5dA.8j8d2XN8_5UwRheG91P2XksYDoM
command_prefix = !
[RELAY]
port = 8080
channel_id = 576585506658189332
allow_logins = true
clean_invites = true
use_nicknames = true
```

4. Set `discord.port` in your `minetest.conf` to match the port you used in `relay.conf`, and grant the mod permission to use the HTTP API. You may also set `discord.text_color` to a hex color string if you'd like to color relayed messages from Discord.

Example `minetest.conf` excerpt:
```
secure.enable_security = true
secure.http_mods = discordmt
discord.port = 8080
discord.text_color = #a7a7a7
```
*(Side note: The port must be set in both `relay.conf` and `minetest.conf` because users may decide to run the relay in a different location than the mod, or to run multiple relays/servers at once.)*

5. Run the relay and, when you're ready, the Minetest server. The relay may be left up even when the server goes down, or may run continuously between several server restarts, for maximum convenience.

## Frequently Asked Questions

**Q: I just want a normal relay. Can I disable logins?**
A: Yep! Just set `allow_logins = false` in `relay.conf`.

**Q: Do I need to re-login after a server restart, like with the IRC mod?**
A: Nope, logins persist as long as the relay is up.

**Q: I'm getting an HTTP error - it says the server can't be found?**
A: Make sure the relay is running and that you've configured the correct port in both `minetest.conf` and `relay.conf`.



