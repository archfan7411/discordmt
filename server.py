#!/usr/bin/env python3
import sys
from aiohttp import web
import aiohttp
import discord
from discord.ext import commands
import asyncio
import collections
import json
import time
import configparser
import re
import traceback

config = configparser.ConfigParser()

config.read('relay.conf')


class Queue:
    def __init__(self):
        self.queue = []

    def add(self, item):
        self.queue.append(item)

    def get(self):
        if len(self.queue) >= 1:
            return self.queue.pop(0)

    def get_all(self):
        items = self.queue
        self.queue = []
        return items

    def isEmpty(self):
        return len(self.queue) == 0


def clean_invites(string):
    return ' '.join(word for word in string.split()
                    if not ('discord.gg' in word) and
                    'discordapp.com/invite' not in word)


outgoing_msgs = Queue()
command_queue = Queue()
login_queue = Queue()

prefix = config['BOT']['command_prefix']

bot = commands.Bot(
    command_prefix=prefix,
    intents=discord.Intents(messages=True, message_content=True),
)

channel_id = int(config['RELAY']['channel_id'])

port = int(config['RELAY']['port'])
token = config['BOT']['token']
logins_allowed = config['RELAY'].getboolean('allow_logins')
do_clean_invites = config['RELAY'].getboolean('clean_invites')
do_use_nicknames = config['RELAY'].getboolean('use_nicknames')
if config['RELAY'].getboolean('send_every_3s'):
    incoming_msgs = collections.deque()
else:
    incoming_msgs = None

last_request = 0

channel = bot.get_partial_messageable(channel_id)
authenticated_users = {}


def check_timeout():
    return time.time() - last_request <= 1


translation_re = re.compile(r'\x1b(T|F|E|\(T@[^\)]*\))')


async def handle(request):
    global last_request
    last_request = time.time()
    try:
        data = await request.json()
        if data['type'] == 'DISCORD-RELAY-MESSAGE':
            msg = translation_re.sub('', data['content'])
            msg = discord.utils.escape_mentions(msg)[:2000]
            if 'context' in data:
                id = int(data['context'])
                target_channel = bot.get_partial_messageable(id)
                await target_channel.send(msg)
            elif incoming_msgs is None:
                await channel.send(msg)
            else:
                incoming_msgs.append(msg)

            # discord.send should NOT block extensively on the Lua side
            return web.Response(text='Acknowledged')
        if data['type'] == 'DISCORD_LOGIN_RESULT':
            user_id = int(data['user_id'])
            user = bot.get_user(user_id)
            if user is None:
                user = await bot.fetch_user(user_id)

            if data['success']:
                authenticated_users[user_id] = data['username']
                await user.send('Login successful.')
            else:
                await user.send('Login failed.')
    except Exception:
        traceback.print_exc()

    response = json.dumps({
        'messages': outgoing_msgs.get_all(),
        'commands': command_queue.get_all(),
        'logins': login_queue.get_all()
    })
    return web.Response(text=response)


app = web.Application()
app.add_routes([web.get('/', handle),
                web.post('/', handle)])


@bot.event
async def on_message(message):
    global outgoing_msgs
    if check_timeout():
        if (message.channel.id == channel_id and
                message.author.id != bot.user.id):
            msg = {
                'author': (message.author.display_name
                           if do_use_nicknames else message.author.name),
                'content': message.content.replace('\n', '/')
            }
            if do_clean_invites:
                msg['content'] = clean_invites(msg['content'])
            if msg['content'] != '':
                outgoing_msgs.add(msg)

    await bot.process_commands(message)


@bot.command(help='Runs an ingame command from Discord.')
async def cmd(ctx, command, *, args=''):
    if not check_timeout():
        await ctx.send("The server currently appears to be down.")
        return
    if ((ctx.channel.id != channel_id and ctx.guild is not None) or
            not logins_allowed):
        return
    if ctx.author.id not in authenticated_users.keys():
        await ctx.send('Not logged in.')
        return
    command = {
        'name': authenticated_users[ctx.author.id],
        'command': command,
        'params': args.replace('\n', '')
    }
    if ctx.guild is None:
        command['context'] = str(ctx.channel.id)
    command_queue.add(command)


@bot.command(help='Logs into your ingame account from Discord so you can run '
                  'commands. You should only run this command in DMs with the '
                  'bot.')
async def login(ctx, username, password=''):
    if not logins_allowed:
        return
    if ctx.guild is not None:
        await ctx.send(ctx.author.mention + ' You\'ve quite possibly just '
                       'leaked your password by using this command outside of '
                       'DMs; it is advised that you change it at once.\n*This '
                       'message will be automatically deleted.*',
                       delete_after=10)
        try:
            await ctx.message.delete()
        except discord.errros.Forbidden:
            print(f"Unable to delete possible password leak by user ID "
                  f"{ctx.author.id} due to insufficient permissions.")
        return
    login_queue.add({
        'username': username,
        'password': password,
        'user_id': str(ctx.author.id)
    })
    if not check_timeout():
        await ctx.send("The server currently appears to be down, but your "
                       "login attempt has been added to the queue and will be "
                       "executed as soon as the server returns.")


@bot.command(help='Lists connected players and server information.')
async def status(ctx, *, args=None):
    if not check_timeout():
        await ctx.send("The server currently appears to be down.")
        return
    if ctx.channel.id != channel_id and ctx.guild is not None:
        return
    data = {
        'name': 'discord_relay',
        'command': 'status',
        'params': '',
    }
    if ctx.guild is None:
        data['context'] = str(ctx.channel.id)
    command_queue.add(data)


async def send_messages():
    while True:
        await asyncio.sleep(3)
        if channel is None or not incoming_msgs:
            continue

        to_send = []
        msglen = 0
        while incoming_msgs and msglen + len(incoming_msgs[0]) <= 2000:
            msg = incoming_msgs.popleft()
            to_send.append(msg)
            msglen += len(msg) + 1

        try:
            await asyncio.wait_for(channel.send('\n'.join(to_send)),
                                   timeout=10)
        except Exception:
            traceback.print_exc()


async def on_startup(app):
    asyncio.create_task(bot.start(token))
    if incoming_msgs is not None:
        asyncio.create_task(send_messages())


app.on_startup.append(on_startup)


if __name__ == '__main__':
    try:
        print('='*37+'\nStarting relay. Press Ctrl-C to exit.\n'+'='*37)
        web.run_app(app, host='localhost', port=port)
    except KeyboardInterrupt:
        pass
