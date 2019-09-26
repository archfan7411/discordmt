## API

`discordmt` offers a simple API which other mods can use to listen to and send messages with Discord.

It does not expose the command interface or logins to the API, and `discord.register_on_message` events will *not* recieve login information.

### `discord.send(message)`
Sends `message` to Discord.
This function makes an HTTP request; therefore the sending of large volumes of data might be better grouped into a single request. **Do note that Discord limits messages to 2,000 characters, and the relay automatically cuts off messages.**

### `discord.register_on_message(function(name, message))`
Adds a function to `discord.registered_on_messages`, which are called every time a message is received from Discord, excluding logins. `name` is by default the Discord username of the user who sent the message (excluding the discriminator) and `message` is the message content. This function should be called on startup.

### `discord.chat_send_all(message)`
Sends a message to all ingame (Minetest) players. This function does **not** relay to Discord. It may, however, trigger other mods which have overriding `minetest.chat_send_all`, dependent only on the capricous nature of Minetest's mod loading.

### `discord.send_noirc(message)`
Sends a message to Discord, but does **not** relay said message to IRC. This function is *only* available if the IRC mod is enabled.
