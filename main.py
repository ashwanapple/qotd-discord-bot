import discord
from discord import app_commands
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


# time
tz = ZoneInfo("America/Vancouver")
DEFAULT_SETTINGS = {"hour": 0, "min": 0, "target_channel": None}
settings = {**DEFAULT_SETTINGS, **load_json(SETTINGS, {})}

def make_time():
    return datetime.time(hour = settings["hour"], minute = settings["min"], tzinfo=tz)

def update_time():
    called_once_a_day.change_interval(time=make_time())
    called_once_a_day.restart()

class QOTDBot(commands.Bot):
    async def setup_hook(self):
        await self.tree.sync()
        called_once_a_day.start()

    async def on_ready(self):
        print(f"Ready, {self.user.name}")

bot = QOTDBot(command_prefix=commands.when_mentioned, intents=intents)

async def send_qotd():
    if settings["target_channel"] is None:
        return "No QOTD channel set yet! Use !set_channel in your desired channel"
    
    message_channel = bot.get_channel(settings["target_channel"])

    if message_channel is None:
        return "Erm something went wrong... maybe your permissions are sus"
    
    question = await get_new_question()
    if question is None:
        return "No more questions?!"

    await message_channel.send(question)

    used = set(load_json(QUESTION_LOG, []))
    used.add(question)
    save_json(QUESTION_LOG, sorted(used))

    return None

# trigger daily
@tasks.loop(time=make_time())
async def called_once_a_day():
    error = await send_qotd()
    if error:
        print(error)

@called_once_a_day.before_loop
async def before_called_once_a_day():
    await bot.wait_until_ready()

# COMMANDS
# test command
@bot.tree.command(name="test", description="Test command")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention}!")

# set hour from user
@bot.tree.command(name="set_hour", description="Set the hour (0-23) the QOTD is sent")
async def set_hour(interaction: discord.Interaction, hour: app_commands.Range[int, 0, 23]):
    settings["hour"] = hour
    save_json(SETTINGS, settings)
    update_time()
    await interaction.response.send_message(f"Hour set to: {hour}")


# set min from user
@bot.tree.command(name="set_min", description="Set the min (0-59) the QOTD is sent")
async def set_min(interaction: discord.Interaction, minute: app_commands.Range[int, 0, 59]):
    settings["min"] = minute
    save_json(SETTINGS, settings)
    update_time()
    await interaction.response.send_message(f"Minutes set to: {minute}")

# print current set time
@bot.tree.command(name="get_time", description="Show what time the daily QOTD is sent")
async def get_time(interaction: discord.Interaction):
    await interaction.response.send_message(f"Your daily send time is set to: {settings['hour']}:{settings['min']}")

# set channel
@bot.tree.command(name="set_channel", description="Set channel for questions to be current channel")
async def set_channel(interaction: discord.Interaction):
    settings["target_channel"] = interaction.channel.id
    save_json(SETTINGS, settings)
    await interaction.response.send_message("QOTD's will be sent here")

@bot.tree.command(name="get_channel", description="Get channel where questions are sent")
async def get_channel(interaction: discord.Interaction):
    channel_id = settings["target_channel"]
    channel = bot.get_channel(channel_id) if channel_id else None
    if channel is None:
        await interaction.response.send_message("No QOTD channel set yet! Use /set_channel")
        return
    await interaction.response.send_message(f"QOTD channel: {channel.mention}")

# trigger question
@bot.tree.command(name="trigger", description="Trigger a question right now")
async def trigger(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    error = await send_qotd()
    await interaction.followup.send(error or "Question sent!", ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "missing permissions"
    else:
        msg = "Something went wrong..."
        print(f"Slash command error: {error!r}")
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)