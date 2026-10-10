import discord
from discord.ext import commands, tasks
import datetime
import logging
from dotenv import load_dotenv
import os

load_dotenv() # load environment file
token = os.getenv('DISCORD_TOKEN')

# logging
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()

intents.message_content = True
intents.members = True

# time
utc = datetime.timezone.utc
settings = {"hour": 0, "min": 0}

def make_time():
    return datetime.time(hour = settings["hour"], minute = settings["min"], tzinfo=utc)

def update_time():
    called_once_a_day.change_interval(time=make_time())
    called_once_a_day.restart()

# trigger daily
@tasks.loop(time=make_time())
async def called_once_a_day():
    message_channel = bot.get_channel(target_channel_id)
    print(f"Channel to send questions: {message_channel}")
    await message_channel.send(question)


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
    update_time()
    await ctx.send(f"Minutes set to: {minute}")

@set_min.error
async def set_min_error(ctx, error):
    if isinstance(error, commands.BadArgument):
        await ctx.send("Not a valid minute dummy")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Enter something... It doesn't magically appear! e.g. !set_min 30")

# print current set time
@bot.command()
async def get_time(ctx):
    await ctx.send(f"Your daily send time is set to: {make_time()}")


bot.run(token, log_handler=handler, log_level=logging.DEBUG)