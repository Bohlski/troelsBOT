import discord
import requests
import time
import urllib
import random
import bs4
import pyimgflip
import youtube_dl
from discord.ext import commands
from requests.exceptions import HTTPError

######################################################
# TO DO:
# - Make polls with reactions? :D
# - Put cleverbot globalvariables in file or some shit
# - Fix summoner search to allow name without ""??
######################################################

bot = discord.Client()
RIOT_TOKEN = '***REMOVED***' # Needs to be updated every day.. bro.
BOT_TOKEN = '***REMOVED***'
CB_TOKEN = '***REMOVED***'
REPLY_TIMEFRAME = 3		# Minutes to wait before resetting cb
cb_last_call = 0		# Time for last call to cb
conversation_key = ''
players = {}

@bot.event
async def on_ready():
	print('Logged in.')
	print('Name : {}'.format(bot.user.name))
	print('ID : {}'.format(bot.user.id))
	print(discord.__version__)
	print('----------')


def checkpermission(message):
	print(message.author.server_permissions.value)


@bot.event
async def on_message(message):
	author = str(message.author) # Convert the Member object to a string
	# Command !troels
	if message.content.startswith('!troels'):
		print('Command !troels received...')
		await bot.send_message(message.channel, 'Ja, %s?' % (author[:-5]))
	# Command !quit
	elif message.content.startswith('!quit') and message.author.id == '166613316154687489':
		print('Command !quit received...')
		await bot.send_message(message.channel, 'Okay, %s. Shutting down...' % (author[:-5]))
		print('Logging out...\n')
		await bot.logout()
		await bot.close()
	# Command !gud - Just Troels things..
	elif message.content.startswith('!gud'):
		await bot.send_message(message.channel, 'Du kan bare kalde mig Troels.. :BrokeBack:')
	# Command !roll - returns message with roll between 0 and specified number (default: 100) 
	elif message.content.startswith('!roll'):
		print('Command !roll received...')
		roll_args = message.content.split()
		if roll_args[1].isdigit():
			await bot.send_message(message.channel, '%s rolled %s.' % (author[:-5], random.randint(0, int(roll_args[1]))))
		else:
			await bot.send_message(message.channel, '%s rolled %s.' % (author[:-5], random.randint(0, 100)))

	# Command !lolss - returns message with lol stats for given name and region
	elif message.content.startswith('!lolss'):
		search_args = message.content.split('"')
		formatted_args = []
		for arg in search_args:
			formatted_args.append(arg.strip())	# Format the arguments to allow names of several words
		if len(formatted_args) == 3:
			print('Command !lolss received...')
			summoner_name = formatted_args[1].capitalize()
			region = formatted_args[2].upper()
			await summoner_search(message, summoner_name, region)
		else:
			await bot.send_message(message.channel, '**Usage**: !lolss "<name>" <region>')

	# Command !youtube - returns a link for the top search on youtube with the given argument
	elif message.content.startswith('!youtube'):
		await youtube_search(message)
	# Command !play - Join the callers channel and play a given youtube-url
	elif message.content.startswith('!play'):
		await youtube_play(message)
	# Command !pause - Pause the current playing youtube-url
	elif message.content.startswith('!pause'):
		await youtube_pause(message)
	# Command !resume - Resume playing youtube-url
	elif message.content.startswith('!resume'):
		await youtube_resume(message)

	# Command !op.gg - returns a link for op.gg page of a given name and region (very lazy)
	elif message.content.startswith('!opgg'):
		await opgg_search(message)

	elif message.content.startswith('!sponge'):
		await spongebob_meme(message)

	# Command for everything else when bot is prompted
	elif message.content.startswith('!'):
		await cleverbot_ask(message)


def get_search_args(message):
	search_args = message.content.split('"')
	formatted_args = []
	for arg in search_args:
		formatted_args.append(arg.strip())	# Format the arguments to allow names of several words
	return formatted_args


async def cleverbot_ask(message):
	global cb_last_call
	global conversation_key
	curr_time = time.time()
	question = str(message.content)[1:]

	# If too much time has passed since last call, reset conversation key
	if (cb_last_call != 0 and curr_time - cb_last_call > REPLY_TIMEFRAME * 60):
		print('Conversation with cb reset.')
		conversation_key = ''

	print('Asking CB question: "' + question + '"')
	# Dictionary to be urlencoded. 'cs' is the key for keeping conversation info
	query = {'key':CB_TOKEN, 'input':question, 'cs': conversation_key}
	try:
		response = requests.get('https://www.cleverbot.com/getreply?%s'
								% (urllib.parse.urlencode(query)))
		response.raise_for_status()
		conversation_key = response.json()['cs']
		cb_reply = response.json()['output']
		response.close()
		await bot.send_message(message.channel, cb_reply)

	except HTTPError:
		await bot.send_message(message.channel, 'Could not contact cleverbot.')
		return
	cb_last_call = curr_time


