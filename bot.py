import aiohttp, discord, asyncio, json, yaml, logging, sys, imgkit, os
from datetime import datetime
from discord.ext.commands.core import command
from itertools import islice
from discord import Webhook, AsyncWebhookAdapter
from discord.ext import commands, tasks
from infoscraper import streamInfo, channelInfo

with open("settings.yaml") as f:
    settings = yaml.load(f, Loader=yaml.FullLoader)

if settings["logging"] == "info":
    logging.basicConfig(level=logging.INFO, filename='status.log', filemode='w', format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
elif settings["logging"] == "debug":
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.FileHandler('status.log', 'w', 'utf-8')], format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s')

bot = commands.Bot(command_prefix=commands.when_mentioned_or(settings["prefix"]))
bot.remove_command('help')

def chunks(data, SIZE=10000):
    it = iter(data)
    for i in range(0, len(data), SIZE):
        yield {k:data[k] for k in islice(it, SIZE)}

async def creatorCheck(ctx):
    return ctx.author.id == 256009740239241216

async def getwebhook(servers, cserver, cchannel):
    if isinstance(cserver, str) and isinstance(cchannel, str):
        cserver = bot.get_guild(int(cserver))
        cchannel = bot.get_channel(int(cchannel))
    try:
        logging.debug(f"Trying to get webhook url for {cserver.id}")
        whurl = servers[str(cserver.id)][str(cchannel.id)]["url"]
    except KeyError:
        logging.debug("Failed to get webhook url! Creating new webhook.")
        if str(cserver.id) not in servers:
            logging.debug("New server! Adding to database.")
            servers[str(cserver.id)] = {
                str(cchannel.id): {
                    "url": "",
                    "subbed": [],
                    "notified": {}
                }
            }
        elif str(cchannel.id) not in servers[str(cserver.id)]:
            logging.debug("New channel in server! Adding to database.")
            servers[str(cserver.id)][str(cchannel.id)] = {
                "url": "",
                "subbed": [],
                "notified": {}
            }
        with open("yagoo.jpg", "rb") as image:
            webhook = await cchannel.create_webhook(name="Yagoo", avatar=image.read())
        whurl = webhook.url
        servers[str(cserver.id)][str(cchannel.id)]["url"] = whurl
        with open("servers.json", "w") as f:
            json.dump(servers, f, indent=4)
    return whurl

async def streamcheck(ctx = None, test: bool = False, loop: bool = False):
    with open("channels.json", encoding="utf-8") as f:
        channels = json.load(f)
    if not test:
        cstreams = {}
        for channel in channels:
            cshrt = channels[channel]
            for x in range(2):
                try:
                    # print(f'Checking {cshrt["name"]}...')
                    if cshrt["channel"] != "":
                        status = await streamInfo(cshrt["channel"])
                        ytchannel = await channelInfo(cshrt["channel"])
                        if status["isLive"]:
                            cstreams[channel] = {
                                "name": ytchannel["name"],
                                "image": ytchannel["image"],
                                "videoId": status["videoId"],
                                "videoTitle": status["videoTitle"],
                                "timeText": status["timeText"]
                            }
                    break
                except:
                    continue
        return cstreams
    else:
        stext = ""
        stext2 = ""
        for channel in channels:
            cshrt = channels[channel]
            for x in range(2):
                try:
                    # print(f'Checking {cshrt["name"]}...')
                    if cshrt["channel"] != "":
                        status = await streamInfo(cshrt["channel"])
                        ytchan = await channelInfo(cshrt["channel"])
                        if len(stext) + len(f'{ytchan["name"]}: <:green_circle:786380003306111018>\n') <= 2000:
                            if status["isLive"]:
                                stext += f'{ytchan["name"]}: <:green_circle:786380003306111018>\n'
                            else:
                                stext += f'{ytchan["name"]}: <:red_circle:786380003306111018>\n'
                        else:
                            if status["isLive"]:
                                stext2 += f'{ytchan["name"]}: <:green_circle:786380003306111018>\n'
                            else:
                                stext2 += f'{ytchan["name"]}: <:red_circle:786380003306111018>\n'
                    break
                except:
                    if x == 2:
                        if len(stext) + len(f'{channel}: <:warning:786380003306111018>\n') <= 2000:
                            stext += f'{channel}: <:warning:786380003306111018>\n'
                        else:
                            stext2 += f'{channel}: <:warning:786380003306111018>\n'
        await ctx.send(stext.strip())
        await ctx.send(stext2.strip())

