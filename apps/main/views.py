import datetime
import random

import bleach
import pytz
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.html import strip_tags

import apps
from apps.main.models import Playlist, Tag
from django.contrib.auth.decorators import login_required  # redirects user to settings.LOGIN_URL
from allauth.socialaccount.models import SocialToken
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.template import loader
from .util import *


# Create your views here.
@login_required
def home(request):
    user_profile = request.user
    watching = user_profile.playlists.filter(Q(marked_as="watching") & Q(is_in_db=True)).order_by("-num_of_accesses")
    recently_accessed_playlists = user_profile.playlists.filter(is_in_db=True).filter(
        updated_at__gt=user_profile.profile.updated_at).order_by("-updated_at")[:6]
    recently_added_playlists = user_profile.playlists.filter(is_in_db=True).order_by("-created_at")[:6]

    #### FOR NEWLY JOINED USERS ######
    channel_found = True
    if user_profile.profile.show_import_page:
        """
        Logic:
        show_import_page is True by default. When a user logs in for the first time (infact anytime), google 
        redirects them to 'home' url. Since, show_import_page is True by default, the user is then redirected
        from 'home' to 'import_in_progress' url
        
        show_import_page is only set false in the import_in_progress.html page, i.e when user cancels YT import
        """
        # user_profile.show_import_page = False

        if user_profile.profile.access_token.strip() == "" or user_profile.profile.refresh_token.strip() == "":
            user_social_token = SocialToken.objects.get(account__user=request.user)
            user_profile.profile.access_token = user_social_token.token
            user_profile.profile.refresh_token = user_social_token.token_secret
            user_profile.profile.expires_at = user_social_token.expires_at
            user_profile.save()
            Playlist.objects.getUserYTChannelID(user_profile)

        if user_profile.profile.imported_yt_playlists:
            user_profile.profile.show_import_page = False  # after user imports all their YT playlists no need to show_import_page again
            user_profile.profile.save(update_fields=['show_import_page'])
            return render(request, "home.html", {"import_successful": True})

        return render(request, "import_in_progress.html")

        # if Playlist.objects.getUserYTChannelID(request.user) == -1:  # user channel not found
        #    channel_found = False
        # else:
        #   Playlist.objects.initPlaylist(request.user, None)  # get all playlists from user's YT channel
        #  return render(request, "home.html", {"import_successful": True})
    ##################################

    user_playlists = request.user.playlists.filter(is_in_db=True)
    total_num_playlists = user_playlists.count()
    user_playlists = user_playlists.filter(num_of_accesses__gt=0).order_by(
        "-num_of_accesses")

    statistics = {
        "public_x": 0,
        "private_x": 0,
        "favorites_x": 0,
        "watching_x": 0,
        "imported_x": 0
    }

    if total_num_playlists != 0:
        # x means  percentage
        statistics["public_x"] = round(user_playlists.filter(is_private_on_yt=False).count() / total_num_playlists,
                                       1) * 100
        statistics["private_x"] = round(user_playlists.filter(is_private_on_yt=True).count() / total_num_playlists,
                                        1) * 100
        statistics["favorites_x"] = round(user_playlists.filter(is_favorite=True).count() / total_num_playlists,
                                          1) * 100
        statistics["watching_x"] = round(user_playlists.filter(marked_as="watching").count() / total_num_playlists,
                                         1) * 100
        statistics["imported_x"] = round(user_playlists.filter(is_user_owned=False).count() / total_num_playlists,
                                         1) * 100

    return render(request, 'home.html', {"channel_found": channel_found,
                                         "user_playlists": user_playlists,
                                         "watching": watching,
                                         "recently_accessed_playlists": recently_accessed_playlists,
                                         "recently_added_playlists": recently_added_playlists,
                                         "statistics": statistics})


@login_required
def view_video(request, video_id):
    if request.user.videos.filter(video_id=video_id).exists():
        video = request.user.videos.get(video_id=video_id)

        if video.is_unavailable_on_yt or video.was_deleted_on_yt:
            messages.error(request, "Video went private/deleted on YouTube!")
            return redirect('home')

        video.num_of_accesses += 1
        video.save(update_fields=['num_of_accesses'])

        return render(request, 'view_video.html', {"video": video})
    else:
        messages.error(request, "No such video in your UnTube collection!")
        return redirect('home')


@login_required
@require_POST
def video_notes(request, video_id):
    print(request.POST)
    if request.user.videos.filter(video_id=video_id).exists():
        video = request.user.videos.get(video_id=video_id)

        if 'video-notes-text-area' in request.POST:
            video.user_notes = bleach.clean(request.POST['video-notes-text-area'], tags=['br'])
            video.save(update_fields=['user_notes', 'user_label'])
            # messages.success(request, 'Saved!')

        return HttpResponse("""
            <div hx-ext="class-tools">
                <div classes="add visually-hidden:2s">Saved!</div>
            </div>
        """)
    else:
        return HttpResponse('No such video in your UnTube collection!')


