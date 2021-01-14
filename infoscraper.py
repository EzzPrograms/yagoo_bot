import json, aiohttp, asyncio, re
import logging
from bs4 import BeautifulSoup
from typing import Union

def round_down(num, divisor):
    return num - (num%divisor)

async def streamInfo(channelId: Union[str, int]):
    output = None

    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://www.youtube.com/channel/{channelId}/live?hl=en-US') as r:
            soup = BeautifulSoup(await r.text(), "html5lib")
            scripts = soup.find_all("script")
            for script in scripts:
                if ("var ytInitialData" in script.getText()) or ('window["ytInitialData"]' in script.getText()):
                    ytdata = json.loads(script.getText().replace(';', '').replace('var ytInitialData = ', '').replace('window["ytInitialData"]', ''))
                    isVideo = False
                    for cat in ytdata:
                        if cat == "playerOverlays":
                            isVideo = True
                    if isVideo:
                        morevInfo = ytdata["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"][0]["videoPrimaryInfoRenderer"]
                        if "viewCount" in morevInfo:
                            videoInfo = morevInfo["viewCount"]["videoViewCountRenderer"]
                            if videoInfo["isLive"] and ("watching now" in videoInfo["viewCount"]["runs"][0]["text"]):
                                title = ""
                                if len(morevInfo["title"]["runs"]) > 1:
                                    for subrun in morevInfo["title"]["runs"]:
                                        title += subrun["text"]
                                else:
                                    title = morevInfo["title"]["runs"][0]["text"]
                                output = {
                                    "isLive": True,
                                    "videoId": morevInfo["updatedMetadataEndpoint"]["updatedMetadataEndpoint"]["videoId"],
                                    "videoTitle": title,
                                    "timeText": morevInfo["dateText"]["simpleText"].replace('Started streaming ', '')
                                }
                            else:
                                output = {
                                    "isLive": False
                                }
    if not output:
        output = {
            "isLive": False
        }
    return output

async def channelInfo(channelId: Union[str, int]):
    channelData = None
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://www.youtube.com/channel/{channelId}?hl=en-US') as r:
            soup = BeautifulSoup(await r.text(), "html5lib")
            scripts = soup.find_all("script")
            for script in scripts:
                if ("var ytInitialData" in script.getText()) or ('window["ytInitialData"]' in script.getText()):
                    ytdata = json.loads(script.getText().replace(';', '').replace('var ytInitialData = ', '').replace('window["ytInitialData"]', ''))

                    cSubsText = ytdata["header"]["c4TabbedHeaderRenderer"]["subscriberCountText"]["simpleText"]

                    if "M" in cSubsText:
                        cSubsA = int(float(cSubsText.replace("M subscribers", "")) * 1000000)
                        cSubsR = round_down(cSubsA, 500000)
                    elif "K" in cSubsText:
                        cSubsA = int(float(cSubsText.replace("K subscribers", "")) * 1000)
                        cSubsR = round_down(cSubsA, 100000)
                    else:
                        cSubsA = None
                        cSubsR = None

                    channelData = {
                        "name": ytdata["metadata"]["channelMetadataRenderer"]["title"],
                        "formattedName": re.split(r'([a-zA-Z\xC0-\xFF]+)', ytdata["metadata"]["channelMetadataRenderer"]["title"]),
                        "image": ytdata["metadata"]["channelMetadataRenderer"]["avatar"]["thumbnails"][0]["url"],
                        "banner": ytdata["header"]["c4TabbedHeaderRenderer"]["banner"]["thumbnails"][3]["url"],
                        "mbanner": ytdata["header"]["c4TabbedHeaderRenderer"]["banner"]["thumbnails"][1]["url"],
                        "realSubs": cSubsA,
                        "roundSubs": cSubsR,
                        "success": True
                    }
    
    if channelData == None:
        channelData = {
            "success": False
        }
    return channelData

def sInfoAdapter(id):
    cData = asyncio.run(channelInfo(id))
    print(cData)

if __name__ == "__main__":
    sInfoAdapter("UC1DCedRgGHBdm81E1llLhOQ")
