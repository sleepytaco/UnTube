import requests
from django.contrib.auth.models import User
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from apps.users.models import Profile
from .util import *
import pytz
from UnTube.secrets import SECRETS
from django.db import models
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import timedelta
from googleapiclient.discovery import build
import googleapiclient.errors
from django.db.models import Q, Sum


class PlaylistManager(models.Manager):
    def getCredentials(self, user):
        credentials = Credentials(
            user.profile.access_token,
            refresh_token=user.profile.refresh_token,
            # id_token=session.token.get("id_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=SECRETS["GOOGLE_OAUTH_CLIENT_ID"],
            client_secret=SECRETS["GOOGLE_OAUTH_CLIENT_SECRET"],
            scopes=SECRETS["GOOGLE_OAUTH_SCOPES"]
        )

        credentials.expiry = user.profile.expires_at.replace(tzinfo=None)

        if not credentials.valid:
            # if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            user.profile.expires_at = credentials.expiry
            user.profile.access_token = credentials.token
            user.profile.refresh_token = credentials.refresh_token
            user.save()

        return credentials

    def getPlaylistId(self, video_link):
        temp = video_link.split("?")[-1].split("&")

        for el in temp:
            if "list=" in el:
                return el.split("list=")[-1]

    # Used to check if the user has a vaild YouTube channel
    # Will return -1 if user does not have a YouTube channel
    def getUserYTChannelID(self, user):
        credentials = self.getCredentials(user)

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.channels().list(
                part='id,topicDetails,status,statistics,snippet,localizations,contentOwnerDetails,contentDetails,brandingSettings',
                mine=True  # get playlist details for this user's playlists
            )

            pl_response = pl_request.execute()

            print(pl_response)

            if pl_response['pageInfo']['totalResults'] == 0:
                print("Looks like do not have a channel on youtube. Create one to import all of your playlists. Retry?")
                return -1
            else:
                user.profile.yt_channel_id = pl_response['items'][0]['id']
                user.save()

        return 0

    def initPlaylist(self, user, pl_id):  # takes in playlist id and saves all of the vids in user's db

        credentials = self.getCredentials(user)

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlists().list(
                part='contentDetails, snippet, id, player, status',
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

            print("Playlist", pl_response)

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

            # check if this playlist already exists in user's untube database
            if user.playlists.filter(playlist_id=playlist_id).exists():
                playlist = user.playlists.get(playlist_id__exact=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist count changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()

                return -3
            else:  # no such playlist in database
                ### MAKE THE PLAYLIST AND LINK IT TO CURRENT_USER
                playlist = Playlist(  # create the playlist and link it to current user
                    playlist_id=playlist_id,
                    name=item['snippet']['title'],
                    description=item['snippet']['description'],
                    published_at=item['snippet']['publishedAt'],
                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                    video_count=item['contentDetails']['itemCount'],
                    is_private_on_yt=True if item['status']['privacyStatus'] == 'private' else False,
                    playlist_yt_player_HTML=item['player']['embedHtml'],
                    untube_user=user
                )

                playlist.save()

                playlist = user.playlists.get(playlist_id=playlist_id)

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

                    print("Playlist Items", pl_response)

                    if playlist.channel_id == "":
                        playlist.channel_id = item['snippet']['channelId']
                        playlist.channel_name = item['snippet']['channelTitle']

                        if user.profile.yt_channel_id.strip() != item['snippet']['channelId']:
                            playlist.is_user_owned = False

                        playlist.save()

                    for item in pl_response['items']:
                        video_id = item['contentDetails']['videoId']

                        if not playlist.videos.filter(video_id=video_id).exists():  # video DNE
                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet']['description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):
                                video = Video(
                                    playlist_item_id=item["id"],
                                    video_id=video_id,
                                    name=item['snippet']['title'],
                                    is_unavailable_on_yt=True,
                                    video_position=item['snippet']['position'] + 1
                                )
                                video.save()
                            else:
                                video = Video(
                                    playlist_item_id=item["id"],
                                    video_id=video_id,
                                    published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                               item[
                                                                                                   'contentDetails'] else None,
                                    name=item['snippet']['title'],
                                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                    channel_id=item['snippet']['videoOwnerChannelId'],
                                    channel_name=item['snippet']['videoOwnerChannelTitle'],
                                    description=item['snippet']['description'],
                                    video_position=item['snippet']['position'] + 1,
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

                                if not playlist.videos.filter(video_id=video_id).exists():  # video DNE
                                    if (item['snippet']['title'] == "Deleted video" and
                                        item['snippet']['description'] == "This video is unavailable.") or (
                                            item['snippet']['title'] == "Private video" and \
                                            item['snippet']['description'] == "This video is private."):

                                        video = Video(
                                            playlist_item_id=item["id"],
                                            video_id=video_id,
                                            published_at=item['contentDetails'][
                                                'videoPublishedAt'] if 'videoPublishedAt' in item[
                                                'contentDetails'] else None,
                                            name=item['snippet']['title'],
                                            is_unavailable_on_yt=True,
                                            video_position=item['snippet']['position'] + 1
                                        )
                                        video.save()
                                    else:
                                        video = Video(
                                            playlist_item_id=item["id"],
                                            video_id=video_id,
                                            published_at=item['contentDetails'][
                                                'videoPublishedAt'] if 'videoPublishedAt' in item[
                                                'contentDetails'] else None,
                                            name=item['snippet']['title'],
                                            thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                            channel_id=item['snippet']['videoOwnerChannelId'],
                                            channel_name=item['snippet']['videoOwnerChannelTitle'],
                                            video_position=item['snippet']['position'] + 1,
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

                    print(video_ids)
                    print(video_ids_strings)

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

                        print("Videos()", pl_response)

                        for item in vid_response['items']:
                            duration = item['contentDetails']['duration']
                            vid = playlist.videos.get(video_id=item['id'])

                            if (item['snippet']['title'] == "Deleted video" and
                                item['snippet'][
                                    'description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):
                                playlist.has_unavailable_videos = True
                                vid_durations.append(duration)
                                vid.video_details_modified = True
                                vid.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                                vid.save(update_fields=['video_details_modified', 'video_details_modified_at',
                                                        'was_deleted_on_yt', 'is_unavailable_on_yt'])
                                continue

                            vid.name = item['snippet']['title']
                            vid.description = item['snippet']['description']
                            vid.thumbnail_url = getThumbnailURL(item['snippet']['thumbnails'])
                            vid.duration = duration.replace("PT", "")
                            vid.duration_in_seconds = calculateDuration([duration])
                            vid.has_cc = True if item['contentDetails']['caption'].lower() == 'true' else False
                            vid.view_count = item['statistics']['viewCount'] if 'viewCount' in item[
                                'statistics'] else -1
                            vid.like_count = item['statistics']['likeCount'] if 'likeCount' in item[
                                'statistics'] else -1
                            vid.dislike_count = item['statistics']['dislikeCount'] if 'dislikeCount' in item[
                                'statistics'] else -1
                            vid.comment_count = item['statistics']['commentCount'] if 'commentCount' in item[
                                'statistics'] else -1
                            vid.yt_player_HTML = item['player']['embedHtml'] if 'embedHtml' in item['player'] else ''
                            vid.save()

                            vid_durations.append(duration)

                playlist_duration_in_seconds = calculateDuration(vid_durations)

                playlist.playlist_duration_in_seconds = playlist_duration_in_seconds
                playlist.playlist_duration = getHumanizedTimeString(playlist_duration_in_seconds)

                if len(video_ids) != len(vid_durations):  # that means some videos in the playlist are deleted
                    playlist.has_unavailable_videos = True

                playlist.is_in_db = True
                # playlist.is_user_owned = False
                playlist.save()

        if pl_id is None:
            user.profile.show_import_page = False
            user.profile.import_in_progress = False
            user.save()

        return 0

    # Set pl_id as None to retrive all the playlists from authenticated user. Playlists already imported will be skipped by default.
    # Set pl_id = <valid playlist id>, to import that specific playlist into the user's account
    def initializePlaylist(self, user, pl_id=None):
        '''
        Retrieves all of user's playlists from YT and stores them in the Playlist model. Note: only stores
        the few of the columns of each playlist in every row, and has is_in_db column as false as no videos will be
        saved yet.
        :param user: django User object
        :param pl_id:
        :return:
        '''
        result = {"status": 0,
                  "num_of_playlists": 0,
                  "first_playlist_name": "N/A",
                  "playlist_ids": []}

        credentials = self.getCredentials(user)

        playlist_ids = []
        with build('youtube', 'v3', credentials=credentials) as youtube:
            if pl_id is not None:
                pl_request = youtube.playlists().list(
                    part='contentDetails, snippet, id, player, status',
                    id=pl_id,  # get playlist details for this playlist id
                    maxResults=50
                )
            else:
                print("GETTING ALL USER AUTH PLAYLISTS")
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

            if pl_id is None:
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
            playlist_ids.append(playlist_id)
            # check if this playlist already exists in user's untube collection
            if user.playlists.filter(playlist_id=playlist_id).exists():
                playlist = user.playlists.get(playlist_id=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist count changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()

                if pl_id is not None:
                    result["status"] = -3
                    return result
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
                    untube_user=user,
                    is_user_owned=True if item['snippet']['channelId'] == user.profile.yt_channel_id else False,
                    is_yt_mix=True if ("My Mix" in item['snippet']['title'] or "Mix -" in item['snippet']['title']) and
                                      item['snippet']['channelId'] == "UCBR8-60-B28hp2BmDPdntcQ" else False
                )
                playlist.save()

        result["playlist_ids"] = playlist_ids

        return result

    def getAllVideosForPlaylist(self, user, playlist_id):
        credentials = self.getCredentials(user)

        playlist = user.playlists.get(playlist_id=playlist_id)

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
                playlist_item_id = item["id"]
                video_id = item['contentDetails']['videoId']
                video_ids.append(video_id)

                # video DNE in user's untube:
                # 1. create and save the video in user's untube
                # 2. add it to playlist
                # 3. make a playlist item which is linked to the video
                if not user.videos.filter(video_id=video_id).exists():
                    if item['snippet']['title'] == "Deleted video" or item['snippet'][
                        'description'] == "This video is unavailable." or item['snippet']['title'] == "Private video" or \
                            item['snippet']['description'] == "This video is private.":
                        video = Video(
                            video_id=video_id,
                            name=item['snippet']['title'],
                            description=item['snippet']['description'],
                            is_unavailable_on_yt=True,
                            untube_user=user
                        )
                        video.save()
                    else:
                        video = Video(
                            video_id=video_id,
                            published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                       item[
                                                                                           'contentDetails'] else None,
                            name=item['snippet']['title'],
                            description=item['snippet']['description'],
                            thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                            channel_id=item['snippet']['videoOwnerChannelId'],
                            channel_name=item['snippet']['videoOwnerChannelTitle'],
                            untube_user=user
                        )
                        video.save()

                    playlist.videos.add(video)

                    playlist_item = PlaylistItem(
                        playlist_item_id=playlist_item_id,
                        published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                       item[
                                                                           'snippet'] else None,
                        channel_id=item['snippet']['channelId'],
                        channel_name=item['snippet']['channelTitle'],
                        video_position=item['snippet']['position'],
                        playlist=playlist,
                        video=video
                    )
                    playlist_item.save()
                else:  # video found in user's db
                    video = user.videos.get(video_id=video_id)

                    # if video already in playlist.videos
                    is_duplicate = False
                    if playlist.videos.filter(video_id=video_id).exists():
                        playlist.has_duplicate_videos = True
                        is_duplicate = True
                    else:
                        playlist.videos.add(video)
                    playlist_item = PlaylistItem(
                        playlist_item_id=playlist_item_id,
                        published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                       item[
                                                                           'snippet'] else None,
                        channel_id=item['snippet']['channelId'] if 'channelId' in
                                                                   item[
                                                                       'snippet'] else None,
                        channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                        item[
                                                                            'snippet'] else None,
                        video_position=item['snippet']['position'],
                        playlist=playlist,
                        video=video,
                        is_duplicate=is_duplicate

                    )
                    playlist_item.save()

                    # check if the video became unavailable on youtube
                    if not video.is_unavailable_on_yt and not video.was_deleted_on_yt and (item['snippet']['title'] == "Deleted video" or
                                                           item['snippet'][
                                                               'description'] == "This video is unavailable.") or (
                            item['snippet']['title'] == "Private video" or item['snippet'][
                        'description'] == "This video is private."):
                        video.was_deleted_on_yt = True
                        playlist.has_unavailable_videos = True
                        video.save(update_fields=['was_deleted_on_yt'])

            while True:
                try:
                    pl_request = youtube.playlistItems().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    for item in pl_response['items']:
                        playlist_item_id = item["id"]
                        video_id = item['contentDetails']['videoId']
                        video_ids.append(video_id)

                        # video DNE in user's untube:
                        # 1. create and save the video in user's untube
                        # 2. add it to playlist
                        # 3. make a playlist item which is linked to the video
                        if not user.videos.filter(video_id=video_id).exists():
                            if item['snippet']['title'] == "Deleted video" or item['snippet'][
                                'description'] == "This video is unavailable." or item['snippet'][
                                'title'] == "Private video" or \
                                    item['snippet']['description'] == "This video is private.":
                                video = Video(
                                    video_id=video_id,
                                    name=item['snippet']['title'],
                                    description=item['snippet']['description'],
                                    is_unavailable_on_yt=True,
                                    untube_user=user
                                )
                                video.save()
                            else:
                                video = Video(
                                    video_id=video_id,
                                    published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                               item[
                                                                                                   'contentDetails'] else None,
                                    name=item['snippet']['title'],
                                    description=item['snippet']['description'],
                                    thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                    channel_id=item['snippet']['videoOwnerChannelId'],
                                    channel_name=item['snippet']['videoOwnerChannelTitle'],
                                    untube_user=user
                                )
                                video.save()

                            playlist.videos.add(video)

                            playlist_item = PlaylistItem(
                                playlist_item_id=playlist_item_id,
                                published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                               item[
                                                                                   'snippet'] else None,
                                channel_id=item['snippet']['channelId'],
                                channel_name=item['snippet']['channelTitle'],
                                video_position=item['snippet']['position'],
                                playlist=playlist,
                                video=video
                            )
                            playlist_item.save()
                        else:  # video found in user's db
                            video = user.videos.get(video_id=video_id)

                            # if video already in playlist.videos
                            is_duplicate = False
                            if playlist.videos.filter(video_id=video_id).exists():
                                playlist.has_duplicate_videos = True
                                is_duplicate = True
                            else:
                                playlist.videos.add(video)
                            playlist_item = PlaylistItem(
                                playlist_item_id=playlist_item_id,
                                published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                               item[
                                                                                   'snippet'] else None,
                                channel_id=item['snippet']['channelId'] if 'channelId' in
                                                                           item[
                                                                               'snippet'] else None,
                                channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                                item[
                                                                                    'snippet'] else None,
                                video_position=item['snippet']['position'],
                                playlist=playlist,
                                video=video,
                                is_duplicate=is_duplicate
                            )
                            playlist_item.save()

                            # check if the video became unavailable on youtube
                            if not video.is_unavailable_on_yt and not video.was_deleted_on_yt and (item['snippet']['title'] == "Deleted video" or
                                                                   item['snippet'][
                                                                       'description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" or item['snippet'][
                                'description'] == "This video is private."):
                                video.was_deleted_on_yt = True
                                playlist.has_unavailable_videos = True
                                video.save(update_fields=['was_deleted_on_yt'])


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

                    vid.name = item['snippet']['title']
                    vid.description = item['snippet']['description']
                    vid.thumbnail_url = getThumbnailURL(item['snippet']['thumbnails'])
                    vid.duration = duration.replace("PT", "")
                    vid.duration_in_seconds = calculateDuration([duration])
                    vid.has_cc = True if item['contentDetails']['caption'].lower() == 'true' else False
                    vid.view_count = item['statistics']['viewCount'] if 'viewCount' in item[
                        'statistics'] else -1
                    vid.like_count = item['statistics']['likeCount'] if 'likeCount' in item[
                        'statistics'] else -1
                    vid.dislike_count = item['statistics']['dislikeCount'] if 'dislikeCount' in item[
                        'statistics'] else -1
                    vid.comment_count = item['statistics']['commentCount'] if 'commentCount' in item[
                        'statistics'] else -1
                    vid.yt_player_HTML = item['player']['embedHtml'] if 'embedHtml' in item['player'] else ''
                    vid.save()

                    vid_durations.append(duration)

        playlist_duration_in_seconds = calculateDuration(vid_durations)

        playlist.playlist_duration_in_seconds = playlist_duration_in_seconds
        playlist.playlist_duration = getHumanizedTimeString(playlist_duration_in_seconds)

        if len(video_ids) != len(vid_durations):  # that means some videos in the playlist are deleted
            playlist.has_unavailable_videos = True

        playlist.is_in_db = True

        playlist.save()

    # Returns True if the video count for a playlist on UnTube and video count on same playlist on YouTube is different
    def checkIfPlaylistChangedOnYT(self, user, pl_id):
        """
        If full_scan is true, the whole playlist (i.e each and every video from the PL on YT and PL on UT, is scanned and compared)
        is scanned to see if there are any missing/deleted/newly added videos. This will be only be done
        weekly by looking at the playlist.last_full_scan_at

        If full_scan is False, only the playlist count difference on YT and UT is checked on every visit
        to the playlist page. This is done everytime.
        """
        credentials = self.getCredentials(user)

        playlist = user.playlists.get(playlist_id=pl_id)

        # if its been a week since the last full scan, do a full playlist scan
        # basically checks all the playlist video for any updates
        if playlist.last_full_scan_at + datetime.timedelta(minutes=2) < datetime.datetime.now(pytz.utc):
            print("DOING A FULL SCAN")
            current_video_ids = [playlist_item.video_id for playlist_item in playlist.playlist_items.all()]
            current_playlist_item_ids = [playlist_item.playlist_item_id for playlist_item in
                                         playlist.playlist_items.all()]

            deleted_videos, unavailable_videos, added_videos = 0, 0, 0

            ### GET ALL VIDEO IDS FROM THE PLAYLIST
            video_ids = []  # stores list of all video ids for a given playlist
            with build('youtube', 'v3', credentials=credentials) as youtube:
                pl_request = youtube.playlistItems().list(
                    part='contentDetails, snippet, status',
                    playlistId=pl_id,  # get all playlist videos details for this playlist id
                    maxResults=50
                )

                # execute the above request, and store the response
                pl_response = pl_request.execute()

                for item in pl_response['items']:
                    playlist_item_id = item['id']
                    video_id = item['contentDetails']['videoId']

                    if not playlist.playlist_items.filter(
                            playlist_item_id=playlist_item_id).exists():  # if playlist item DNE in playlist, a new vid added to playlist
                        added_videos += 1
                        video_ids.append(video_id)
                    else:  # playlist_item found in playlist
                        if playlist_item_id in current_playlist_item_ids:
                            video_ids.append(video_id)
                            current_playlist_item_ids.remove(playlist_item_id)

                        video = playlist.videos.get(video_id=video_id)
                        # check if the video became unavailable on youtube
                        if not video.is_unavailable_on_yt and not video.was_deleted_on_yt:
                            if (item['snippet']['title'] == "Deleted video" or
                                item['snippet']['description'] == "This video is unavailable." or
                                    item['snippet']['title'] == "Private video" or item['snippet'][
                                'description'] == "This video is private."):
                                unavailable_videos += 1

                while True:
                    try:
                        pl_request = youtube.playlistItems().list_next(pl_request, pl_response)
                        pl_response = pl_request.execute()

                        for item in pl_response['items']:
                            playlist_item_id = item['id']
                            video_id = item['contentDetails']['videoId']

                            if not playlist.playlist_items.filter(
                                    playlist_item_id=playlist_item_id).exists():  # if playlist item DNE in playlist, a new vid added to playlist
                                added_videos += 1
                                video_ids.append(video_id)
                            else:  # playlist_item found in playlist
                                if playlist_item_id in current_playlist_item_ids:
                                    video_ids.append(video_id)
                                    current_playlist_item_ids.remove(playlist_item_id)

                                video = playlist.videos.get(video_id=video_id)
                                # check if the video became unavailable on youtube
                                if not video.is_unavailable_on_yt and not video.was_deleted_on_yt:
                                    if (item['snippet']['title'] == "Deleted video" or
                                        item['snippet']['description'] == "This video is unavailable." or
                                            item['snippet']['title'] == "Private video" or item['snippet'][
                                        'description'] == "This video is private."):
                                        unavailable_videos += 1
                    except AttributeError:
                        break

            playlist.last_full_scan_at = datetime.datetime.now(pytz.utc)

            playlist.save()

            deleted_videos = len(current_playlist_item_ids)  # left out video ids

            return [1, deleted_videos, unavailable_videos, added_videos]

        """
        print("DOING A SMOL SCAN")

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

            print("PLAYLIST", pl_response)

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
            if user.playlists.filter(playlist_id=playlist_id).exists():
                playlist = user.playlists.get(playlist_id__exact=playlist_id)
                print(f"PLAYLIST {playlist.name} ALREADY EXISTS IN DB")

                # POSSIBLE CASES:
                # 1. PLAYLIST HAS DUPLICATE VIDEOS, DELETED VIDS, UNAVAILABLE VIDS

                # check if playlist changed on youtube
                if playlist.video_count != item['contentDetails']['itemCount']:
                    playlist.has_playlist_changed = True
                    playlist.save()
                    return [-1, item['contentDetails']['itemCount']]
        """

        return [0, "no change"]

    def updatePlaylist(self, user, playlist_id):
        credentials = self.getCredentials(user)

        playlist = user.playlists.get(playlist_id__exact=playlist_id)
        playlist.has_duplicate_videos = False  # reset this to false for now
        has_duplicate_videos = False

        current_video_ids = [playlist_item.video.video_id for playlist_item in playlist.playlist_items.all()]
        current_playlist_item_ids = [playlist_item.playlist_item_id for playlist_item in playlist.playlist_items.all()]

        updated_playlist_video_count = 0

        deleted_playlist_item_ids, unavailable_videos, added_videos = [], [], []

        ### GET ALL VIDEO IDS FROM THE PLAYLIST
        video_ids = []  # stores list of all video ids for a given playlist
        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlistItems().list(
                part='contentDetails, snippet, status',
                playlistId=playlist_id,  # get all playlist videos details for this playlist id
                maxResults=50
            )

            # execute the above request, and store the response
            try:
                pl_response = pl_request.execute()
            except googleapiclient.errors.HttpError:
                print("Playist was deleted on YouTube")
                return [-1, [], [], []]

            print("ESTIMATED VIDEO IDS FROM RESPONSE", len(pl_response["items"]))
            updated_playlist_video_count += len(pl_response["items"])
            for item in pl_response['items']:
                playlist_item_id = item["id"]
                video_id = item['contentDetails']['videoId']
                video_ids.append(video_id)

                # check if new playlist item added
                if not playlist.playlist_items.filter(playlist_item_id=playlist_item_id).exists():
                    # if video dne in user's db at all, create and save it
                    if not user.videos.filter(video_id=video_id).exists():
                        if (item['snippet']['title'] == "Deleted video" and item['snippet'][
                            'description'] == "This video is unavailable.") or (item['snippet'][
                            'title'] == "Private video" and item['snippet']['description'] == "This video is private."):
                            video = Video(
                                video_id=video_id,
                                name=item['snippet']['title'],
                                description=item['snippet']['description'],
                                is_unavailable_on_yt=True,
                                untube_user=user
                            )
                            video.save()
                        else:
                            video = Video(
                                video_id=video_id,
                                published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                           item[
                                                                                               'contentDetails'] else None,
                                name=item['snippet']['title'],
                                description=item['snippet']['description'],
                                thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                channel_id=item['snippet']['videoOwnerChannelId'],
                                channel_name=item['snippet']['videoOwnerChannelTitle'],
                                untube_user=user
                            )
                            video.save()

                    video = user.videos.get(video_id=video_id)

                    # check if the video became unavailable on youtube
                    if not video.is_unavailable_on_yt and not video.was_deleted_on_yt and (item['snippet']['title'] == "Deleted video" and
                                                           item['snippet'][
                                                               'description'] == "This video is unavailable.") or (
                            item['snippet']['title'] == "Private video" and item['snippet'][
                        'description'] == "This video is private."):
                        video.was_deleted_on_yt = True
                        playlist.has_unavailable_videos = True

                    is_duplicate = False
                    if not playlist.videos.filter(video_id=video_id).exists():
                        playlist.videos.add(video)
                    else:
                        is_duplicate = True
                        has_duplicate_videos = True

                    playlist_item = PlaylistItem(
                        playlist_item_id=playlist_item_id,
                        published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                       item[
                                                                           'snippet'] else None,
                        channel_id=item['snippet']['channelId'] if 'channelId' in
                                                                   item[
                                                                       'snippet'] else None,
                        channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                        item[
                                                                            'snippet'] else None,
                        video_position=item['snippet']['position'],
                        playlist=playlist,
                        video=video,
                        is_duplicate=is_duplicate
                    )
                    playlist_item.save()

                    video.video_details_modified = True
                    video.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                    video.save(update_fields=['video_details_modified', 'video_details_modified_at', 'was_deleted_on_yt'])
                    added_videos.append(video)

                else:  # if playlist item already in playlist
                    current_playlist_item_ids.remove(playlist_item_id)

                    playlist_item = playlist.playlist_items.get(playlist_item_id=playlist_item_id)
                    playlist_item.video_position = item['snippet']['position']
                    playlist_item.save(update_fields=['video_position'])

                    # check if the video became unavailable on youtube
                    if not playlist_item.video.is_unavailable_on_yt and not playlist_item.video.was_deleted_on_yt:
                        if (item['snippet']['title'] == "Deleted video" and
                            item['snippet']['description'] == "This video is unavailable.") or (
                                item['snippet']['title'] == "Private video" and item['snippet'][
                            'description'] == "This video is private."):
                            playlist_item.video.was_deleted_on_yt = True  # video went private on YouTube
                            playlist_item.video.video_details_modified = True
                            playlist_item.video.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                            playlist_item.video.save(update_fields=['was_deleted_on_yt', 'video_details_modified',
                                                      'video_details_modified_at'])

                            unavailable_videos.append(playlist_item.video)

            while True:
                try:
                    pl_request = youtube.playlistItems().list_next(pl_request, pl_response)
                    pl_response = pl_request.execute()
                    updated_playlist_video_count += len(pl_response["items"])
                    for item in pl_response['items']:
                        playlist_item_id = item["id"]
                        video_id = item['contentDetails']['videoId']
                        video_ids.append(video_id)

                        # check if new playlist item added
                        if not playlist.playlist_items.filter(playlist_item_id=playlist_item_id).exists():
                            # if video dne in user's db at all, create and save it
                            if not user.videos.filter(video_id=video_id).exists():
                                if (item['snippet']['title'] == "Deleted video" and item['snippet'][
                                    'description'] == "This video is unavailable.") or (item['snippet'][
                                                                                            'title'] == "Private video" and
                                                                                        item['snippet'][
                                                                                            'description'] == "This video is private."):
                                    video = Video(
                                        video_id=video_id,
                                        name=item['snippet']['title'],
                                        description=item['snippet']['description'],
                                        is_unavailable_on_yt=True,
                                        untube_user=user
                                    )
                                    video.save()
                                else:
                                    video = Video(
                                        video_id=video_id,
                                        published_at=item['contentDetails']['videoPublishedAt'] if 'videoPublishedAt' in
                                                                                                   item[
                                                                                                       'contentDetails'] else None,
                                        name=item['snippet']['title'],
                                        description=item['snippet']['description'],
                                        thumbnail_url=getThumbnailURL(item['snippet']['thumbnails']),
                                        channel_id=item['snippet']['videoOwnerChannelId'],
                                        channel_name=item['snippet']['videoOwnerChannelTitle'],
                                        untube_user=user
                                    )
                                    video.save()

                            video = user.videos.get(video_id=video_id)

                            # check if the video became unavailable on youtube
                            if not video.is_unavailable_on_yt and not video.was_deleted_on_yt and (item['snippet']['title'] == "Deleted video" and
                                                                   item['snippet'][
                                                                       'description'] == "This video is unavailable.") or (
                                    item['snippet']['title'] == "Private video" and item['snippet'][
                                'description'] == "This video is private."):
                                video.was_deleted_on_yt = True
                                playlist.has_unavailable_videos = True

                            is_duplicate = False
                            if not playlist.videos.filter(video_id=video_id).exists():
                                playlist.videos.add(video)
                            else:
                                is_duplicate = True
                                has_duplicate_videos = True

                            playlist_item = PlaylistItem(
                                playlist_item_id=playlist_item_id,
                                published_at=item['snippet']['publishedAt'] if 'publishedAt' in
                                                                               item[
                                                                                   'snippet'] else None,
                                channel_id=item['snippet']['channelId'] if 'channelId' in
                                                                           item[
                                                                               'snippet'] else None,
                                channel_name=item['snippet']['channelTitle'] if 'channelTitle' in
                                                                                item[
                                                                                    'snippet'] else None,
                                video_position=item['snippet']['position'],
                                playlist=playlist,
                                video=video,
                                is_duplicate=is_duplicate
                            )
                            playlist_item.save()

                            video.video_details_modified = True
                            video.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                            video.save(update_fields=['video_details_modified', 'video_details_modified_at',
                                                      'was_deleted_on_yt'])
                            added_videos.append(video)

                        else:  # if playlist item already in playlist
                            current_playlist_item_ids.remove(playlist_item_id)
                            playlist_item = playlist.playlist_items.get(playlist_item_id=playlist_item_id)
                            playlist_item.video_position = item['snippet']['position']
                            playlist_item.save(update_fields=['video_position'])

                            # check if the video became unavailable on youtube
                            if not playlist_item.video.is_unavailable_on_yt and not playlist_item.video.was_deleted_on_yt:
                                if (item['snippet']['title'] == "Deleted video" and
                                    item['snippet']['description'] == "This video is unavailable.") or (
                                        item['snippet']['title'] == "Private video" and item['snippet'][
                                    'description'] == "This video is private."):
                                    playlist_item.video.was_deleted_on_yt = True  # video went private on YouTube
                                    playlist_item.video.video_details_modified = True
                                    playlist_item.video.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                                    playlist_item.video.save(
                                        update_fields=['was_deleted_on_yt', 'video_details_modified',
                                                       'video_details_modified_at'])

                                    unavailable_videos.append(playlist_item.video)

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

                    if (item['snippet']['title'] == "Deleted video" or
                        item['snippet'][
                            'description'] == "This video is unavailable.") or (
                            item['snippet']['title'] == "Private video" or item['snippet'][
                        'description'] == "This video is private."):

                        playlist.has_unavailable_videos = True
                        vid_durations.append(duration)
                        vid.video_details_modified = True
                        vid.video_details_modified_at = datetime.datetime.now(tz=pytz.utc)
                        vid.save(
                            update_fields=['video_details_modified', 'video_details_modified_at', 'was_deleted_on_yt',
                                           'is_unavailable_on_yt'])
                        continue

                    vid.name = item['snippet']['title']
                    vid.description = item['snippet']['description']
                    vid.thumbnail_url = getThumbnailURL(item['snippet']['thumbnails'])
                    vid.duration = duration.replace("PT", "")
                    vid.duration_in_seconds = calculateDuration([duration])
                    vid.has_cc = True if item['contentDetails']['caption'].lower() == 'true' else False
                    vid.view_count = item['statistics']['viewCount'] if 'viewCount' in item[
                        'statistics'] else -1
                    vid.like_count = item['statistics']['likeCount'] if 'likeCount' in item[
                        'statistics'] else -1
                    vid.dislike_count = item['statistics']['dislikeCount'] if 'dislikeCount' in item[
                        'statistics'] else -1
                    vid.comment_count = item['statistics']['commentCount'] if 'commentCount' in item[
                        'statistics'] else -1
                    vid.yt_player_HTML = item['player']['embedHtml'] if 'embedHtml' in item['player'] else ''
                    vid.save()

                    vid_durations.append(duration)

        playlist_duration_in_seconds = calculateDuration(vid_durations)

        playlist.playlist_duration_in_seconds = playlist_duration_in_seconds
        playlist.playlist_duration = getHumanizedTimeString(playlist_duration_in_seconds)

        if len(video_ids) != len(vid_durations) or len(
                unavailable_videos) != 0:  # that means some videos in the playlist became private/deleted
            playlist.has_unavailable_videos = True

        playlist.has_playlist_changed = False
        playlist.video_count = updated_playlist_video_count
        playlist.has_new_updates = True
        playlist.save()

        playlist.has_duplicate_videos = has_duplicate_videos

        deleted_playlist_item_ids = current_playlist_item_ids  # left out playlist_item_ids

        return [0, deleted_playlist_item_ids, unavailable_videos, added_videos]

    def deletePlaylistItems(self, user, playlist_id, playlist_item_ids):
        """
        Takes in playlist itemids for the videos in a particular playlist
        """
        credentials = self.getCredentials(user)
        playlist = user.playlists.get(playlist_id=playlist_id)

        # new_playlist_duration_in_seconds = playlist.playlist_duration_in_seconds
        # new_playlist_video_count = playlist.video_count
        with build('youtube', 'v3', credentials=credentials) as youtube:
            for playlist_item_id in playlist_item_ids:
                pl_request = youtube.playlistItems().delete(
                    id=playlist_item_id
                )
                print(pl_request)
                try:
                    pl_response = pl_request.execute()
                    print(pl_response)
                except googleapiclient.errors.HttpError as e:  # failed to delete playlist item
                    # possible causes:
                    # playlistItemsNotAccessible (403)
                    # playlistItemNotFound (404)
                    # playlistOperationUnsupported (400)
                    print(e, e.error_details, e.status_code)
                    continue

                # playlistItem was successfully deleted if no HttpError, so delete it from db
                # video = playlist.videos.get(playlist_item_id=playlist_item_id)
                # new_playlist_video_count -= 1
                # new_playlist_duration_in_seconds -= video.duration_in_seconds
                # video.delete()

        # playlist.video_count = new_playlist_video_count
        # playlist.playlist_duration_in_seconds = new_playlist_duration_in_seconds
        # playlist.playlist_duration = getHumanizedTimeString(new_playlist_duration_in_seconds)
        # playlist.save(update_fields=['video_count', 'playlist_duration', 'playlist_duration_in_seconds'])
        # time.sleep(2)

    def updatePlaylistDetails(self, user, playlist_id, details):
        """
        Takes in playlist itemids for the videos in a particular playlist
        """
        credentials = self.getCredentials(user)
        playlist = user.playlists.get(playlist_id=playlist_id)

        with build('youtube', 'v3', credentials=credentials) as youtube:
            pl_request = youtube.playlists().update(
                part="id,snippet,status",
                body={
                    "id": playlist_id,
                    "snippet": {
                        "title": details["title"],
                        "description": details["description"],
                    },
                    "status": {
                        "privacyStatus": "private" if details["privacyStatus"] else "public"
                    }
                },
            )

            print(details["description"])
            try:
                pl_response = pl_request.execute()
            except googleapiclient.errors.HttpError as e:  # failed to update playlist details
                # possible causes:
                # playlistItemsNotAccessible (403)
                # playlistItemNotFound (404)
                # playlistOperationUnsupported (400)
                # errors i ran into:
                # runs into HttpError 400 "Invalid playlist snippet." when the description contains <, >
                print("ERROR UPDATING PLAYLIST DETAILS", e, e.status_code, e.error_details)
                return -1

            print(pl_response)
            playlist.name = pl_response['snippet']['title']
            playlist.description = pl_response['snippet']['description']
            playlist.is_private_on_yt = True if pl_response['status']['privacyStatus'] == "private" else False
            playlist.save(update_fields=['name', 'description', 'is_private_on_yt'])

            return 0


class Tag(models.Model):
    name = models.CharField(max_length=69)
    created_by = models.ForeignKey(User, related_name="playlist_tags", on_delete=models.CASCADE)

    times_viewed = models.IntegerField(default=0)
    # type = models.CharField(max_length=10)  # either 'playlist' or 'video'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Channel(models.Model):
    channel_id = models.CharField(max_length=420, default="")
    name = models.CharField(max_length=420, default="")
    description = models.CharField(max_length=420, default="No description")
    thumbnail_url = models.CharField(max_length=420, blank=True)
    published_at = models.DateTimeField(blank=True)

    # statistics
    view_count = models.IntegerField(default=0)
    subscriberCount = models.IntegerField(default=0)
    hidden_subscriber_count = models.BooleanField(null=True)
    video_ount = models.IntegerField(default=0)
    is_private = models.BooleanField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Video(models.Model):
    untube_user = models.ForeignKey(User, related_name="videos", on_delete=models.CASCADE, null=True)

    # video details
    video_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100, blank=True)
    duration = models.CharField(max_length=100, blank=True)
    duration_in_seconds = models.IntegerField(default=0)
    thumbnail_url = models.CharField(max_length=420, blank=True)
    published_at = models.DateTimeField(blank=True, null=True)
    description = models.CharField(max_length=420, default="")
    has_cc = models.BooleanField(default=False, blank=True, null=True)

    # video stats
    public_stats_viewable = models.BooleanField(default=True)
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    dislike_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)

    yt_player_HTML = models.CharField(max_length=420, blank=True)

    # video is made by this channel
    # channel = models.ForeignKey(Channel, related_name="videos", on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=420, blank=True)
    channel_name = models.CharField(max_length=420, blank=True)

    # which playlist this video belongs to, and position of that video in the playlist (i.e ALL videos belong to some pl)
    # playlist = models.ForeignKey(Playlist, related_name="videos", on_delete=models.CASCADE)

    # (moved to playlistItem)
    # is_duplicate = models.BooleanField(default=False)  # True if the same video exists more than once in the playlist
    # video_position = models.IntegerField(blank=True)

    # NOTE: For a video in db:
    # 1.) if both is_unavailable_on_yt and was_deleted_on_yt are true,
    # that means the video was originally fine, but then went unavailable when updatePlaylist happened
    # 2.) if only is_unavailable_on_yt is true and was_deleted_on_yt is false,
    # then that means the video was an unavaiable video when initPlaylist was happening
    # 3.) if both is_unavailable_on_yt and was_deleted_on_yt are false, the video is fine, ie up on Youtube
    is_unavailable_on_yt = models.BooleanField(
        default=False)  # True if the video was unavailable (private/deleted) when the API call was first made
    was_deleted_on_yt = models.BooleanField(default=False)  # True if video became unavailable on a subsequent API call

    is_pinned = models.BooleanField(default=False)
    is_marked_as_watched = models.BooleanField(default=False)  # mark video as watched
    is_favorite = models.BooleanField(default=False, blank=True)  # mark video as favorite
    num_of_accesses = models.CharField(max_length=69,
                                       default="0")  # tracks num of times this video was clicked on by user
    user_label = models.CharField(max_length=100, default="")  # custom user given name for this video
    user_notes = models.CharField(max_length=420, default="")  # user can take notes on the video and save them

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # for new videos added/modified/deleted in the playlist
    video_details_modified = models.BooleanField(
        default=False)  # is true for videos whose details changed after playlist update
    video_details_modified_at = models.DateTimeField(auto_now_add=True)  # to set the above false after a day


class Playlist(models.Model):
    tags = models.ManyToManyField(Tag, related_name="playlists")
    untube_user = models.ForeignKey(User, related_name="playlists", on_delete=models.CASCADE, null=True)

    # playlist is made by this channel
    channel_id = models.CharField(max_length=420, blank=True)
    channel_name = models.CharField(max_length=420, blank=True)

    # playlist details
    is_yt_mix = models.BooleanField(default=False)
    playlist_id = models.CharField(max_length=150)
    name = models.CharField(max_length=150, blank=True)  # YT PLAYLIST NAMES CAN ONLY HAVE MAX OF 150 CHARS
    thumbnail_url = models.CharField(max_length=420, blank=True)
    description = models.CharField(max_length=420, default="No description")
    video_count = models.IntegerField(default=0)
    published_at = models.DateTimeField(blank=True)
    is_private_on_yt = models.BooleanField(default=False)
    videos = models.ManyToManyField(Video, related_name="playlists")

    # eg. "<iframe width=\"640\" height=\"360\" src=\"http://www.youtube.com/embed/videoseries?list=PLFuZstFnF1jFwMDffUhV81h0xeff0TXzm\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>"
    playlist_yt_player_HTML = models.CharField(max_length=420, blank=True)

    playlist_duration = models.CharField(max_length=69, blank=True)  # string version of playlist dureation
    playlist_duration_in_seconds = models.IntegerField(default=0)
    has_unavailable_videos = models.BooleanField(default=False)  # if videos in playlist are private/deleted
    has_duplicate_videos = models.BooleanField(default=False)  # duplicate videos will not be shown on site

    # watch playlist details
    # watch_time_left = models.CharField(max_length=150, default="")
    started_on = models.DateTimeField(auto_now_add=True, null=True)
    last_watched = models.DateTimeField(auto_now_add=True, null=True)

    # manage playlist
    is_pinned = models.BooleanField(default=False)
    user_notes = models.CharField(max_length=420, default="")  # user can take notes on the playlist and save them
    user_label = models.CharField(max_length=100, default="")  # custom user given name for this playlist
    marked_as = models.CharField(default="none",
                                 max_length=100)  # can be set to "none", "watching", "on-hold", "plan-to-watch"
    is_favorite = models.BooleanField(default=False, blank=True)  # to mark playlist as fav
    num_of_accesses = models.IntegerField(default="0")  # tracks num of times this playlist was opened by user
    last_accessed_on = models.DateTimeField(default=datetime.datetime.now)
    is_user_owned = models.BooleanField(default=True)  # represents YouTube playlist owned by user

    # set playlist manager
    objects = PlaylistManager()

    # playlist settings
    hide_unavailable_videos = models.BooleanField(default=False)
    confirm_before_deleting = models.BooleanField(default=True)

    # for import
    is_in_db = models.BooleanField(default=False)  # is true when all the videos of a playlist have been imported
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # for updates
    last_full_scan_at = models.DateTimeField(auto_now_add=True)
    has_playlist_changed = models.BooleanField(default=False)  # determines whether playlist was modified online or not
    has_new_updates = models.BooleanField(default=False)  # meant to keep track of newly added/unavailable videos

    def __str__(self):
        return str(self.playlist_id)

    def get_channels_list(self):
        channels_list = []
        num_channels = 0
        for video in self.videos.all():
            channel = video.channel_name
            if channel not in channels_list:
                channels_list.append(channel)
                num_channels += 1

        return [num_channels, channels_list]

    def generate_playlist_thumbnail_url(self):
        pl_name = self.name
        response = requests.get(
            f'https://api.unsplash.com/search/photos/?client_id={SECRETS["UNSPLASH_API_ACCESS_KEY"]}&page=1&query={pl_name}')
        image = response.json()["results"][0]["urls"]["small"]

        print(image)

        return image

    def get_unavailable_videos_count(self):
        return self.video_count - self.get_watchable_videos_count()

    # return count of watchable videos, i.e # videos that are not private or deleted in the playlist
    def get_watchable_videos_count(self):
        return self.playlist_items.filter(Q(is_duplicate=False) & Q(video__is_unavailable_on_yt=False) & Q(video__was_deleted_on_yt=False)).count()

    def get_watched_videos_count(self):
        return self.playlist_items.filter(Q(is_duplicate=False) &
            Q(video__is_marked_as_watched=True) & Q(video__is_unavailable_on_yt=False) & Q(video__was_deleted_on_yt=False)).count()

    # diff of time from when playlist was first marked as watched and playlist reached 100% completion
    def get_finish_time(self):
        return self.last_watched - self.started_on

    def get_watch_time_left(self):
        unwatched_playlist_items_secs = self.playlist_items.filter(Q(is_duplicate=False) &
            Q(video__is_marked_as_watched=False) &
          Q(video__is_unavailable_on_yt=False) &
          Q(video__was_deleted_on_yt=False)).aggregate(Sum('video__duration_in_seconds'))['video__duration_in_seconds__sum']

        watch_time_left = getHumanizedTimeString(unwatched_playlist_items_secs) if unwatched_playlist_items_secs is not None else getHumanizedTimeString(0)

        return watch_time_left

    # return 0 if playlist empty or all videos in playlist are unavailable
    def get_percent_complete(self):
        total_playlist_video_count = self.get_watchable_videos_count()
        watched_videos = self.playlist_items.filter(Q(is_duplicate=False) &
            Q(video__is_marked_as_watched=True) & Q(video__is_unavailable_on_yt=False) & Q(video__was_deleted_on_yt=False))
        num_videos_watched = watched_videos.count()
        percent_complete = round((num_videos_watched / total_playlist_video_count) * 100,
                                 1) if total_playlist_video_count != 0 else 0
        return percent_complete

    def all_videos_unavailable(self):
        all_vids_unavailable = False
        if self.videos.filter(
                Q(is_unavailable_on_yt=True) | Q(was_deleted_on_yt=True)).count() == self.video_count:
            all_vids_unavailable = True
        return all_vids_unavailable


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, related_name="playlist_items",
                                 on_delete=models.CASCADE)  # playlist this pl item belongs to
    video = models.ForeignKey(Video, on_delete=models.CASCADE)

    # details
    playlist_item_id = models.CharField(max_length=100)  # the item id of the playlist this video beo
    video_position = models.IntegerField(blank=True)  # video position in the playlist
    published_at = models.DateTimeField(
        default=datetime.datetime.now)  # snippet.publishedAt - The date and time that the item was added to the playlist
    channel_id = models.CharField(null=True,
                                  max_length=250)  # snippet.channelId - The ID that YouTube uses to uniquely identify the user that added the item to the playlist.
    channel_name = models.CharField(null=True,
                                    max_length=250)  # snippet.channelTitle -  The channel title of the channel that the playlist item belongs to.

    # video_owner_channel_id = models.CharField(max_length=100)
    # video_owner_channel_title = models.CharField(max_length=100)
    is_duplicate = models.BooleanField(default=False)  # True if the same video exists more than once in the playlist
    is_marked_as_watched = models.BooleanField(default=False, blank=True)  # mark video as watched
    num_of_accesses = models.IntegerField(default=0)  # tracks num of times this video was clicked on by user

    # for new videos added/modified/deleted in the playlist
    # video_details_modified = models.BooleanField(
    #    default=False)  # is true for videos whose details changed after playlist update
    # video_details_modified_at = models.DateTimeField(auto_now_add=True)  # to set the above false after a day
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Pin(models.Model):
    type = models.CharField(max_length=100)  # "playlist", "video"
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
