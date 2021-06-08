import googleapiclient.errors
from django.db import models
from django.db.models import Q
from google.oauth2.credentials import Credentials
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from google.auth.transport.requests import Request

from apps.users.models import Profile
import re
from datetime import timedelta
from googleapiclient.discovery import build
from UnTube import settings

import pytz


# Create your models here.

input = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
def getVideoIdsStrings(video_ids):
    output = []

    i = 0
    while i < len(video_ids):
        output.append(",".join(video_ids[i:i + 10]))
        i += 10

    return output


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

        video_seconds = timedelta(
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


class PlaylistManager(models.Manager):

    # Returns True if the video count for a playlist on UnTube and video count on same playlist on YouTube is different
    def checkIfPlaylistChangedOnYT(self, user, pl_id):
        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id="901333803283-1lscbdmukcjj3qp0t3relmla63h6l9k6.apps.googleusercontent.com",
            client_secret="ekdBniL-_mAnNPwCmugfIL2q",
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            user.profile.expires_at = credentials.expiry
            user.profile.access_token = credentials.token
            user.profile.refresh_token = credentials.refresh_token
            user.save()

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlists().list(
                part='contentDetails, snippet, id, status',
                id=pl_id,  # get playlist details for this playlist id
                maxResults=50
            )

            # execute the above request, and store the response
            try:
                pl_response = pl_request.execute()
            except googleapiclient.errors.HttpError:
                print("YouTube channel not found if mine=True")
                print("YouTube playlist not found if id=playlist_id")
                return -1

            playlist_items = []

            for item in pl_response["items"]:
                playlist_items.append(item)

            while True:
                try:
                    pl_request = youtube.playlists().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    for item in pl_response["items"]:
                        playlist_items.append(item)
                except AttributeError:
                    break

        for item in playlist_items:
            playlist_id = item["id"]

            # check if this playlist already exists in database
            if user.profile.playlists.filter(playlist_id=playlist_id).count() != 0:
                playlist = user.profile.playlists.get(playlist_id__exact=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist count changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()

    # Used to check if the user has a vaild YouTube channel
    # Will return -1 if user does not have a YouTube channel
    def getUserYTChannelID(self, user):
        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id="901333803283-1lscbdmukcjj3qp0t3relmla63h6l9k6.apps.googleusercontent.com",
            client_secret="ekdBniL-_mAnNPwCmugfIL2q",
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.channels().list(
                part='id',
                mine=True  # get playlist details for this user's playlists
            )

            pl_response = pl_request.execute()

            if pl_response['pageInfo']['totalResults'] == 0:
                print("Looks like do not have a channel on youtube. Create one to import all of your playlists. Retry?")
                return -1
            else:
                user.profile.yt_channel_id = pl_response['items'][0]['id']
                user.save()

        return 0

    # Set pl_id as None to retrive all the playlists from authenticated user. Playlists already imported will be skipped by default.
    # Set pl_id = <valid playlist id>, to import that specific playlist into the user's account
    def initPlaylist(self, user, pl_id):  # takes in playlist id and saves all of the vids in user's db
        current_user = user.profile

        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id="901333803283-1lscbdmukcjj3qp0t3relmla63h6l9k6.apps.googleusercontent.com",
            client_secret="ekdBniL-_mAnNPwCmugfIL2q",
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            user.profile.expires_at = credentials.expiry
            user.profile.access_token = credentials.token
            user.profile.refresh_token = credentials.refresh_token
            user.save()

        with build('youtube', 'v3', credentials=credentials) as youtube:
            if pl_id is not None:
                pl_request = youtube.playlists().list(
                    part='contentDetails, snippet, id, player, status',
                    id=pl_id,  # get playlist details for this playlist id
                    maxResults=50
                )
            else:
                pl_request = youtube.playlists().list(
                    part='contentDetails, snippet, id, player, status',
                    mine=True,  # get playlist details for this playlist id
                    maxResults=50
                )
            # execute the above request, and store the response
            try:
                pl_response = pl_request.execute()
            except googleapiclient.errors.HttpError:
                print("YouTube channel not found if mine=True")
                print("YouTube playlist not found if id=playlist_id")
                return -1

            if pl_response["pageInfo"]["totalResults"] == 0:
                print("No playlists created yet on youtube.")
                return -2

            playlist_items = []

            for item in pl_response["items"]:
                playlist_items.append(item)

            while True:
                try:
                    pl_request = youtube.playlists().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    for item in pl_response["items"]:
                        playlist_items.append(item)
                except AttributeError:
                    break

        for item in playlist_items:
            playlist_id = item["id"]

            # check if this playlist already exists in database
            if current_user.playlists.filter(playlist_id=playlist_id).count() != 0:
                playlist = current_user.playlists.get(playlist_id__exact=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist count changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()
            else:  # no such playlist in database
                ### MAKE THE PLAYLIST AND LINK IT TO CURRENT_USER
                playlist = Playlist(  # create the playlist and link it to current user
                    playlist_id=playlist_id,
                    name=item['snippet']['title'],
                    description=item['snippet']['description'],
                    published_at=item['snippet']['publishedAt'],
                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                    channel_id=item['snippet']['channelId'] if 'channelId' in
                                                               item['snippet'] else '',
                    channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                    item[
                                                                        'snippet'] else '',
                    video_count=item['contentDetails']['itemCount'],
                    is_private_on_yt=True if item['status']['privacyStatus'] == 'private' else False,
                    playlist_yt_player_HTML=item['player']['embedHtml'],
                    user=current_user
                )
                playlist.save()

                playlist = current_user.playlists.get(playlist_id__exact=playlist_id)

                ### GET ALL VIDEO IDS FROM THE PLAYLIST
                video_ids = []  # stores list of all video ids for a given playlist
                with build('youtube', 'v3', credentials=credentials) as youtube:
                    pl_request = youtube.playlistItems().list(
                        part='contentDetails, snippet, status',
                        playlistId=playlist_id,  # get all playlist videos details for this playlist id
                        maxResults=50
                    )

                    # execute the above request, and store the response
                    pl_response = pl_request.execute()

                    for item in pl_response['items']:
                        video_id = item['contentDetails']['videoId']

                        if playlist.videos.filter(video_id=video_id).count() == 0:  # video DNE
                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet']['description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):
                                video = Video(
                                    video_id=video_id,
                                    name=item['snippet']['title'],
                                    is_unavailable_on_yt=True,
                                    playlist=playlist,
                                    video_position=item['snippet']['position'] + 1
                                )
                                video.save()
                            else:
                                video = Video(
                                    video_id=video_id,
                                    published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                               item[
                                                                                                   'contentDetails'] else None,
                                    name=item['snippet']['title'],
                                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                    channel_id=item['snippet']['channelId'],
                                    channel_name=item['snippet']['channelTitle'],
                                    description=item['snippet']['description'],
                                    video_position=item['snippet']['position'] + 1,
                                    playlist=playlist
                                )
                                video.save()
                            video_ids.append(video_id)
                        else:  # video found in db
                            video = playlist.videos.get(video_id=video_id)

                            # check if the video became unavailable on youtube
                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet']['description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and \
                                    item['snippet']['description'] == "This video is private."):
                                video.was_deleted_on_yt = True

                            video.is_duplicate = True
                            playlist.has_duplicate_videos = True
                            video.save()

                    while True:
                        try:
                            pl_request = youtube.playlistItems().list_next(pl_request, pl_response)
                            pl_response = pl_request.execute()
                            for item in pl_response['items']:
                                video_id = item['contentDetails']['videoId']

                                if playlist.videos.filter(video_id=video_id).count() == 0:  # video DNE
                                    if (item['snippet']['title'] == "Deleted video" and
                                        item['snippet']['description'] == "This video is unavailable.") or (
                                            item['snippet']['title'] == "Private video" and \
                                            item['snippet']['description'] == "This video is private."):

                                        video = Video(
                                            video_id=video_id,
                                            published_at=item['contentDetails'][
                                                'videoPublishedAt'] if 'videoPublishedAt' in item[
                                                'contentDetails'] else None,
                                            name=item['snippet']['title'],
                                            is_unavailable_on_yt=True,
                                            playlist=playlist,
                                            video_position=item['snippet']['position'] + 1
                                        )
                                        video.save()
                                    else:
                                        video = Video(
                                            video_id=video_id,
                                            published_at=item['contentDetails'][
                                                'videoPublishedAt'] if 'videoPublishedAt' in item[
                                                'contentDetails'] else None,
                                            name=item['snippet']['title'],
                                            thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                            channel_id=item['snippet']['channelId'],
                                            channel_name=item['snippet']['channelTitle'],
                                            video_position=item['snippet']['position'] + 1,
                                            playlist=playlist
                                        )
                                        video.save()
                                    video_ids.append(video_id)
                                else:  # video found in db
                                    video = playlist.videos.get(video_id=video_id)

                                    # check if the video became unavailable on youtube
                                    if (item['snippet']['title'] == "Deleted video" and
                                        item['snippet']['description'] == "This video is unavailable.") or (
                                            item['snippet']['title'] == "Private video" and \
                                            item['snippet']['description'] == "This video is private."):
                                        video.was_deleted_on_yt = True

                                    video.is_duplicate = True
                                    playlist.has_duplicate_videos = True
                                    video.save()
                        except AttributeError:
                            break

                    # API expects the video ids to be a string of comma seperated values, not a python list
                    video_ids_strings = getVideoIdsStrings(video_ids)

                    # store duration of all the videos in the playlist
                    vid_durations = []

                    for video_ids_string in video_ids_strings:
                        # query the videos resource using API with the string above
                        vid_request = youtube.videos().list(
                            part="contentDetails,player,snippet,statistics",  # get details of eac video
                            id=video_ids_string,
                            maxResults=50
                        )

                        vid_response = vid_request.execute()

                        for item in vid_response['items']:
                            duration = item['contentDetails']['duration']
                            vid = playlist.videos.get(video_id=item['id'])
                            vid.duration = duration.replace("PT", "")
                            vid.duration_in_seconds = calculateDuration([duration])
                            vid.has_cc = True if item['contentDetails']['caption'].lower() == 'true' else False
                            vid.view_count = item['statistics']['viewCount'] if 'viewCount' in item[
                                'statistics'] else -1
                            vid.like_count = item['statistics']['likeCount'] if 'likeCount' in item[
                                'statistics'] else -1
                            vid.dislike_count = item['statistics']['dislikeCount'] if 'dislikeCount' in item[
                                'statistics'] else -1
                            vid.yt_player_HTML = item['player']['embedHtml'] if 'embedHtml' in item['player'] else ''
                            vid.save()

                            vid_durations.append(duration)

                playlist_duration_in_seconds = calculateDuration(vid_durations)

                playlist.playlist_duration_in_seconds = playlist_duration_in_seconds
                playlist.playlist_duration = str(timedelta(seconds=playlist_duration_in_seconds))

                if len(video_ids) != len(vid_durations):  # that means some videos in the playlist are deleted
                    playlist.has_unavailable_videos = True

                playlist.is_in_db = True

                playlist.save()

        if pl_id is None:
            user.profile.just_joined = False
            user.profile.import_in_progress = False
            user.save()

    def getAllPlaylistsFromYT(self, user):
        '''
        Retrieves all of user's playlists from YT and stores them in the Playlist model. Note: only stores
        the few of the columns of each playlist in every row, and has is_in_db column as false as no videos will be
        saved.
        :param user:
        :return:
        '''
        result = {"status": 0, "num_of_playlists": 0, "first_playlist_name": "N/A"}

        current_user = user.profile

        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id="901333803283-1lscbdmukcjj3qp0t3relmla63h6l9k6.apps.googleusercontent.com",
            client_secret="ekdBniL-_mAnNPwCmugfIL2q",
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            user.profile.expires_at = credentials.expiry
            user.profile.access_token = credentials.token
            user.profile.refresh_token = credentials.refresh_token
            user.save()

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlists().list(
                part='contentDetails, snippet, id, player, status',
                mine=True,  # get playlist details for this playlist id
                maxResults=50
            )
            # execute the above request, and store the response
            try:
                pl_response = pl_request.execute()
            except googleapiclient.errors.HttpError:
                print("YouTube channel not found if mine=True")
                print("YouTube playlist not found if id=playlist_id")
                result["status"] = -1
                return result

            if pl_response["pageInfo"]["totalResults"] == 0:
                print("No playlists created yet on youtube.")
                result["status"] = -2
                return result

            playlist_items = []

            for item in pl_response["items"]:
                playlist_items.append(item)

            while True:
                try:
                    pl_request = youtube.playlists().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    for item in pl_response["items"]:
                        playlist_items.append(item)
                except AttributeError:
                    break

        result["num_of_playlists"] = len(playlist_items)
        result["first_playlist_name"] = playlist_items[0]["snippet"]["title"]

        for item in playlist_items:
            playlist_id = item["id"]

            # check if this playlist already exists in database
            if current_user.playlists.filter(playlist_id=playlist_id).count() != 0:
                playlist = current_user.playlists.get(playlist_id__exact=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist count changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()
            else:  # no such playlist in database
                ### MAKE THE PLAYLIST AND LINK IT TO CURRENT_USER
                playlist = Playlist(  # create the playlist and link it to current user
                    playlist_id=playlist_id,
                    name=item['snippet']['title'],
                    description=item['snippet']['description'],
                    published_at=item['snippet']['publishedAt'],
                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                    channel_id=item['snippet']['channelId'] if 'channelId' in
                                                               item['snippet'] else '',
                    channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                    item[
                                                                        'snippet'] else '',
                    video_count=item['contentDetails']['itemCount'],
                    is_private_on_yt=True if item['status']['privacyStatus'] == 'private' else False,
                    playlist_yt_player_HTML=item['player']['embedHtml'],
                    user=current_user
                )
                playlist.save()

        return result

    def getAllVideosForPlaylist(self, user, playlist_id):

        current_user = user.profile

        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id="901333803283-1lscbdmukcjj3qp0t3relmla63h6l9k6.apps.googleusercontent.com",
            client_secret="ekdBniL-_mAnNPwCmugfIL2q",
            scopes=['https://www.googleapis.com/auth/youtube']
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            user.profile.expires_at = credentials.expiry
            user.profile.access_token = credentials.token
            user.profile.refresh_token = credentials.refresh_token
            user.save()

        playlist = current_user.playlists.get(playlist_id__exact=playlist_id)

        ### GET ALL VIDEO IDS FROM THE PLAYLIST
        video_ids = []  # stores list of all video ids for a given playlist
        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlistItems().list(
                part='contentDetails, snippet, status',
                playlistId=playlist_id,  # get all playlist videos details for this playlist id
                maxResults=50
            )

            # execute the above request, and store the response
            pl_response = pl_request.execute()

            for item in pl_response['items']:
                video_id = item['contentDetails']['videoId']

                if playlist.videos.filter(video_id=video_id).count() == 0:  # video DNE
                    if (item['snippet']['title'] == "Deleted video" and
                        item['snippet']['description'] == "This video is unavailable.") or (
                            item['snippet']['title'] == "Private video" and item['snippet'][
                        'description'] == "This video is private."):
                        video = Video(
                            video_id=video_id,
                            name=item['snippet']['title'],
                            is_unavailable_on_yt=True,
                            playlist=playlist,
                            video_position=item['snippet']['position'] + 1
                        )
                        video.save()
                    else:
                        video = Video(
                            video_id=video_id,
                            published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                       item[
                                                                                           'contentDetails'] else None,
                            name=item['snippet']['title'],
                            thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                            channel_id=item['snippet']['channelId'],
                            channel_name=item['snippet']['channelTitle'],
                            description=item['snippet']['description'],
                            video_position=item['snippet']['position'] + 1,
                            playlist=playlist
                        )
                        video.save()
                    video_ids.append(video_id)
                else:  # video found in db
                    video = playlist.videos.get(video_id=video_id)

                    # check if the video became unavailable on youtube
                    if (item['snippet']['title'] == "Deleted video" and
                        item['snippet']['description'] == "This video is unavailable.") or (
                            item['snippet']['title'] == "Private video" and item['snippet'][
                        'description'] == "This video is private."):
                        video.was_deleted_on_yt = True

                    video.is_duplicate = True
                    playlist.has_duplicate_videos = True
                    video.save()

            while True:
                try:
                    pl_request = youtube.playlistItems().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    for item in pl_response['items']:
                        video_id = item['contentDetails']['videoId']

                        if playlist.videos.filter(video_id=video_id).count() == 0:  # video DNE
                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet']['description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):

                                video = Video(
                                    video_id=video_id,
                                    published_at=item['contentDetails'][
                                        'videoPublishedAt'] if 'videoPublishedAt' in item[
                                        'contentDetails'] else None,
                                    name=item['snippet']['title'],
                                    is_unavailable_on_yt=True,
                                    playlist=playlist,
                                    video_position=item['snippet']['position'] + 1
                                )
                                video.save()
                            else:
                                video = Video(
                                    video_id=video_id,
                                    published_at=item['contentDetails'][
                                        'videoPublishedAt'] if 'videoPublishedAt' in item[
                                        'contentDetails'] else None,
                                    name=item['snippet']['title'],
                                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                    channel_id=item['snippet']['channelId'],
                                    channel_name=item['snippet']['channelTitle'],
                                    video_position=item['snippet']['position'] + 1,
                                    playlist=playlist
                                )
                                video.save()
                            video_ids.append(video_id)
                        else:  # video found in db
                            video = playlist.videos.get(video_id=video_id)

                            # check if the video became unavailable on youtube
                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet']['description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):
                                video.was_deleted_on_yt = True

                            video.is_duplicate = True
                            playlist.has_duplicate_videos = True
                            video.save()
                except AttributeError:
                    break

            # API expects the video ids to be a string of comma seperated values, not a python list
            video_ids_strings = getVideoIdsStrings(video_ids)

            # store duration of all the videos in the playlist
            vid_durations = []

            for video_ids_string in video_ids_strings:
                # query the videos resource using API with the string above
                vid_request = youtube.videos().list(
                    part="contentDetails,player,snippet,statistics",  # get details of eac video
                    id=video_ids_string,
                    maxResults=50
                )

                vid_response = vid_request.execute()

                for item in vid_response['items']:
                    duration = item['contentDetails']['duration']
                    vid = playlist.videos.get(video_id=item['id'])
                    vid.duration = duration.replace("PT", "")
                    vid.duration_in_seconds = calculateDuration([duration])
                    vid.has_cc = True if item['contentDetails']['caption'].lower() == 'true' else False
                    vid.view_count = item['statistics']['viewCount'] if 'viewCount' in item[
                        'statistics'] else -1
                    vid.like_count = item['statistics']['likeCount'] if 'likeCount' in item[
                        'statistics'] else -1
                    vid.dislike_count = item['statistics']['dislikeCount'] if 'dislikeCount' in item[
                        'statistics'] else -1
                    vid.yt_player_HTML = item['player']['embedHtml'] if 'embedHtml' in item['player'] else ''
                    vid.save()

                    vid_durations.append(duration)

        playlist_duration_in_seconds = calculateDuration(vid_durations)

        playlist.playlist_duration_in_seconds = playlist_duration_in_seconds
        playlist.playlist_duration = str(timedelta(seconds=playlist_duration_in_seconds))

        if len(video_ids) != len(vid_durations):  # that means some videos in the playlist are deleted
            playlist.has_unavailable_videos = True

        playlist.is_in_db = True

        playlist.save()


