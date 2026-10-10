import discord
from discord.ext import commands, tasks
import datetime
from zoneinfo import ZoneInfo
import logging
from dotenv import load_dotenv
import os
import aiohttp
import json


load_dotenv() # load environment file
token = os.getenv('DISCORD_TOKEN')
QOTD_API_KEY = os.getenv('API_KEY')
QUESTION_LOG = "logs.json"
SETTINGS = "settings.json"

def load_json(path, default):
    try:
        with open(path, 'r', encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path, data):
    temp = path + ".tmp"
    with open(temp, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp, path)

# fetch questions from Open API
async def fetch_question():
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        headers = {"Authorization": QOTD_API_KEY}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://api.harys.is-a.dev/v1/qotd', headers=headers) as response:
                if response.status != 200:
                    print(f"Error response status: {response.status}")
                    print(await response.text())
                    return None
                data = await response.json()
                questions = data.get("questions", [])
                return questions[0] if questions else None
    except Exception as e:
        print(f"An error occured (ohno): {e}")
        return None

# avoid duplicate questions
async def get_new_question():
    used = set(load_json(QUESTION_LOG, []))
    for _ in range(5):
        q = await fetch_question()
        if q and q not in used:
            return q
    return None

# logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()

intents.message_content = True
intents.members = True

# time
tz = ZoneInfo("America/Vancouver")
DEFAULT_SETTINGS = {"hour": 0, "min": 0, "target_channel": None}
settings = {**DEFAULT_SETTINGS, **load_json(SETTINGS, {})}

def make_time():
    return datetime.time(hour = settings["hour"], minute = settings["min"], tzinfo=tz)

def update_time():
    called_once_a_day.change_interval(time=make_time())
    called_once_a_day.restart()

# trigger daily
@tasks.loop(time=make_time())
async def called_once_a_day():
    if settings["target_channel"] is None:
        print(f"No QOTD channel set yet! Use !set_channel in your desired channel")
        return
    message_channel = bot.get_channel(settings["target_channel"])
    # print(f"Channel to send questions: {message_channel}")
    if message_channel is None:
        print(f"Erm something went wrong... maybe your permissions are sus")
        return
    
    question = await get_new_question()
    if question is None:
        print(f"No more questions?!")
        return

    await message_channel.send(question)

    used = set(load_json(QUESTION_LOG, []))
    used.add(question)
    save_json(QUESTION_LOG, sorted(used))



bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Ready, {bot.user.name}")
    if not called_once_a_day.is_running():
        called_once_a_day.start()

# COMMANDS
# test command
@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

# set hour from user
@bot.command()
async def set_hour(ctx, hour: int):
    if not 0 <= hour <= 23:
        await ctx.send("Please set a valid hour")
        return
    settings["hour"] = hour
    save_json(SETTINGS, settings)
    update_time()
    await ctx.send(f"Hour set to: {hour}")

@set_hour.error
async def set_hour_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("Not a valid hour dummy")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Enter something... It doesn't magically appear! e.g. !set_hour 5")
    else:
        raise error

# set min from user
@bot.command()
async def set_min(ctx, minute: int):
    if not 0 <= minute <= 59:
        await ctx.send("Please set a valid minute")
        return
    settings["min"] = minute
    save_json(SETTINGS, settings)
    update_time()
    await ctx.send(f"Minutes set to: {minute}")

@set_min.error
async def set_min_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("Not a valid minute dummy")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Enter something... It doesn't magically appear! e.g. !set_min 30")
    else:
        raise error

# print current set time
@bot.command()
async def get_time(ctx):
    await ctx.send(f"Your daily send time is set to: {make_time()}")

# set channel
@bot.command()
async def set_channel(ctx):
    settings["target_channel"] = ctx.channel.id
    save_json(SETTINGS, settings)
    await ctx.channel.send("QOTD's will be sent here")

@bot.command()
async def get_channel(ctx):
    await ctx.send(f"Your QOTD channel is: {bot.get_channel(settings['target_channel'])}")

# trigger question
@bot.command()
async def trigger(ctx):
    await called_once_a_day()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)