async def streamNotify(cData):
    with open("servers.json", encoding="utf-8") as f:
        servers = json.load(f)
    for server in servers:
        for channel in servers[server]:
            for ytch in cData:
                if ytch not in servers[server][channel]["notified"] and ytch in servers[server][channel]["subbed"]:
                    servers[server][channel]["notified"][ytch] = {
                        "videoId": ""
                    }
                if ytch in servers[server][channel]["subbed"] and cData[ytch]["videoId"] != servers[server][channel]["notified"][ytch]["videoId"]:
                    whurl = await getwebhook(servers, server, channel)
                    async with aiohttp.ClientSession() as session:
                        embed = discord.Embed(title=f'{cData[ytch]["videoTitle"]}', url=f'https://youtube.com/watch?v={cData[ytch]["videoId"]}')
                        embed.description = f'Started streaming {cData[ytch]["timeText"]}'
                        embed.set_image(url=f'https://img.youtube.com/vi/{cData[ytch]["videoId"]}/maxresdefault.jpg')
                        webhook = Webhook.from_url(whurl, adapter=AsyncWebhookAdapter(session))
                        await webhook.send(f'New livestream from {cData[ytch]["name"]}!', embed=embed, username=cData[ytch]["name"], avatar_url=cData[ytch]["image"])
                        servers[server][channel]["notified"][ytch]["videoId"] = cData[ytch]["videoId"]
    with open("servers.json", "w", encoding="utf-8") as f:
        servers = json.dump(servers, f, indent=4)

async def streamClean(cData):
    with open("servers.json", encoding="utf-8") as f:
        servers = json.load(f)
    livech = []
    for ytch in cData:
        livech.append(ytch)
    for server in servers:
        for channel in servers[server]:
            for ytch in servers[server][channel]["notified"]:
                if ytch not in livech:
                    servers[server][channel]["notified"].remove(ytch)
    with open("servers.json", "w", encoding="utf-8") as f:
        servers = json.dump(servers, f, indent=4)
    
class StreamCycle(commands.Cog):
    def __init__(self):
        self.timecheck.start()

    def cog_unload(self):
        self.timecheck.cancel()

    @tasks.loop(minutes=3.0)
    async def timecheck(self):
        logging.info("Starting stream checks.")
        cData = await streamcheck(loop=True)
        logging.info("Notifying channels (Stream).")
        await streamNotify(cData)
        logging.info("Stream checks done.")

async def milestoneCheck():
    with open("channels.json") as f:
        channels = json.load(f)
    
    milestone = {}
    noWrite = True

    for channel in channels:
        for x in range(2):
            try:
                ytch = await channelInfo(channels[channel]["channel"])
                if ytch["roundSubs"] > channels[channel]["milestone"]:
                    noWrite = False
                    if ytch["roundSubs"] < 1000000:
                        subtext = f'{int(ytch["roundSubs"] / 1000)}K Subscribers'
                    else:
                        if ytch["roundSubs"] == ytch["roundSubs"] - (ytch["roundSubs"] % 1000000):
                            subtext = f'{int(ytch["roundSubs"] / 1000000)}M Subscribers'
                        else:
                            subtext = f'{ytch["roundSubs"] / 1000000}M Subscribers'
                    milestone[channel] = {
                        "name": ytch["name"],
                        "image": ytch["image"],
                        "banner": ytch["mbanner"],
                        "msText": subtext
                    }
                    channels[channel]["milestone"] = ytch["roundSubs"]
                    break
            except:
                if x == 2:
                    logging.error(f'Unable to get info for {channel}!')
                    break
                else:
                    logging.warning(f'Failed to get info for {channel}. Retrying...')
    
    if not noWrite:
        with open("channels.json", "w") as f:
            json.dump(channels, f, indent=4)
    
    return milestone