class Playlist(models.Model):
    # playlist details
    playlist_id = models.CharField(max_length=150)
    name = models.CharField(max_length=150, blank=True)
    thumbnail_url = models.CharField(max_length=420, blank=True)
    description = models.CharField(max_length=420, default="No description")
    video_count = models.IntegerField(default=0)
    published_at = models.DateTimeField(blank=True, null=True)

    # eg. "<iframe width=\"640\" height=\"360\" src=\"http://www.youtube.com/embed/videoseries?list=PLFuZstFnF1jFwMDffUhV81h0xeff0TXzm\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>"
    playlist_yt_player_HTML = models.CharField(max_length=420, blank=True)

    user = models.ForeignKey(Profile, on_delete=models.CASCADE,
                             related_name="playlists")  # a user can have many playlists
    playlist_duration = models.CharField(max_length=69, blank=True)  # string version of playlist dureation
    playlist_duration_in_seconds = models.IntegerField(default=0)
    has_unavailable_videos = models.BooleanField(default=False)  # if videos in playlist are private/deleted

    # playlist is made by this channel
    channel_id = models.CharField(max_length=420, blank=True)
    channel_name = models.CharField(max_length=420, blank=True)

    user_notes = models.CharField(max_length=420, default="")  # user can take notes on the playlist and save them
    user_label = models.CharField(max_length=100, default="")  # custom user given name for this playlist

    # manage playlist
    marked_as = models.CharField(default="",
                                 max_length=100)  # can be set to "none", "watching", "on hold", "plan to watch"
    is_favorite = models.BooleanField(default=False, blank=True)  # to mark playlist as fav
    num_of_accesses = models.IntegerField(default="0")  # tracks num of times this playlist was opened by user
    has_playlist_changed = models.BooleanField(default=False)  # determines whether playlist was modified online or not
    is_private_on_yt = models.BooleanField(default=False)
    is_from_yt = models.BooleanField(default=True)
    has_duplicate_videos = models.BooleanField(default=False)  # duplicate videos will not be shown on site

    # for UI
    view_in_grid_mode = models.BooleanField(default=False)  # if False, videso will be showed in a list

    # set playlist manager
    objects = PlaylistManager()

    # for import
    is_in_db = models.BooleanField(default=False)  # is true when all the videos of a playlist have been imported
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Playlist Len " + str(self.video_count)