@login_required
def view_playlist(request, playlist_id):
    user_profile = request.user
    user_owned_playlists = user_profile.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))

    # specific playlist requested
    if user_profile.playlists.filter(Q(playlist_id=playlist_id) & Q(is_in_db=True)).exists():
        playlist = user_profile.playlists.get(playlist_id__exact=playlist_id)
        # playlist.num_of_accesses += 1
        # only note down that the playlist as been viewed when 5mins has passed since the last access
        if playlist.last_accessed_on + datetime.timedelta(minutes=5) < datetime.datetime.now(pytz.utc):
            playlist.num_of_accesses += 1
            playlist.last_accessed_on = datetime.datetime.now(pytz.utc)
        playlist.save()
    else:
        if playlist_id == "LL":  # liked videos playlist hasnt been imported yet
            return render(request, 'view_playlist.html', {"not_imported_LL": True})
        messages.error(request, "No such playlist found!")
        return redirect('home')

    if playlist.has_new_updates:
        recently_updated_videos = playlist.videos.filter(video_details_modified=True)

        for video in recently_updated_videos:
            if video.video_details_modified_at + datetime.timedelta(hours=12) < datetime.datetime.now(
                    pytz.utc):  # expired
                video.video_details_modified = False
                video.save()

        if not recently_updated_videos.exists():
            playlist.has_new_updates = False
            playlist.save()

    playlist_items = playlist.playlist_items.select_related('video').order_by("video_position")

    user_created_tags = Tag.objects.filter(created_by=request.user)
    playlist_tags = playlist.tags.all()

    for tag in playlist_tags:
        tag.times_viewed += 1
        tag.save(update_fields=['times_viewed'])

    unused_tags = user_created_tags.difference(playlist_tags)

    return render(request, 'view_playlist.html', {"playlist": playlist,
                                                  "playlist_tags": playlist_tags,
                                                  "unused_tags": unused_tags,
                                                  "playlist_items": playlist_items,
                                                  "user_owned_playlists": user_owned_playlists,
                                                  "watching_message": generateWatchingMessage(playlist),
                                                  })


@login_required
def tagged_playlists(request, tag):
    tag = get_object_or_404(Tag, created_by=request.user, name=tag)
    playlists = tag.playlists.all()

    return render(request, 'all_playlists_with_tag.html', {"playlists": playlists, "tag": tag})


@login_required
def all_playlists(request, playlist_type):
    """
    Possible playlist types for marked_as attribute: (saved in database like this)
    "none", "watching", "plan-to-watch"
    """
    playlist_type = playlist_type.lower()
    watching = False
    if playlist_type == "" or playlist_type == "all":
        playlists = request.user.playlists.all().filter(is_in_db=True)
        playlist_type_display = "All Playlists"
    elif playlist_type == "user-owned":  # YT playlists owned by user
        playlists = request.user.playlists.all().filter(Q(is_user_owned=True) & Q(is_in_db=True))
        playlist_type_display = "Your YouTube Playlists"
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_user_owned=False) & Q(is_in_db=True))
        playlist_type_display = "Imported playlists"
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        playlist_type_display = "Favorites"
    elif playlist_type.lower() in ["watching", "plan-to-watch"]:
        playlists = request.user.playlists.filter(Q(marked_as=playlist_type.lower()) & Q(is_in_db=True))
        playlist_type_display = playlist_type.lower().replace("-", " ")
        if playlist_type.lower() == "watching":
            watching = True
    elif playlist_type.lower() == "home":  # displays cards of all playlist types
        return render(request, 'playlists_home.html')
    elif playlist_type.lower() == "random":  # randomize playlist
        if request.method == "POST":
            playlists_type = request.POST["playlistsType"]
            if playlists_type == "All":
                playlists = request.user.playlists.all().filter(is_in_db=True)
            elif playlists_type == "Favorites":
                playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
            elif playlists_type == "Watching":
                playlists = request.user.playlists.filter(Q(marked_as="watching") & Q(is_in_db=True))
            elif playlists_type == "Plan to Watch":
                playlists = request.user.playlists.filter(Q(marked_as="plan-to-watch") & Q(is_in_db=True))
            else:
                return redirect('/playlists/home')

            if not playlists.exists():
                messages.info(request, f"No playlists in {playlists_type}")
                return redirect('/playlists/home')
            random_playlist = random.choice(playlists)
            return redirect(f'/playlist/{random_playlist.playlist_id}')
        return render(request, 'playlists_home.html')
    else:
        return redirect('home')

    return render(request, 'all_playlists.html', {"playlists": playlists,
                                                  "playlist_type": playlist_type,
                                                  "playlist_type_display": playlist_type_display,
                                                  "watching": watching})


@login_required
def all_videos(request, videos_type):
    """
    To implement this need to redesign the database
    Currently videos -> playlist -> user.profile

    Need to do
    user.profile <- videos <- playlistItem -> playlist
    many ways actually
    """
    videos_type = videos_type.lower()

    if videos_type == "" or videos_type == "all":
        playlists = request.user.playlists.all().filter(is_in_db=True)
        videos_type_display = "All Videos"
    elif videos_type == "user-owned":  # YT playlists owned by user
        playlists = request.user.playlists.all().filter(Q(is_user_owned=True) & Q(is_in_db=True))
        videos_type_display = "All Videos in your YouTube Playlists"
    elif videos_type == "imported":  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_user_owned=False) & Q(is_in_db=True))
        videos_type_display = "Imported YouTube Playlists Videos"
    elif videos_type == "favorites":  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        videos_type_display = "Favorite Videos"
    elif videos_type == "watched":  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        videos_type_display = "Watched Videos"
    elif videos_type == 'hidden-videos':  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        videos_type_display = "Hidden Videos"
    elif videos_type.lower() == "home":  # displays cards of all playlist types
        return render(request, 'videos_home.html')
    else:
        return redirect('home')

    return render(request, 'all_playlists.html', {"playlists": playlists,
                                                  "videos_type": videos_type,
                                                  "videos_type_display": videos_type_display})