async def milestoneNotify(msDict):
    with open("servers.json") as f:
        servers = json.load(f)
    for channel in msDict:
        with open("milestone/milestone.html") as f:
            msHTML = f.read()
        options = {
            "enable-local-file-access": "",
            "encoding": "UTF-8",
            "quiet": ""
        }
        msHTML = msHTML.replace('[msBanner]', msDict[channel]["banner"]).replace('[msImage]', msDict[channel]["image"]).replace('[msName]', msDict[channel]["name"]).replace('[msSubs]', msDict[channel]["msText"])
        with open("milestone/msTemp.html", "w", encoding="utf-8") as f:
            f.write(msHTML)
        imgkit.from_file("milestone/msTemp.html", f'milestone/generated/{channel}.png', options=options)
        os.remove("milestone/msTemp.html")
        for server in servers:
            for dch in servers[server]:
                if channel in servers[server][dch]["subbed"]:
                    await bot.get_channel(int(dch)).send(f'{msDict[channel]["name"]} has reached {msDict[channel]["msText"].replace("Subscribers", "subscribers")}!', file=discord.File(f'milestone/generated/{channel}.png'))
                    await bot.get_channel(int(dch)).send("おめでとう！")

class msCycle(commands.Cog):
    def __init__(self):
        self.timecheck.start()

    def cog_unload(self):
        self.timecheck.cancel()

    @tasks.loop(minutes=3.0)
    async def timecheck(self):
        logging.info("Starting milestone checks.")
        msData = await milestoneCheck()
        if msData != {}:
            logging.info("Notifying channels (Milestone).")
            await milestoneNotify(msData)
        logging.info("Milestone checks done.")

@bot.event
async def on_ready():
    print("Yagoo Bot now streaming!")
    await bot.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.watching, name='other Hololive members'))
    if settings["notify"]:
        bot.add_cog(StreamCycle())
    if settings["milestone"]:
        bot.add_cog(msCycle())

@bot.event
async def on_guild_remove(server):
    logging.info(f'Got removed from a server, cleaning up server data for: {str(server)}')
    with open("servers.json") as f:
        servers = json.load(f)
    servers.pop(str(server.id), None)
    with open("servers.json", "w") as f:
        json.dump(servers, f, indent=4)

@bot.command(aliases=['sub'])
async def subscribe(ctx):
    with open("channels.json", encoding="utf-8") as f:
        channels = json.load(f)
    csplit = []
    for split in chunks(channels, 9):
        csplit.append(split)
    first = True
    pagepos = 0
    picknum = 1
    pickstr = ""
    picklist = []
    for split in csplit[pagepos]:
        ytch = await channelInfo(csplit[pagepos][split]["channel"])
        pickstr += f'{picknum}. {ytch["name"]}\n'
        picklist.append(split)
        picknum += 1
    if pagepos == 0:
        pickstr += f'A. Subscribe to all channels\nN. Go to next page\nX. Cancel'
    elif pagepos == len(csplit) - 1:
        pickstr += f'A. Subscribe to all channels\nB. Go to previous page\nX. Cancel'
    else:
        pickstr += f'A. Subscribe to all channels\nN. Go to next page\nB. Go to previous page\nX. Cancel'

    listembed = discord.Embed(title="Subscribe to channel:", description=pickstr)
    listmsg = await ctx.send(embed=listembed)

    while True:
        if not first:
            picknum = 1
            pickstr = ""
            picklist = []
            for split in csplit[pagepos]:
                ytch = await channelInfo(csplit[pagepos][split]["channel"])
                pickstr += f'{picknum}. {ytch["name"]}\n'
                picklist.append(split)
                picknum += 1
            if pagepos == 0:
                pickstr += f'A. Subscribe to all channels\nN. Go to next page\nX. Cancel'
            elif pagepos == len(csplit) - 1:
                pickstr += f'A. Subscribe to all channels\nB. Go to previous page\nX. Cancel'
            else:
                pickstr += f'A. Subscribe to all channels\nN. Go to next page\nB. Go to previous page\nX. Cancel'

            listembed = discord.Embed(title="Subscribe to channel:", description=pickstr)
            await listmsg.edit(embed=listembed)
        else:
            first = False

        def check(m):
            print(m)
            return m.content.lower() in ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'n', 'b', 'x'] and m.author == ctx.author

        while True:
            try:
                msg = await bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await listmsg.delete()
                await ctx.message.delete()
                return
            else:
                if msg.content in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    with open("servers.json") as f:
                        servers = json.load(f)
                    await getwebhook(servers, ctx.guild, ctx.channel)
                    with open("servers.json") as f:
                        servers = json.load(f)
                    if picklist[int(msg.content) - 1] not in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
                        servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"].append(picklist[int(msg.content) - 1])
                    else:
                        ytch = await channelInfo(csplit[pagepos][picklist[int(msg.content) - 1]]["channel"])
                        await listmsg.edit(content=f'This channel is already subscribed to {ytch["name"]}.', embed=None)
                        await msg.delete()
                        await ctx.message.delete()
                        return
                    with open("servers.json", "w") as f:
                        json.dump(servers, f, indent=4)
                    ytch = await channelInfo(csplit[pagepos][picklist[int(msg.content) - 1]]["channel"])
                    await listmsg.edit(content=f'This channel is now subscribed to: {ytch["name"]}.', embed=None)
                    await msg.delete()
                    await ctx.message.delete()
                    return
                elif msg.content.lower() == 'a':
                    with open("servers.json") as f:
                        servers = json.load(f)
                    await getwebhook(servers, ctx.guild, ctx.channel)
                    with open("servers.json") as f:
                        servers = json.load(f)
                    for ytch in channels:
                        if ytch not in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
                            servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"].append(ytch)
                    with open("servers.json", "w") as f:
                        json.dump(servers, f, indent=4)
                    await listmsg.edit(content=f'This channel is now subscribed to all Hololive YouTube channels.', embed=None)
                    await msg.delete()
                    await ctx.message.delete()
                    return
                elif msg.content.lower() == 'n' and pagepos < len(csplit) - 1:
                    await msg.delete()
                    pagepos += 1
                    break
                elif msg.content.lower() == 'b' and pagepos > 0:
                    await msg.delete()
                    pagepos -= 1
                    break
                elif msg.content.lower() == 'x':
                    await msg.delete()
                    await listmsg.delete()
                    await ctx.message.delete()
                    return
                else:
                    await msg.delete()