class Video(models.Model):
    # video details
    video_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100, blank=True)
    duration = models.CharField(max_length=100, blank=True)
    duration_in_seconds = models.IntegerField(default=0)
    thumbnail_url = models.CharField(max_length=420, blank=True)
    published_at = models.DateTimeField(blank=True, null=True)
    description = models.CharField(max_length=420, default="")
    has_cc = models.BooleanField(default=False, blank=True, null=True)

    user_notes = models.CharField(max_length=420, default="")  # user can take notes on the video and save them

    # video stats
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    dislike_count = models.IntegerField(default=0)

    yt_player_HTML = models.CharField(max_length=420, blank=True)

    # video is made by this channel
    channel_id = models.CharField(max_length=420, blank=True)
    channel_name = models.CharField(max_length=420, blank=True)

    # which playlist this video belongs to, and position of that video in the playlist (i.e ALL videos belong to some pl)
    playlist = models.ForeignKey(Playlist, related_name="videos", on_delete=models.CASCADE)
    video_position = models.CharField(max_length=69, blank=True)

    # manage video
    is_duplicate = models.BooleanField(default=False)  # True if the same video exists more than once in the playlist
    is_unavailable_on_yt = models.BooleanField(
        default=False)  # True if the video was unavailable (private/deleted) when the API call was first made
    was_deleted_on_yt = models.BooleanField(default=False)  # True if video became unavailable on a subsequent API call
    is_marked_as_watched = models.BooleanField(default=False, blank=True)  # mark video as watched
    is_favorite = models.BooleanField(default=False, blank=True)  # mark video as favorite
    num_of_accesses = models.CharField(max_length=69,
                                       default="0")  # tracks num of times this video was clicked on by user
    user_label = models.CharField(max_length=100, default="")  # custom user given name for this video