@login_required
def order_playlist_by(request, playlist_id, order_by):
    playlist = request.user.playlists.get(Q(playlist_id=playlist_id) & Q(is_in_db=True))

    display_text = "Nothing in this playlist! Add something!"  # what to display when requested order/filter has no videws
    videos_details = ""

    if order_by == "all":
        playlist_items = playlist.playlist_items.select_related('video').order_by("video_position")
    elif order_by == "favorites":
        playlist_items = playlist.playlist_items.select_related('video').filter(video__is_favorite=True).order_by(
            "video_position")
        videos_details = "Sorted by Favorites"
        display_text = "No favorites yet!"
    elif order_by == "popularity":
        videos_details = "Sorted by Popularity"
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__like_count")
    elif order_by == "date-published":
        videos_details = "Sorted by Date Published"
        playlist_items = playlist.playlist_items.select_related('video').order_by("-published_at")
    elif order_by == "views":
        videos_details = "Sorted by View Count"
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__view_count")
    elif order_by == "has-cc":
        videos_details = "Filtered by Has CC"
        playlist_items = playlist.playlist_items.select_related('video').filter(video__has_cc=True).order_by(
            "video_position")
        display_text = "No videos in this playlist have CC :("
    elif order_by == "duration":
        videos_details = "Sorted by Video Duration"
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__duration_in_seconds")
    elif order_by == 'new-updates':
        playlist_items = []
        videos_details = "Sorted by New Updates"
        display_text = "No new updates! Note that deleted videos will not show up here."
        if playlist.has_new_updates:
            recently_updated_videos = playlist.playlist_items.select_related('video').filter(
                video__video_details_modified=True)

            for playlist_item in recently_updated_videos:
                if playlist_item.video.video_details_modified_at + datetime.timedelta(hours=12) < datetime.datetime.now(
                        pytz.utc):  # expired
                    playlist_item.video.video_details_modified = False
                    playlist_item.video.save(update_fields=['video_details_modified'])

            if not recently_updated_videos.exists():
                playlist.has_new_updates = False
                playlist.save(update_fields=['has_new_updates'])
            else:
                playlist_items = recently_updated_videos.order_by("video_position")
    elif order_by == 'unavailable-videos':
        playlist_items = playlist.playlist_items.select_related('video').filter(
            Q(video__is_unavailable_on_yt=True) & Q(video__was_deleted_on_yt=True))
        videos_details = "Sorted by Unavailable Videos"
        display_text = "None of the videos in this playlist have gone unavailable... yet."
    elif order_by == 'channel':
        channel_name = request.GET["channel-name"]
        playlist_items = playlist.playlist_items.select_related('video').filter(
            video__channel_name=channel_name).order_by("video_position")
        videos_details = f"Sorted by Channel '{channel_name}'"
    else:
        return HttpResponse("Something went wrong :(")

    return HttpResponse(loader.get_template("intercooler/videos.html").render({"playlist": playlist,
                                                                               "playlist_items": playlist_items,
                                                                               "videos_details": videos_details,
                                                                               "display_text": display_text,
                                                                               "order_by": order_by}))


@login_required
def order_playlists_by(request, playlist_type, order_by):
    print("GET", request.GET)
    print("POST", request.POST)
    print("CONTENT PARAMS", request.content_params)
    print("HEAD", request.headers)
    print("BODY", request.body)

    watching = False

    if playlist_type == "" or playlist_type.lower() == "all":
        playlists = request.user.playlists.all()
    elif playlist_type.lower() == "favorites":
        playlists = request.user.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
    elif playlist_type.lower() in ["watching", "plan-to-watch"]:
        playlists = request.user.playlists.filter(Q(marked_as=playlist_type.lower()) & Q(is_in_db=True))
        if playlist_type.lower() == "watching":
            watching = True
    elif playlist_type.lower() == "imported":
        playlists = request.user.playlists.filter(Q(is_user_owned=False) & Q(is_in_db=True))
    elif playlist_type.lower() == "user-owned":
        playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    else:
        return HttpResponse("Not found.")

    if order_by == 'recently-accessed':
        playlists = playlists.order_by("-updated_at")
    elif order_by == 'playlist-duration-in-seconds':
        playlists = playlists.order_by("-playlist_duration_in_seconds")
    elif order_by == 'video-count':
        playlists = playlists.order_by("-video_count")

    return HttpResponse(loader.get_template("intercooler/playlists.html")
                        .render({"playlists": playlists, "watching": watching}))


@login_required
def mark_playlist_as(request, playlist_id, mark_as):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    marked_as_response = '<span></span><meta http-equiv="refresh" content="0" />'

    if mark_as in ["watching", "on-hold", "plan-to-watch"]:
        playlist.marked_as = mark_as
        playlist.save()
        icon = ""
        if mark_as == "watching":
            playlist.last_watched = datetime.datetime.now(pytz.utc)
            playlist.save(update_fields=['last_watched'])
            icon = '<i class="fas fa-fire-alt me-2"></i>'
        elif mark_as == "plan-to-watch":
            icon = '<i class="fas fa-flag me-2"></i>'
        marked_as_response = f'<span class="badge bg-success text-white" >{icon}{mark_as}</span> <meta http-equiv="refresh" content="0" />'
    elif mark_as == "none":
        playlist.marked_as = mark_as
        playlist.save()
    elif mark_as == "favorite":
        if playlist.is_favorite:
            playlist.is_favorite = False
            playlist.save()
            return HttpResponse('<i class="far fa-star"></i>')
        else:
            playlist.is_favorite = True
            playlist.save()
            return HttpResponse('<i class="fas fa-star"></i>')
    else:
        return redirect('home')

    return HttpResponse(marked_as_response)


@login_required
def playlists_home(request):
    return render(request, 'playlists_home.html')