@bot.command(aliases=["unsub"])
async def unsubscribe(ctx):
    with open("channels.json", encoding="utf-8") as f:
        channels = json.load(f)
    with open("servers.json") as f:
        servers = json.load(f)
    
    try:
        len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"])
    except:
        await ctx.send("There are no subscriptions on this channel.")
        return

    multi = False
    sublist = []
    templist = []
    if len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) > 9:
        for sub in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
            if len(templist) < 9:
                templist.append(sub)
            else:
                sublist.append(templist)
                templist = [sub]
        sublist.append(templist)
        multi = True
    elif len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) > 0 and len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) < 10:
        for sub in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
            sublist.append(sub)
    else:
        await ctx.send("There are no subscriptions on this channel.")
        return

    unsubmsg = await ctx.send("Loading subscription list...")
    
    pagepos = 0
    while True:
        dispstring = ""
        dispnum = 1
        if multi:
            subProc = sublist[pagepos]
            for sub in subProc:
                ytch = await channelInfo(channels[sub]["channel"])
                dispstring += f'{dispnum}. {ytch["name"]}\n'
                dispnum += 1
            if pagepos == 0:
                dispstring += f'A. Unsubscribe to all channels\nN. Go to next page\nX. Cancel'
            elif pagepos == len(sublist) - 1:
                dispstring += f'A. Unsubscribe to all channels\nB. Go to previous page\nX. Cancel'
            else:
                dispstring += f'A. Unsubscribe to all channels\nN. Go to next page\nB. Go to previous page\nX. Cancel'
        else:
            subProc = sublist
            for sub in sublist:
                ytch = await channelInfo(channels[sub]["channel"])
                dispstring += f'{dispnum}. {ytch["name"]}\n'
                dispnum += 1
            dispstring += f'A. Unsubscribe to all channels\nX. Cancel'
        
        usembed = discord.Embed(title="Unsubscribe from channel:", description=dispstring)
        await unsubmsg.edit(content=None, embed=usembed)

        def check(m):
            return m.content.lower() in ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'n', 'b', 'x'] and m.author == ctx.author

        while True:
            try:
                msg = await bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await unsubmsg.delete()
                await ctx.message.delete()
                return
            else:
                if msg.content in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    with open("servers.json") as f:
                        servers = json.load(f)
                    await getwebhook(servers, ctx.guild, ctx.channel)
                    with open("servers.json") as f:
                        servers = json.load(f)
                    try:
                        servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"].remove(subProc[int(msg.content) - 1])
                    except:
                        ytch = await channelInfo(channels[subProc[int(msg.content) - 1]]["channel"])
                        await unsubmsg.edit(content=f'Couldn\'t unsubscibe from: {ytch["name"]}!', embed=None)
                    else:
                        servers[str(ctx.guild.id)][str(ctx.channel.id)]["notified"].pop(subProc[int(msg.content) - 1], None)
                        ytch = await channelInfo(channels[subProc[int(msg.content) - 1]]["channel"])
                        await unsubmsg.edit(content=f'Unsubscribed from: {ytch["name"]}.', embed=None)
                    with open("servers.json", "w") as f:
                        json.dump(servers, f, indent=4)
                    await msg.delete()
                    await ctx.message.delete()
                    return
                elif msg.content.lower() == 'a':
                    with open("servers.json") as f:
                        servers = json.load(f)
                    await getwebhook(servers, ctx.guild, ctx.channel)
                    with open("servers.json") as f:
                        servers = json.load(f)
                    servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"] = []
                    servers[str(ctx.guild.id)][str(ctx.channel.id)]["notified"] = {}
                    with open("servers.json", "w") as f:
                        json.dump(servers, f, indent=4)
                    await unsubmsg.edit(content=f'This channel is now unsubscribed from any Hololive YouTube channels.', embed=None)
                    await msg.delete()
                    await ctx.message.delete()
                    return
                elif multi:
                    if msg.content.lower() == 'n' and pagepos < len(sublist) - 1:
                        await msg.delete()
                        pagepos += 1
                        break
                    elif msg.content.lower() == 'b' and pagepos > 0:
                        await msg.delete()
                        pagepos -= 1
                        break
                elif msg.content.lower() == 'x':
                    await msg.delete()
                    await unsubmsg.delete()
                    await ctx.message.delete()
                    return
                else:
                    await msg.delete()