async def summoner_search(message, summoner_name, region):
	# Dictionary to funcion as switch for looking up region names
	region_val = {'EUW': 'euw1', 'NA': 'na1', 'EUNE': 'eun1'}[region]
	lookup_url = ('https://{}.api.riotgames.com/lol/summoner/v3/summoners'
				 '/by-name/{}?api_key={}').format(region_val, summoner_name, RIOT_TOKEN)
	print('Looking up "{}" on server "{}"...'.format(summoner_name, region))	# Logging in console ...
	try:
		response = requests.get(lookup_url)
		response.raise_for_status()
		summoner_id = response.json()['id']
		summoner_level = response.json()['summonerLevel']
		response.close()
	except HTTPError:
		await bot.send_message(message.channel, '**Error during lookup of summoner id**')
		return
	# Make sure not to get ranked stats if summoner is not lvl 30
	if summoner_level != 30:
		await bot.send_message(message.channel, ('**{} ({})**\n```\nLevel: {}\n'
			'This summoner has yet to play ranked.```').format(summoner_name, region, summoner_level))
	else:
		ranked_url = ('https://{}.api.riotgames.com/lol/league/v3/positions'
						'/by-summoner/{}?api_key={}').format(region_val, summoner_id, RIOT_TOKEN)
		try:
			response = requests.get(ranked_url)
			response.raise_for_status()
			output = '**{} ({})**\n```\n'.format(summoner_name, region)
			# Append info for all queues to the output string
			for queue in response.json():
				queuetype = {'RANKED_FLEX_SR': 'FLEX 5v5', 
							'RANKED_SOLO_5x5': 'SOLO/DUO',
							'RANKED_FLEX_TT': 'FLEX 3v3'}[queue['queueType']]
				output += '|{}|\n'.format(queuetype)
				output += '>Rank: {} {} ({} LP)\n'.format(queue['tier'], queue['rank'], queue['leaguePoints'])
				wins = queue['wins']
				losses = queue['losses']
				winrate = wins/(wins+losses)*100
				output += '>Win/Loss: {}/{} ({}% winrate)\n'.format(wins, losses, round(winrate, 1))
				output += '\n'
			output += '```'
			response.close()
			await bot.send_message(message.channel, output)
		except (HTTPError, ConnectionResetError) as err:
			print(err)
			print(err.args)
			await bot.send_message(message.channel, '**Error during lookup of summoner stats**')
			return


# VIRKELIG GRIM INDTIL VIDERE
async def youtube_play(message):
	yt_url = message.content[6:]
	try:
		channel = message.author.voice.voice_channel
		voice = await bot.join_voice_channel(channel)
		player = await voice.create_ytdl_player(yt_url)
		players[message.server.id] = player
		player.start()
		await bot.send_message(message.channel, "Now playing {}.".format(player.title))
	except discord.errors.InvalidArgument:
		await bot.send_message(message.channel, "You're not in a voice channel. Please join one before using !play.")
	except Exception as error:
		print(error)
		await bot.send_message(message.channel, "Something went wrong.")


async def youtube_pause(message):
	try:
		players[message.server.id].pause()
	except:
		pass


async def youtube_resume(message):
	try:
		players[message.server.id].resume()
	except:
		pass


async def youtube_search(message):
	search_string = message.content.replace('!youtube', '').strip()
	print('Searching Youtube for "{}".'.format(search_string))
	query = urllib.parse.quote_plus(search_string)
	url = 'https://www.youtube.com/results?search_query={}'.format(query)
	try:
		response = requests.get(url)
		soup = bs4.BeautifulSoup(response.text, 'lxml')
		link = 'https://www.youtube.com{}'.format(soup.find(attrs={'class': 'yt-uix-tile-link'})['href'])
	except (HTTPError, TypeError) as err:
		print(err)
		print(err.args)
		await bot.send_message(message.channel, 'Sorry, I fucked up.. :GunterClown:')
	response.close()
	await bot.send_message(message.channel, link)


async def opgg_search(message):
	args = get_search_args(message)
	if len(args) != 3:
		await bot.send_message(message.channel, '**Usage**: !opgg "<name>" <region>')
	else:
		summoner_name = urllib.parse.quote_plus(args[1])
		region = args[2]
		print('Making op.gg url for "{}" ({})...'.format(summoner_name, region))
		url = 'https://{}.op.gg/summoner/userName={}'.format(region, summoner_name)
		await bot.send_message(message.channel, url)


async def spongebob_meme(message):
	args = get_search_args(message)
	if len(args) != 3: # I'm lazy
		await bot.send_message(message.channel, '**Usage**: !sponge "<text>"')
	else:
		spongified_word = ''
		capitalize = True
		for letter in args[1]:
			if capitalize:
				spongified_word += letter.upper()
			else:
				spongified_word += letter
			capitalize = not capitalize
		imgflip = pyimgflip.Imgflip(username='***REMOVED***', password='***REMOVED***')
		print("Generating spongebob meme..")
		result = imgflip.caption_image(102156234, spongified_word, '')
		print("Meme available at URL: " + result['url'])
		await bot.send_message(message.channel, result['url'])


if __name__ == '__main__':
	bot.run(BOT_TOKEN)