@login_required
@require_POST
def delete_videos(request, playlist_id, command):
    all = False
    num_vids = 0
    playlist_item_ids = []
    print(request.POST)
    if "all" in request.POST:
        if request.POST["all"] == "yes":
            all = True
            num_vids = request.user.playlists.get(playlist_id=playlist_id).playlist_items.all().count()
            if command == "start":
                playlist_item_ids = [playlist_item.playlist_item_id for playlist_item in request.user.playlists.get(playlist_id=playlist_id).playlist_items.all()]
    else:
        playlist_item_ids = request.POST.getlist("video-id", default=[])
        num_vids = len(playlist_item_ids)

    extra_text = " "
    if num_vids == 0:
        return HttpResponse("""
        <div hx-ext="class-tools">
            <div classes="add visually-hidden:3s">
                <h5>Select some videos first!</h5><hr>
            </div>
        </div>
        """)

    if 'confirm before deleting' in request.POST:
        if request.POST['confirm before deleting'] == 'False':
            command = "confirmed"

    if command == "confirm":
        if all or num_vids == request.user.playlists.get(playlist_id=playlist_id).playlist_items.all().count():
            hx_vals = """hx-vals='{"all": "yes"}'"""
            delete_text = "ALL VIDEOS"
            extra_text = " This will not delete the playlist itself, will only make the playlist empty. "
        else:
            hx_vals = ""
            delete_text = f"{num_vids} videos"

        if playlist_id == "LL":
            extra_text += "Since you're deleting from your Liked Videos playlist, the selected videos will also be unliked from YouTube. "

        url = f"/playlist/{playlist_id}/delete-videos/confirmed"

        return HttpResponse(
            f"""
                <div hx-ext="class-tools">
                <div classes="add visually-hidden:30s">
                    <h5>
                    Are you sure you want to delete {delete_text} from your YouTube playlist?{extra_text}This cannot be undone.</h5>
                    <button hx-post="{url}" hx-include="[id='video-checkboxes']" {hx_vals} hx-target="#delete-videos-confirm-box" type="button" class="btn btn-outline-danger btn-sm">Confirm</button>
                    <hr>
                </div>
                </div>
            """)
    elif command == "confirmed":
        if all:
            hx_vals = """hx-vals='{"all": "yes"}'"""
        else:
            hx_vals = ""
        url = f"/playlist/{playlist_id}/delete-videos/start"
        return HttpResponse(
            f"""
            <div class="spinner-border text-light" role="status" hx-post="{url}" {hx_vals} hx-trigger="load" hx-include="[id='video-checkboxes']" hx-target="#delete-videos-confirm-box"></div><hr>
            """)
    elif command == "start":
        print("Deleting", len(playlist_item_ids), "videos")
        Playlist.objects.deletePlaylistItems(request.user, playlist_id, playlist_item_ids)
        if all:
            help_text = "Finished emptying this playlist."
        else:
            help_text = "Done deleting selected videos from your playlist on YouTube."

        return HttpResponse(f"""
        <h5 hx-get="/playlist/{playlist_id}/update/checkforupdates" hx-trigger="load delay:2s" hx-target="#checkforupdates">
            {help_text} Refresh page!
        </h5>
        <hr>
        """)


@login_required
@require_POST
def delete_specific_videos(request, playlist_id, command):
    Playlist.objects.deleteSpecificPlaylistItems(request.user, playlist_id, command)

    help_text = "Error."
    if command == "unavailable":
        help_text = "Deleted all unavailable videos."
    elif command == "duplicate":
        help_text = "Deleted all duplicate videos."

    return HttpResponse(f"""
        <h5>
            {help_text} Refresh page!
        </h5>
        <hr>
        """)

@login_required
@require_POST
def search_tagged_playlists(request, tag):
    tag = get_object_or_404(Tag, created_by=request.user, name=tag)
    playlists = tag.playlists.all()

    return HttpResponse("yay")


@login_required
@require_POST
def search_playlists(request, playlist_type):
    # print(request.POST)  # prints <QueryDict: {'search': ['aa']}>

    search_query = request.POST["search"]
    watching = False

    playlists = None
    if playlist_type == "all":
        try:
            playlists = request.user.playlists.all().filter(Q(name__startswith=search_query) & Q(is_in_db=True))
        except:
            playlists = request.user.playlists.all()
    elif playlist_type == "user-owned":  # YT playlists owned by user
        try:
            playlists = request.user.playlists.filter(
                Q(name__startswith=search_query) & Q(is_user_owned=True) & Q(is_in_db=True))
        except:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        try:
            playlists = request.user.playlists.filter(
                Q(name__startswith=search_query) & Q(is_user_owned=False) & Q(is_in_db=True))
        except:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        try:
            playlists = request.user.playlists.filter(
                Q(name__startswith=search_query) & Q(is_favorite=True) & Q(is_in_db=True))
        except:
            playlists = request.user.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
    elif playlist_type in ["watching", "plan-to-watch"]:
        try:
            playlists = request.user.playlists.filter(
                Q(name__startswith=search_query) & Q(marked_as=playlist_type) & Q(is_in_db=True))
        except:
            playlists = request.user.playlists.all().filter(Q(marked_as=playlist_type) & Q(is_in_db=True))
        if playlist_type == "watching":
            watching = True

    return HttpResponse(loader.get_template("intercooler/playlists.html")
                        .render({"playlists": playlists,
                                 "watching": watching}))


#### MANAGE VIDEOS #####
@login_required
def mark_video_favortie(request, playlist_id, video_id):
    video = request.user.videos.get(video_id=video_id)

    if video.is_favorite:
        video.is_favorite = False
        video.save(update_fields=['is_favorite'])
        return HttpResponse('<i class="far fa-heart"></i>')
    else:
        video.is_favorite = True
        video.save(update_fields=['is_favorite'])
        return HttpResponse('<i class="fas fa-heart" style="color: #fafa06"></i>')