@bot.command(aliases=["subs", "subslist", "subscriptions", "subscribed"])
async def sublist(ctx):
    with open("channels.json", encoding="utf-8") as f:
        channels = json.load(f)
    with open("servers.json") as f:
        servers = json.load(f)
    
    try:
        len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"])
    except:
        await ctx.send("There are no subscriptions on this channel.")
        return

    multi = False
    sublist = []
    templist = []
    if len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) > 10:
        for sub in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
            if len(templist) < 10:
                templist.append(sub)
            else:
                sublist.append(templist)
                templist = [sub]
        sublist.append(templist)
        multi = True
    elif len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) > 0 and len(servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]) < 11:
        for sub in servers[str(ctx.guild.id)][str(ctx.channel.id)]["subbed"]:
            sublist.append(sub)
    else:
        await ctx.send("There are no subscriptions on this channel.")
        return

    subsmsg = await ctx.send("Loading subscription list...")
    
    pagepos = 0
    realnum = 1
    while True:
        dispstring = ""
        if multi:
            subProc = sublist[pagepos]
            for sub in subProc:
                ytch = await channelInfo(channels[sub]["channel"])
                dispstring += f'{realnum}. {ytch["name"]}\n'
                realnum += 1
            if pagepos == 0:
                dispstring += f'\nN. Go to next page\nX. Remove this message'
            elif pagepos == len(sublist) - 1:
                dispstring += f'\nB. Go to previous page\nX. Remove this message'
            else:
                dispstring += f'\nN. Go to next page\nB. Go to previous page\nX. Remove this message'
        else:
            subProc = sublist
            for sub in sublist:
                ytch = await channelInfo(channels[sub]["channel"])
                dispstring += f'{realnum}. {ytch["name"]}\n'
                realnum += 1
            dispstring += f'\nX. Remove this message'
        
        subsembed = discord.Embed(title="Currently subscribed channels:", description=dispstring)
        await subsmsg.edit(content=None, embed=subsembed)

        def check(m):
            return m.content.lower() in ['n', 'b', 'x'] and m.author == ctx.author

        while True:
            try:
                msg = await bot.wait_for('message', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                return
            else:
                if msg.content.lower() == 'x':
                    await msg.delete()
                    await subsmsg.delete()
                    await ctx.message.delete()
                    return
                elif multi:
                    if msg.content.lower() == 'n' and pagepos < len(sublist) - 1:
                        await msg.delete()
                        pagepos += 1
                        break
                    elif msg.content.lower() == 'b' and pagepos > 0:
                        await msg.delete()
                        pagepos -= 1
                        realnum -= 20
                        break
                else:
                    await msg.delete()

@bot.command()
@commands.check(creatorCheck)
async def test(ctx):
    await ctx.send("Rushia Ch. \u6f64\u7fbd\u308b\u3057\u3042")

@bot.command(aliases=["livestats", "livestat"])
async def livestatus(ctx):
    loadmsg = await ctx.send("Loading info...")
    await streamcheck(ctx, True)
    await loadmsg.delete()

@bot.command()
@commands.check(creatorCheck)
async def mscheck(ctx, vtuber):
    with open("channels.json") as f:
        channels = json.load(f)

    ytch = await channelInfo(channels[vtuber]["channel"])
    if ytch["roundSubs"] < 1000000:
        subtext = f'{int(ytch["roundSubs"] / 1000)}K Subscribers'
    else:
        if ytch["roundSubs"] == ytch["roundSubs"] - (ytch["roundSubs"] % 1000000):
            subtext = f'{int(ytch["roundSubs"] / 1000000)}M Subscribers'
        else:
            subtext = f'{ytch["roundSubs"] / 1000000}M Subscribers'
    msDict = {
        vtuber: {
            "name": ytch["name"],
            "image": ytch["image"],
            "banner": ytch["mbanner"],
            "msText": subtext
        }
    }
    await milestoneNotify(msDict)
    await ctx.send(file=discord.File(f'milestone/generated/{vtuber}.png'))

@bot.command()
@commands.check(creatorCheck)
async def nstest(ctx):
    with open("servers.json") as f:
        servers = json.load(f)
    
    live = await streamcheck()
    whurl = await getwebhook(servers, ctx.guild, ctx.channel)

    for livech in live:
        async with aiohttp.ClientSession() as session:
            embed = discord.Embed(title=f'{live[livech]["videoTitle"]}', url=f'https://youtube.com/watch?v={live[livech]["videoId"]}')
            embed.description = f'Started streaming {live[livech]["timeText"]}'
            embed.set_image(url=f'https://img.youtube.com/vi/{live[livech]["videoId"]}/maxresdefault.jpg')
            webhook = Webhook.from_url(whurl, adapter=AsyncWebhookAdapter(session))
            await webhook.send(f'New livestream from {live[livech]["name"]}!', embed=embed, username=live[livech]["name"], avatar_url=live[livech]["image"])

@bot.command()
@commands.check(creatorCheck)
async def postas(ctx, vtuber, *, text):
    with open("channels.json", encoding="utf-8") as f:
        channels = json.load(f)
    with open("servers.json") as f:
        servers = json.load(f)
    whurl = await getwebhook(servers, ctx.guild, ctx.channel)
    ytch = await channelInfo(channels[vtuber]["channel"])
    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(whurl, adapter=AsyncWebhookAdapter(session))
        await webhook.send(text, username=ytch["name"], avatar_url=ytch["image"])

@bot.command(aliases=["maint", "shutdown", "stop"])
@commands.check(creatorCheck)
async def maintenance(ctx):
    await ctx.send("Changing to maintenance mode...\nBot will shut down in 5 minutes.")
    logging.info("Maintenance mode started. Shutting down in 5 minutes.")
    ctdwn = ["5 minutes", "4 minutes", "3 minutes", "2 minutes", "1 minute"]
    for x in range(5):
        if x != 4:
            await bot.change_presence(status=discord.Status.idle, activity=discord.Activity(type=discord.ActivityType.playing, name=f'Bot will undergo maintenance in {ctdwn[x]}.'))
        else:
            await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=discord.ActivityType.playing, name=f'Bot will undergo maintenance in {ctdwn[x]}.'))
        await asyncio.sleep(60)
    logging.info("Shutting down!")
    await bot.change_presence(status=discord.Status.offline)
    bot.remove_cog(StreamCycle())
    bot.remove_cog(msCycle())
    logging.info("Stopped Stream Checker.")
    dev = bot.get_user(256009740239241216)
    await dev.send("Bot has shutdown.")
    await bot.close()
    logging.info("Logged out.")
    sys.exit()

bot.run(settings["token"])
