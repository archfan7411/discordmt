#!/usr/bin/env python3
import sys
from aiohttp import web
import aiohttp
import discord
from discord.ext import commands
import asyncio
import json
import time
import configparser
import re

config = configparser.ConfigParser()

config.read('relay.conf')

class Queue():
    def __init__(self):
        self.queue = []
    def add(self, item):
        self.queue.append(item)
    def get(self):
        if len(self.queue) >=1:
            item = self.queue[0]
            del self.queue[0]
            return item
        else:
            return None
    def get_all(self):
        items = self.queue
        self.queue = []
        return items
    def isEmpty(self):
        return len(self.queue) == 0

def clean_invites(string):
    return ' '.join([word for word in string.split() if not ('discord.gg' in word) and not ('discordapp.com/invite' in word)])

outgoing_msgs = Queue()
command_queue = Queue()
login_queue = Queue()

prefix = config['BOT']['command_prefix']

bot = commands.Bot(command_prefix=prefix)

channel_id = int(config['RELAY']['channel_id'])

connected = False

port = int(config['RELAY']['port'])
token = config['BOT']['token']
logins_allowed = True if config['RELAY']['allow_logins'] == 'true' else False
do_clean_invites = True if config['RELAY']['clean_invites'] == 'true' else False
do_use_nicknames = True if config['RELAY']['use_nicknames'] == 'true' else False

last_request = 0

channel = None
authenticated_users = {}

def check_timeout():
    return time.time() - last_request <= 1

async def get_or_fetch_channel(id):
    target_channel = bot.get_channel(id)
    if target_channel is None:
        target_channel = await bot.fetch_channel(id)
        if target_channel is None:
            print(f'Failed to fetch channel {id!r}.')

    return target_channel

async def get_or_fetch_user(user_id):
    user = bot.get_user(user_id)
    if user is None:
        user = await bot.fetch_user(user_id)
        if user is None:
            print(f'Failed to fetch user {user_id!r}.')

    return user

async def handle(request):
    global last_request
    last_request = time.time()
    text = await request.text()
    try:
        data = json.loads(text)
        if data['type'] == 'DISCORD-RELAY-MESSAGE':
            msg = discord.utils.escape_mentions(data['content'])[0:2000]
            r = re.compile(r'\x1b(T|F|E|\(T@[^\)]*\))')
            msg = r.sub('', msg)
            if 'context' in data.keys():
                id = int(data['context'])
                target_channel = await get_or_fetch_channel(id)
                if target_channel is not None:
                    await target_channel.send(msg)
            else:
                await channel.send(msg)
            return web.Response(text = 'Acknowledged') # discord.send should NOT block extensively on the Lua side
        if data['type'] == 'DISCORD_LOGIN_RESULT':
            user_id = int(data['user_id'])
            user = await get_or_fetch_user(user_id)
            if user is not None:
                if data['success'] is True:
                    authenticated_users[user_id] = data['username']
                    await user.send('Login successful.')
                else:
                    await user.send('Login failed.')
    except:
        pass
    response = json.dumps({
        'messages' : outgoing_msgs.get_all(),
        'commands' : command_queue.get_all(),
        'logins' : login_queue.get_all()
    })
    return web.Response(text = response)
    

app = web.Application()
app.add_routes([web.get('/', handle),
                web.post('/', handle)])

@bot.event
async def on_ready():
    global connected
    if not connected:
        connected = True
        global channel
        channel = await bot.fetch_channel(channel_id)

@bot.event
async def on_message(message):
    global outgoing_msgs
    if check_timeout():
        if (message.channel.id == channel_id) and (message.author.id != bot.user.id):
            msg = {
                'author': message.author.name if not do_use_nicknames else message.author.display_name,
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
    if ((ctx.channel.id != channel_id) and ctx.guild is not None) or not logins_allowed:
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
        command['context'] = str(ctx.author.id)
    command_queue.add(command)
    
@bot.command(help='Logs into your ingame account from Discord so you can run commands. You should only run this command in DMs with the bot.')
async def login(ctx, username, password=''):
    if not logins_allowed:
        return
    if ctx.guild is not None:
        await ctx.send(ctx.author.mention+' You\'ve quite possibly just leaked your password by using this command outside of DMs; it is advised that you change it at once.\n*This message will be automatically deleted.*', delete_after = 10)
        try:
            await ctx.message.delete()
        except:
            print(f"Unable to delete possible password leak by user ID {ctx.author.id} due to insufficient permissions.")
        return
    login_queue.add({
        'username' : username,
        'password' : password,
        'user_id' : str(ctx.author.id)
    })
    if not check_timeout():
        await ctx.send("The server currently appears to be down, but your login attempt has been added to the queue and will be executed as soon as the server returns.")

@bot.command(help='Lists connected players and server information.')
async def status(ctx, *, args=None):
    if not check_timeout():
        await ctx.send("The server currently appears to be down.")
        return
    if ((ctx.channel.id != channel_id) and ctx.guild is not None):
        return
    data = {
        'name': 'discord_relay',
        'command': 'status',
        'params': '',
    }
    if ctx.guild is None:
        data['context'] = str(ctx.author.id)
    command_queue.add(data)

async def runServer():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()

async def runBot():
    await bot.login(token)
    await bot.connect()

try:
    print('='*37+'\nStarting relay. Press Ctrl-C to exit.\n'+'='*37)
    loop = asyncio.get_event_loop()
    futures = asyncio.gather(runBot(), runServer())
    loop.run_until_complete(futures)

except (KeyboardInterrupt, SystemExit):
    sys.exit()