@login_required
def mark_video_watched(request, playlist_id, video_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    video = playlist.videos.get(video_id=video_id)

    if video.is_marked_as_watched:
        video.is_marked_as_watched = False
        video.save(update_fields=['is_marked_as_watched'])

        return HttpResponse(
            f'<i class="far fa-check-circle" hx-get="/playlist/{playlist_id}/get-watch-message" hx-trigger="load" hx-target="#playlist-watch-message"></i>')
    else:
        video.is_marked_as_watched = True
        video.save(update_fields=['is_marked_as_watched'])
        playlist.last_watched = datetime.datetime.now(pytz.utc)
        playlist.save(update_fields=['last_watched'])

        return HttpResponse(
            f'<i class="fas fa-check-circle" hx-get="/playlist/{playlist_id}/get-watch-message" hx-trigger="load" hx-target="#playlist-watch-message"></i>')


###########
@login_required
def search(request):
    if request.method == "GET":
        return render(request, 'search_untube_page.html', {"playlists": request.user.playlists.all()})
    else:
        return redirect('home')


@login_required
@require_POST
def search_UnTube(request):
    print(request.POST)

    search_query = request.POST["search"]

    all_playlists = request.user.playlists.filter(is_in_db=True)
    if 'playlist-tags' in request.POST:
        tags = request.POST.getlist('playlist-tags')
        for tag in tags:
            all_playlists = all_playlists.filter(tags__name=tag)
        # all_playlists = all_playlists.filter(tags__name__in=tags)

    playlist_items = []

    if request.POST['search-settings'] == 'starts-with':
        playlists = all_playlists.filter(Q(name__istartswith=search_query) | Q(
            user_label__istartswith=search_query)) if search_query != "" else all_playlists.none()

        if search_query != "":
            for playlist in all_playlists:
                pl_items = playlist.playlist_items.select_related('video').filter(
                    Q(video__name__istartswith=search_query) | Q(video__user_label__istartswith=search_query) & Q(
                        is_duplicate=False))

                if pl_items.exists():
                    for v in pl_items.all():
                        playlist_items.append(v)

    else:
        playlists = all_playlists.filter(Q(name__icontains=search_query) | Q(
            user_label__istartswith=search_query)) if search_query != "" else all_playlists.none()

        if search_query != "":
            for playlist in all_playlists:
                pl_items = playlist.playlist_items.select_related('video').filter(
                    Q(video__name__icontains=search_query) | Q(video__user_label__istartswith=search_query) & Q(
                        is_duplicate=False))

                if pl_items.exists():
                    for v in pl_items.all():
                        playlist_items.append(v)

    return HttpResponse(loader.get_template("intercooler/search_untube_results.html")
                        .render({"playlists": playlists,
                                 "playlist_items": playlist_items,
                                 "videos_count": len(playlist_items),
                                 "search_query": True if search_query != "" else False,
                                 "all_playlists": all_playlists}))


@login_required
def manage_playlists(request):
    return render(request, "manage_playlists.html")


@login_required
def manage_view_page(request, page):
    if page == "import":
        return render(request, "manage_playlists_import.html",
                      {"manage_playlists_import_textarea": request.user.profile.manage_playlists_import_textarea})
    elif page == "create":
        return render(request, "manage_playlists_create.html")
    else:
        return HttpResponse('Working on this!')


@login_required
@require_POST
def manage_save(request, what):
    if what == "manage_playlists_import_textarea":
        request.user.profile.manage_playlists_import_textarea = request.POST["import-playlist-textarea"]
        request.user.save()

    return HttpResponse("")


@login_required
@require_POST
def manage_import_playlists(request):
    playlist_links = request.POST["import-playlist-textarea"].replace(",", "").split("\n")

    num_playlists_already_in_db = 0
    num_playlists_initialized_in_db = 0
    num_playlists_not_found = 0
    new_playlists = []
    old_playlists = []
    not_found_playlists = []

    done = []
    for playlist_link in playlist_links:
        if playlist_link.strip() != "" and playlist_link.strip() not in done:
            pl_id = Playlist.objects.getPlaylistId(playlist_link.strip())
            if pl_id is None:
                num_playlists_not_found += 1
                continue

            status = Playlist.objects.initializePlaylist(request.user, pl_id)["status"]
            if status == -1 or status == -2:
                print("\nNo such playlist found:", pl_id)
                num_playlists_not_found += 1
                not_found_playlists.append(playlist_link)
            elif status == -3:  # playlist already in db
                num_playlists_already_in_db += 1
                playlist = request.user.playlists.get(playlist_id__exact=pl_id)
                old_playlists.append(playlist)
            else:  # only if playlist exists on YT, so import its videos
                print(status)
                Playlist.objects.getAllVideosForPlaylist(request.user, pl_id)
                playlist = request.user.playlists.get(playlist_id__exact=pl_id)
                new_playlists.append(playlist)
                num_playlists_initialized_in_db += 1
            done.append(playlist_link.strip())

    request.user.profile.manage_playlists_import_textarea = ""
    request.user.save()

    return HttpResponse(loader.get_template("intercooler/manage_playlists_import_results.html")
        .render(
        {"new_playlists": new_playlists,
         "old_playlists": old_playlists,
         "not_found_playlists": not_found_playlists,
         "num_playlists_already_in_db": num_playlists_already_in_db,
         "num_playlists_initialized_in_db": num_playlists_initialized_in_db,
         "num_playlists_not_found": num_playlists_not_found
         }))


@login_required
@require_POST
def manage_create_playlist(request):
    print(request.POST)
    return HttpResponse("")


@login_required
def load_more_videos(request, playlist_id, order_by, page):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_items = None
    if order_by == "all":
        playlist_items = playlist.playlist_items.select_related('video').order_by("video_position")
        print(f"loading page 1: {playlist_items.count()} videos")
    elif order_by == "favorites":
        playlist_items = playlist.playlist_items.select_related('video').filter(video__is_favorite=True).order_by(
            "video_position")
    elif order_by == "popularity":
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__like_count")
    elif order_by == "date-published":
        playlist_items = playlist.playlist_items.select_related('video').order_by("-published_at")
    elif order_by == "views":
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__view_count")
    elif order_by == "has-cc":
        playlist_items = playlist.playlist_items.select_related('video').filter(video__has_cc=True).order_by(
            "video_position")
    elif order_by == "duration":
        playlist_items = playlist.playlist_items.select_related('video').order_by("-video__duration_in_seconds")
    elif order_by == 'new-updates':
        playlist_items = []
        if playlist.has_new_updates:
            recently_updated_videos = playlist.playlist_items.select_related('video').filter(
                video__video_details_modified=True)

            for playlist_item in recently_updated_videos:
                if playlist_item.video.video_details_modified_at + datetime.timedelta(hours=12) < datetime.datetime.now(
                        pytz.utc):  # expired
                    playlist_item.video.video_details_modified = False
                    playlist_item.video.save()

            if not recently_updated_videos.exists():
                playlist.has_new_updates = False
                playlist.save()
            else:
                playlist_items = recently_updated_videos.order_by("video_position")
    elif order_by == 'unavailable-videos':
        playlist_items = playlist.playlist_items.select_related('video').filter(
            Q(video__is_unavailable_on_yt=True) & Q(video__was_deleted_on_yt=True))
    elif order_by == 'channel':
        channel_name = request.GET["channel-name"]
        playlist_items = playlist.playlist_items.select_related('video').filter(
            video__channel_name=channel_name).order_by("video_position")

    return HttpResponse(loader.get_template("intercooler/videos.html")
        .render(
        {
            "playlist": playlist,
            "playlist_items": playlist_items[50 * page:],  # only send 50 results per page
            "page": page + 1,
            "order_by": order_by}))


@login_required
@require_POST
def update_playlist_settings(request, playlist_id):
    message_type = "success"
    message_content = "Saved!"

    print(request.POST)
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    if "user_label" in request.POST:
        playlist.user_label = request.POST["user_label"]
        playlist.save(update_fields=['user_label'])

        return HttpResponse(loader.get_template("intercooler/messages.html")
            .render(
            {"message_type": message_type,
             "message_content": message_content}))

    if 'confirm before deleting' in request.POST:
        playlist.confirm_before_deleting = True
    else:
        playlist.confirm_before_deleting = False

    if 'hide videos' in request.POST:
        playlist.hide_unavailable_videos = True
    else:
        playlist.hide_unavailable_videos = False

    playlist.save(update_fields=['hide_unavailable_videos', 'confirm_before_deleting'])

    valid_title = request.POST['playlistTitle'].replace(">", "greater than").replace("<", "less than")
    valid_description = request.POST['playlistDesc'].replace(">", "greater than").replace("<", "less than")
    details = {
        "title": valid_title,
        "description": valid_description,
        "privacyStatus": True if request.POST['playlistPrivacy'] == "Private" else False
    }

    status = Playlist.objects.updatePlaylistDetails(request.user, playlist_id, details)
    if status == -1:
        message_type = "danger"
        message_content = "Could not save :("

    return HttpResponse(loader.get_template("intercooler/messages.html")
        .render(
        {"message_type": message_type,
         "message_content": message_content}))


@login_required
def update_playlist(request, playlist_id, command):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if command == "checkforupdates":
        print("Checking if playlist changed...")
        result = Playlist.objects.checkIfPlaylistChangedOnYT(request.user, playlist_id)

        if result[0] == 1:  # full scan was done (full scan is done for a playlist if a week has passed)
            deleted_videos, unavailable_videos, added_videos = result[1:]

            print("CHANGES", deleted_videos, unavailable_videos, added_videos)

            # playlist_changed_text = ["The following modifications happened to this playlist on YouTube:"]
            if deleted_videos != 0 or unavailable_videos != 0 or added_videos != 0:
                pass
                # if added_videos > 0:
                #    playlist_changed_text.append(f"{added_videos} new video(s) were added")
                # if deleted_videos > 0:
                #    playlist_changed_text.append(f"{deleted_videos} video(s) were deleted")
                # if unavailable_videos > 0:
                #    playlist_changed_text.append(f"{unavailable_videos} video(s) went private/unavailable")

                # playlist.playlist_changed_text = "\n".join(playlist_changed_text)
                # playlist.has_playlist_changed = True
                # playlist.save()
            else:  # no updates found
                return HttpResponse("""
                <div hx-ext="class-tools">

                    <div id="checkforupdates" class="sticky-top" style="top: 0.5em;">
                    
                        <div class="alert alert-success alert-dismissible fade show" classes="add visually-hidden:1s" role="alert">
                            Playlist upto date!
                        </div>
                    </div>
                </div>
                """)
        elif result[0] == -1:  # playlist changed
            print("!!!Playlist changed")

            # current_playlist_vid_count = playlist.video_count
            # new_playlist_vid_count = result[1]

            # print(current_playlist_vid_count)
            # print(new_playlist_vid_count)

            # playlist.has_playlist_changed = True
            # playlist.save()
            # print(playlist.playlist_changed_text)
        else:  # no updates found
            return HttpResponse("""
            <div id="checkforupdates" class="sticky-top" style="top: 0.5em;">
                <div hx-ext="class-tools">
                <div classes="add visually-hidden:2s" class="alert alert-success alert-dismissible fade show sticky-top visually-hidden" role="alert" style="top: 0.5em;">
                    No new updates!
                </div>
                </div>
            </div>
            """)

        return HttpResponse(f"""
        <div hx-get="/playlist/{playlist_id}/update/auto" hx-trigger="load" hx-target="this" class="sticky-top" style="top: 0.5em;">
            
            <div class="alert alert-success alert-dismissible fade show" role="alert">
            <div class="d-flex justify-content-center" id="loading-sign">
                <img src="/static/svg-loaders/circles.svg" width="40" height="40">
                <h5 class="mt-2 ms-2">Changes detected on YouTube, updating playlist '{playlist.name}'...</h5>
            </div>
            </div>
        </div>
        """)

    if command == "manual":
        print("MANUAL")
        return HttpResponse(
            f"""<div hx-get="/playlist/{playlist_id}/update/auto" hx-trigger="load" hx-swap="outerHTML">
                    <div class="d-flex justify-content-center mt-4 mb-3" id="loading-sign">
                        <img src="/static/svg-loaders/circles.svg" width="40" height="40">
                        <h5 class="mt-2 ms-2">Refreshing playlist '{playlist.name}', please wait!</h5>
                    </div>
                </div>""")

    print("Attempting to update playlist")
    status, deleted_playlist_item_ids, unavailable_videos, added_videos = Playlist.objects.updatePlaylist(request.user,
                                                                                                          playlist_id)

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if status == -1:
        playlist_name = playlist.name
        playlist.delete()
        return HttpResponse(
            f"""
                <div class="d-flex justify-content-center mt-4 mb-3" id="loading-sign">
                    <h5 class="mt-2 ms-2">Looks like the playlist '{playlist_name}' was deleted on YouTube. It has been removed from UnTube as well.</h5>
                </div>
            """)

    print("Updated playlist")
    playlist_changed_text = []

    if len(added_videos) != 0:
        playlist_changed_text.append(f"{len(added_videos)} added")
        for video in added_videos:
            playlist_changed_text.append(f"--> {video.name}")

        # if len(added_videos) > 3:
        #    playlist_changed_text.append(f"+ {len(added_videos) - 3} more")

    if len(unavailable_videos) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f"{len(unavailable_videos)} went unavailable")
        else:
            playlist_changed_text.append(f"\n{len(unavailable_videos)} went unavailable")
        for video in unavailable_videos:
            playlist_changed_text.append(f"--> {video.name}")
    if len(deleted_playlist_item_ids) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f"{len(deleted_playlist_item_ids)} deleted")
        else:
            playlist_changed_text.append(f"\n{len(deleted_playlist_item_ids)} deleted")

        for playlist_item_id in deleted_playlist_item_ids:
            playlist_item = playlist.playlist_items.select_related('video').get(playlist_item_id=playlist_item_id)
            video = playlist_item.video
            playlist_changed_text.append(f"--> {playlist_item.video.name}")
            playlist_item.delete()
            if playlist_id == "LL":
                video.liked = False
                video.save(update_fields=['liked'])
            if not playlist.playlist_items.filter(video__video_id=video.video_id).exists():
                playlist.videos.remove(video)

    if len(playlist_changed_text) == 0:
        playlist_changed_text = ["Successfully refreshed playlist! No new changes found!"]

    # return HttpResponse
    return HttpResponse(loader.get_template("intercooler/playlist_updates.html")
        .render(
        {"playlist_changed_text": "\n".join(playlist_changed_text),
         "playlist_id": playlist_id}))


