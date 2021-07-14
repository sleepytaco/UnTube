import datetime
import humanize
import re

# given amount of seconds makes it into this 54 MINUTES AND 53 SECONDS (from humanize) then
# perform a bunch of replace operations to make it look like 54mins. 53secs.
from django.db.models import Q


def getHumanizedTimeString(seconds):
    return humanize.precisedelta(
        datetime.timedelta(seconds=seconds)).upper(). \
        replace(" month".upper(), "m.").replace(" months".upper(), "m.").replace(" days".upper(), "d.").replace(
        " day".upper(), "d.").replace(" hours".upper(), "hrs.").replace(" hour".upper(), "hr.").replace(
        " minutes".upper(), "mins.").replace(" minute".upper(), "min.").replace(
        "and".upper(), "").replace(" seconds".upper(), "secs.").replace(" second".upper(), "sec.").replace(",", "")


# input => ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", ..., "100"]  <- array of 100 video ids
# output => ["1,2,3,4,...,50", "51,52,53,...,100"]  <- array of 2 video id strings, each with upto 50 comma sperated video ids
def getVideoIdsStrings(video_ids):
    output = []

    i = 0
    while i < len(video_ids):
        output.append(",".join(video_ids[i:i + 50]))
        i += 50

    return output


# input: array of youtube video duration strings => ["24M23S", "2H2M2S", ...]
# output:integer => seconds
def calculateDuration(vid_durations):
    hours_pattern = re.compile(r'(\d+)H')
    minutes_pattern = re.compile(r'(\d+)M')
    seconds_pattern = re.compile(r'(\d+)S')

    total_seconds = 0
    for duration in vid_durations:
        hours = hours_pattern.search(duration)  # returns matches in the form "24H"
        mins = minutes_pattern.search(duration)  # "24M"
        secs = seconds_pattern.search(duration)  # "24S"

        hours = int(hours.group(1)) if hours else 0  # returns 24
        mins = int(mins.group(1)) if mins else 0
        secs = int(secs.group(1)) if secs else 0

        video_seconds = datetime.timedelta(
            hours=hours,
            minutes=mins,
            seconds=secs
        ).total_seconds()

        total_seconds += video_seconds

    return total_seconds


def getThumbnailURL(thumbnails):
    priority = ("maxres", "standard", "high", "medium", "default")

    for quality in priority:
        if quality in thumbnails:
            return thumbnails[quality]["url"]

    return ''


# generates a message in the form of "1 / 19 watched! 31mins. 15secs. left to go!"
def generateWatchingMessage(playlist):
    """
    This is the message that will be seen when a playlist is set to watching.
    Takes in the playlist object and calculates the watch time left by looping over unwatched video
    and using their durations
    """
    pass