@login_required
def view_playlist_settings(request, playlist_id):
    try:
        playlist = request.user.playlists.get(playlist_id=playlist_id)
    except apps.main.models.Playlist.DoesNotExist:
        messages.error(request, "No such playlist found!")
        return redirect('home')

    return render(request, 'view_playlist_settings.html', {"playlist": playlist})


@login_required
def get_playlist_tags(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    playlist_tags = playlist.tags.all()

    return HttpResponse(loader.get_template("intercooler/playlist_tags.html")
        .render(
        {"playlist_id": playlist_id,
         "playlist_tags": playlist_tags}))


@login_required
def get_unused_playlist_tags(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    user_created_tags = Tag.objects.filter(created_by=request.user)
    playlist_tags = playlist.tags.all()

    unused_tags = user_created_tags.difference(playlist_tags)

    return HttpResponse(loader.get_template("intercooler/playlist_tags_unused.html")
        .render(
        {"unused_tags": unused_tags}))


@login_required
def get_watch_message(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    return HttpResponse(loader.get_template("intercooler/playlist_watch_message.html")
        .render(
        {"playlist": playlist}))


@login_required
@require_POST
def create_playlist_tag(request, playlist_id):
    tag_name = request.POST["createTagField"]

    if tag_name.lower() == 'Pick from existing unused tags'.lower():
        return HttpResponse("Can't use that! Try again >_<")

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    user_created_tags = Tag.objects.filter(created_by=request.user)
    if not user_created_tags.filter(name__iexact=tag_name).exists():  # no tag found, so create it
        tag = Tag(name=tag_name, created_by=request.user)
        tag.save()

        # add it to playlist
        playlist.tags.add(tag)

    else:
        return HttpResponse("""
                            Already created. Try Again >w<
                    """)

    # playlist_tags = playlist.tags.all()

    # unused_tags = user_created_tags.difference(playlist_tags)

    return HttpResponse(f"""
            Created and Added!
              <span class="visually-hidden" hx-get="/playlist/{playlist_id}/get-tags" hx-trigger="load" hx-target="#playlist-tags"></span>
    """)


@login_required
@require_POST
def add_playlist_tag(request, playlist_id):
    tag_name = request.POST["playlistTag"]

    if tag_name == 'Pick from existing unused tags':
        return HttpResponse("Pick something! >w<")

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_tags = playlist.tags.all()
    if not playlist_tags.filter(name__iexact=tag_name).exists():  # tag not on this playlist, so add it
        tag = Tag.objects.filter(Q(created_by=request.user) & Q(name__iexact=tag_name)).first()

        # add it to playlist
        playlist.tags.add(tag)
    else:
        return HttpResponse("Already Added >w<")

    return HttpResponse(f"""
                Added!
                  <span class="visually-hidden" hx-get="/playlist/{playlist_id}/get-tags" hx-trigger="load" hx-target="#playlist-tags"></span>
        """)


@login_required
@require_POST
def remove_playlist_tag(request, playlist_id, tag_name):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_tags = playlist.tags.all()
    if playlist_tags.filter(name__iexact=tag_name).exists():  # tag on this playlist, remove it it
        tag = Tag.objects.filter(Q(created_by=request.user) & Q(name__iexact=tag_name)).first()

        print("Removed tag", tag_name)
        # remove it from the playlist
        playlist.tags.remove(tag)
    else:
        return HttpResponse("Whoops >w<")

    return HttpResponse("")


@login_required
def delete_playlist(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if request.GET["confirmed"] == "no":
        return HttpResponse(f"""
            <a href="/playlist/{playlist_id}/delete-playlist?confirmed=yes" class="btn btn-danger">Confirm Delete</a>
            <a href="/playlist/{playlist_id}" class="btn btn-secondary ms-1">Cancel</a>
        """)

    if not playlist.is_user_owned:  # if playlist trying to delete isn't user owned
        playlist.delete()  # just delete it from untrue
        messages.success(request, "Successfully deleted playlist from UnTube.")
    else:
        # deletes it from YouTube first then from UnTube
        status = Playlist.objects.deletePlaylistFromYouTube(request.user, playlist_id)
        if status == -1:  # failed to delete playlist from youtube
            messages.error(request, "Failed to delete playlist from YouTube :(")
            return redirect('view_playlist_settings', playlist_id=playlist_id)

        messages.success(request, "Successfully deleted playlist from YouTube and removed it from UnTube as well.")

    return redirect('home')


@login_required
def reset_watched(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    for video in playlist.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=False)):
        video.is_marked_as_watched = False
        video.save(update_fields=['is_marked_as_watched'])

    # messages.success(request, "Successfully marked all videos unwatched.")

    return redirect(f'/playlist/{playlist.playlist_id}')


@login_required
@require_POST
def playlist_move_copy_videos(request, playlist_id, action):
    playlist_ids = request.POST.getlist("playlist-ids", default=[])
    playlist_item_ids = request.POST.getlist("video-id", default=[])

    # basic processing
    if not playlist_ids and not playlist_item_ids:
        return HttpResponse(f"""
                <span class="text-warning">Mistakes happen. Try again >w<</span>""")
    elif not playlist_ids:
        return HttpResponse(f"""
        <span class="text-danger">First select some playlists to {action} to!</span>""")
    elif not playlist_item_ids:
        return HttpResponse(f"""
                <span class="text-danger">First select some videos to {action}!</span>""")

    success_message = f"""
                <div hx-ext="class-tools">
                <span classes="add visually-hidden:5s" class="text-success">Successfully {'moved' if action == 'move' else 'copied'} {len(playlist_item_ids)} video(s) to {len(playlist_ids)} other playlist(s)! 
                Go visit those playlist(s)!</span>
                </div>
                """
    if action == "move":
        status = Playlist.objects.moveCopyVideosFromPlaylist(request.user,
                                                             from_playlist_id=playlist_id,
                                                             to_playlist_ids=playlist_ids,
                                                             playlist_item_ids=playlist_item_ids,
                                                             action="move")
        if status[0] == -1:
            if status[1] == 404:
                return HttpResponse("<span class='text-danger'>You cannot copy/move unavailable videos! De-select them and try again.</span>")
            return HttpResponse("Error moving!")
    else:  # copy
        status = Playlist.objects.moveCopyVideosFromPlaylist(request.user,
                                                             from_playlist_id=playlist_id,
                                                             to_playlist_ids=playlist_ids,
                                                             playlist_item_ids=playlist_item_ids)
        if status[0] == -1:
            if status[1] == 404:
                return HttpResponse("<span class='text-danger'>You cannot copy/move unavailable videos! De-select them and try again.</span>")
            return HttpResponse("Error copying!")

    return HttpResponse(success_message)

@login_required
def playlist_open_random_video(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    videos = playlist.videos.all()

    random_video = random.choice(videos)

    return redirect(f'/video/{random_video.video_id}')

@login_required
def playlist_completion_times(request, playlist_id):
    playlist_duration = request.user.playlists.get(playlist_id=playlist_id).playlist_duration_in_seconds

    return HttpResponse(f"""
        <h5 class="text-warning">Playlist completion times:</h5>
        <h6>At 1.25x speed: {getHumanizedTimeString(playlist_duration/1.25)}</h6>
        <h6>At 1.5x speed: {getHumanizedTimeString(playlist_duration/1.5)}</h6>
        <h6>At 1.75x speed: {getHumanizedTimeString(playlist_duration/1.75)}</h6>
        <h6>At 2x speed: {getHumanizedTimeString(playlist_duration/2)}</h6>
    """)
