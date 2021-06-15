import datetime

import pytz
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from apps.main.models import Playlist
from django.contrib.auth.decorators import login_required  # redirects user to settings.LOGIN_URL
from allauth.socialaccount.models import SocialToken
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.template import Context, loader


# Create your views here.
@login_required
def home(request):
    user_profile = request.user.profile
    user_playlists = user_profile.playlists.filter(is_in_db=True).order_by("-num_of_accesses")
    watching = user_profile.playlists.filter(Q(marked_as="watching") & Q(is_in_db=True)).order_by("-num_of_accesses")
    recently_accessed_playlists = user_profile.playlists.filter(is_in_db=True).order_by("-updated_at")[:6]
    recently_added_playlists = user_profile.playlists.filter(is_in_db=True).order_by("-created_at")[:6]

    #### FOR NEWLY JOINED USERS ######
    channel_found = True
    if user_profile.just_joined:
        if user_profile.import_in_progress:
            return render(request, "import_in_progress.html")
        else:
            if user_profile.access_token.strip() == "" or user_profile.refresh_token.strip() == "":
                user_social_token = SocialToken.objects.get(account__user=request.user)
                user_profile.access_token = user_social_token.token
                user_profile.refresh_token = user_social_token.token_secret
                user_profile.expires_at = user_social_token.expires_at
                request.user.save()

            user_profile.just_joined = False
            user_profile.save()

            return render(request, "home.html", {"import_successful": True})

        # if Playlist.objects.getUserYTChannelID(request.user) == -1:  # user channel not found
        #    channel_found = False
        # else:
        #   Playlist.objects.initPlaylist(request.user, None)  # get all playlists from user's YT channel
        #  return render(request, "home.html", {"import_successful": True})
    ##################################

    if request.method == "POST":
        print(request.POST)
        if Playlist.objects.initPlaylist(request.user, request.POST['playlist-id'].strip()) == -1:
            print("No such playlist found.")
            playlist = []
            videos = []
        else:
            playlist = user_profile.playlists.get(playlist_id__exact=request.POST['playlist-id'].strip())
            videos = playlist.videos.all()
    else:  # GET request
        videos = []
        playlist = []

        print("TESTING")

    return render(request, 'home.html', {"channel_found": channel_found,
                                         "playlist": playlist,
                                         "videos": videos,
                                         "user_playlists": user_playlists,
                                         "watching": watching,
                                         "recently_accessed_playlists": recently_accessed_playlists,
                                         "recently_added_playlists": recently_added_playlists})


@login_required
def view_video(request, playlist_id, video_id):
    video = request.user.profile.playlists.get(playlist_id=playlist_id).videos.get(video_id=video_id)
    print(video.name)
    return HttpResponse(loader.get_template("intercooler/video_details.html").render({"video": video}))


@login_required
def video_notes(request, playlist_id, video_id):
    video = request.user.profile.playlists.get(playlist_id=playlist_id).videos.get(video_id=video_id)

    if request.method == "POST":
        if 'video-notes-text-area' in request.POST:
            video.user_notes = request.POST['video-notes-text-area']
            video.save()
            return HttpResponse(loader.get_template("intercooler/messages.html").render(
                {"message_type": "success", "message_content": "Saved!"}))
    else:
        print("GET VIDEO NOTES")

    return HttpResponse(loader.get_template("intercooler/video_notes.html").render({"video": video,
                                                                                    "playlist_id": playlist_id}))


@login_required
def view_playlist(request, playlist_id):
    user_profile = request.user.profile

    # specific playlist requested
    if user_profile.playlists.filter(Q(playlist_id=playlist_id) & Q(is_in_db=True)).count() != 0:
        playlist = user_profile.playlists.get(playlist_id__exact=playlist_id)
        playlist.num_of_accesses += 1
        playlist.save()
    else:
        messages.error(request, "No such playlist found!")
        return redirect('home')

    videos = playlist.videos.order_by("video_position")

    return render(request, 'view_playlist.html', {"playlist": playlist,
                                                  "videos": videos})


@login_required
def all_playlists(request, playlist_type):
    """
    Possible playlist types for marked_as attribute: (saved in database like this)
    "none", "watching", "plan-to-watch"
    """
    playlist_type = playlist_type.lower()

    if playlist_type == "" or playlist_type == "all":
        playlists = request.user.profile.playlists.all().filter(is_in_db=True)
        playlist_type_display = "All Playlists"
    elif playlist_type == "user-owned":  # YT playlists owned by user
        playlists = request.user.profile.playlists.all().filter(Q(is_user_owned=True) & Q(is_in_db=True))
        playlist_type_display = "Your YouTube Playlists"
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        playlists = request.user.profile.playlists.all().filter(Q(is_user_owned=False) & Q(is_in_db=True))
        playlist_type_display = "Imported playlists"
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        playlists = request.user.profile.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        playlist_type_display = "Favorites"
    elif playlist_type.lower() in ["watching", "plan-to-watch"]:
        playlists = request.user.profile.playlists.filter(Q(marked_as=playlist_type.lower()) & Q(is_in_db=True))
        playlist_type_display = playlist_type.lower().replace("-", " ")
    elif playlist_type.lower() == "home":  # displays cards of all playlist types
        return render(request, 'playlists_home.html')
    else:
        return redirect('home')

    return render(request, 'all_playlists.html', {"playlists": playlists,
                                                  "playlist_type": playlist_type,
                                                  "playlist_type_display": playlist_type_display})


@login_required
def order_playlist_by(request, playlist_id, order_by):
    playlist = request.user.profile.playlists.get(Q(playlist_id=playlist_id) & Q(is_in_db=True))

    display_text = "Nothing in this playlist! Add something!"  # what to display when requested order/filter has no videws

    if order_by == "all":
        videos = playlist.videos.order_by("video_position")
    elif order_by == "favorites":
        videos = playlist.videos.filter(is_favorite=True).order_by("video_position")
        display_text = "No favorites yet!"
    elif order_by == "popularity":
        videos = playlist.videos.order_by("-like_count")
    elif order_by == "date-published":
        videos = playlist.videos.order_by("-published_at")
    elif order_by == "views":
        videos = playlist.videos.order_by("-view_count")
    elif order_by == "has-cc":
        videos = playlist.videos.filter(has_cc=True).order_by("video_position")
        display_text = "No videos in this playlist have CC :("
    elif order_by == "duration":
        videos = playlist.videos.order_by("-duration_in_seconds")
    elif order_by == 'new-updates':
        videos = []
        display_text = "No new updates! Note that deleted videos will not show up here."
        if playlist.has_new_updates:
            recently_updated_videos = playlist.videos.filter(video_details_modified=True)

            for video in recently_updated_videos:
                if video.video_details_modified_at + datetime.timedelta(hours=12) < datetime.datetime.now(
                        pytz.utc):  # expired
                    video.video_details_modified = False
                    video.save()

            if recently_updated_videos.count() == 0:
                playlist.has_new_updates = False
                playlist.save()
            else:
                videos = recently_updated_videos.order_by("video_position")
    else:
        return redirect('home')

    return HttpResponse(loader.get_template("intercooler/videos.html").render({"playlist": playlist,
                                                                               "videos": videos,
                                                                               "display_text": display_text}))


@login_required
def order_playlists_by(request, playlist_type, order_by):
    if playlist_type == "" or playlist_type.lower() == "all":
        playlists = request.user.profile.playlists.all()
        playlist_type_display = "All Playlists"
    elif playlist_type.lower() == "favorites":
        playlists = request.user.profile.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
        playlist_type_display = "Favorites"
    elif playlist_type.lower() in ["watching", "plan-to-watch"]:
        playlists = request.user.profile.playlists.filter(Q(marked_as=playlist_type.lower()) & Q(is_in_db=True))
        playlist_type_display = "Watching"
    else:
        return redirect('home')

    if order_by == 'recently-accessed':
        playlists = playlists.order_by("-updated_at")
    elif order_by == 'playlist-duration-in-seconds':
        playlists = playlists.order_by("-playlist_duration_in_seconds")
    elif order_by == 'video-count':
        playlists = playlists.order_by("-video_count")

    return HttpResponse(loader.get_template("intercooler/playlists.html")
                        .render({"playlists": playlists,
                                 "playlist_type_display": playlist_type_display,
                                 "playlist_type": playlist_type}))


@login_required
def mark_playlist_as(request, playlist_id, mark_as):
    playlist = request.user.profile.playlists.get(playlist_id=playlist_id)

    marked_as_response = ""

    if mark_as in ["watching", "on-hold", "plan-to-watch"]:
        playlist.marked_as = mark_as
        playlist.save()
        marked_as_response = f'<span class="badge bg-success text-white" >{mark_as.replace("-", " ")}</span>'
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
        return render('home')

    return HttpResponse(marked_as_response)


@login_required
def playlists_home(request):
    return render(request, 'playlists_home.html')


@login_required
@require_POST
def delete_videos(request, playlist_id, command):
    video_ids = request.POST.getlist("video-id", default=[])

    if command == "confirm":
        print(video_ids)
        num_vids = len(video_ids)
        extra_text = " "
        if num_vids == 0:
            return HttpResponse("<h5>Select some videos first!</h5>")
        elif num_vids == request.user.profile.playlists.get(playlist_id=playlist_id).videos.all().count():
            delete_text = "ALL VIDEOS"
            extra_text = " This will not delete the playlist itself, will only make the playlist empty. "
        else:
            delete_text = f"{num_vids} videos"
        return HttpResponse(
            f"<h5>Are you sure you want to delete {delete_text} from your YouTube playlist?{extra_text}This cannot be undone.</h5>")
    elif command == "confirmed":
        return HttpResponse(
            f'<div class="spinner-border text-light" role="status" hx-post="/from/{playlist_id}/delete-videos/start" hx-trigger="load" hx-swap="outerHTML"></div>')
    elif command == "start":
        for i in range(1000):
            pass
        return HttpResponse('DONE!')
    print(len(video_ids), request.POST)
    return HttpResponse("Worked!")


@login_required
@require_POST
def search_playlists(request, playlist_type):
    print(request.POST)  # prints <QueryDict: {'search': ['aa']}>

    search_query = request.POST["search"]

    if playlist_type == "all":
        try:
            playlists = request.user.profile.playlists.all().filter(Q(name__startswith=search_query) & Q(is_in_db=True))
        except:
            playlists = request.user.profile.playlists.all()
        playlist_type_display = "All Playlists"
    elif playlist_type == "user-owned":  # YT playlists owned by user
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_user_owned=True) & Q(is_in_db=True))
        except:
            playlists = request.user.profile.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
        playlist_type_display = "Your YouTube Playlists"
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_user_owned=False) & Q(is_in_db=True))
        except:
            playlists = request.user.profile.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
        playlist_type_display = "Imported Playlists"
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_favorite=True) & Q(is_in_db=True))
        except:
            playlists = request.user.profile.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
        playlist_type_display = "Your Favorites"
    elif playlist_type in ["watching", "plan-to-watch"]:
        try:
            playlists = request.user.profile.playlists.filter(
                Q(name__startswith=search_query) & Q(marked_as=playlist_type) & Q(is_in_db=True))
        except:
            playlists = request.user.profile.playlists.all().filter(Q(marked_as=playlist_type) & Q(is_in_db=True))
        playlist_type_display = playlist_type.replace("-", " ")

    return HttpResponse(loader.get_template("intercooler/playlists.html")
                        .render({"playlists": playlists,
                                 "playlist_type_display": playlist_type_display,
                                 "playlist_type": playlist_type,
                                 "search_query": search_query}))


#### MANAGE VIDEOS #####
def mark_video_favortie(request, playlist_id, video_id):
    video = request.user.profile.playlists.get(playlist_id=playlist_id).videos.get(video_id=video_id)

    if video.is_favorite:
        video.is_favorite = False
        video.save()
        return HttpResponse('<i class="far fa-heart"></i>')
    else:
        video.is_favorite = True
        video.save()
        return HttpResponse('<i class="fas fa-heart"></i>')


###########

@login_required
@require_POST
def search_UnTube(request):
    print(request.POST)

    search_query = request.POST["search"]

    all_playlists = request.user.profile.playlists.filter(is_in_db=True)
    videos = []
    starts_with = False
    contains = False

    if request.POST['search-settings'] == 'starts-with':
        playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_in_db=True)) if search_query != "" else []

        if search_query != "":
            for playlist in all_playlists:
                pl_videos = playlist.videos.filter(name__startswith=search_query)

                if pl_videos.count() != 0:
                    for v in pl_videos.all():
                        videos.append(v)

        starts_with = True
    else:
        playlists = request.user.profile.playlists.filter(Q(name__contains=search_query) & Q(is_in_db=True)) if search_query != "" else []

        if search_query != "":
            for playlist in all_playlists:
                pl_videos = playlist.videos.filter(Q(name__contains=search_query) & Q(is_in_db=True))

                if pl_videos.count() != 0:
                    for v in pl_videos.all():
                        videos.append(v)

        contains = True
    return HttpResponse(loader.get_template("intercooler/search_untube.html")
                        .render({"playlists": playlists,
                                 "videos": videos,
                                 "videos_count": len(videos),
                                 "search_query": search_query,
                                 "starts_with": starts_with,
                                 "contains": contains}))


@login_required
def manage_playlists(request):
    return render(request, "manage_playlists.html")


@login_required
def manage_view_page(request, page):
    if page == "import":
        return HttpResponse(loader.get_template("intercooler/manage_playlists_import.html")
            .render(
            {"manage_playlists_import_textarea": request.user.profile.manage_playlists_import_textarea}))
    elif page == "create":
        return HttpResponse(loader.get_template("intercooler/manage_playlists_create.html")
            .render(
            {}))
    else:
        return redirect('home')


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
            status = Playlist.objects.initPlaylist(request.user, pl_id)
            if status == -1 or status == -2:
                print("\nNo such playlist found:", pl_id)
                num_playlists_not_found += 1
                not_found_playlists.append(playlist_link)
            elif status == -3:
                num_playlists_already_in_db += 1
                playlist = request.user.profile.playlists.get(playlist_id__exact=pl_id)
                old_playlists.append(playlist)
            else:
                print(status)
                playlist = request.user.profile.playlists.get(playlist_id__exact=pl_id)
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
def update_playlist(request, playlist_id, type):
    playlist = request.user.profile.playlists.get(playlist_id=playlist_id)

    if type == "checkforupdates":
        print("Checking if playlist changed...")
        result = Playlist.objects.checkIfPlaylistChangedOnYT(request.user, playlist_id)

        if result[0] == 1:  # full scan was done (full scan is done for a playlist if a week has passed)
            deleted_videos, unavailable_videos, added_videos = result[1:]

            print("CHANGES", deleted_videos, unavailable_videos, added_videos)

            playlist_changed_text = ["The following modifications happened to this playlist on YouTube:"]
            if deleted_videos != 0 or unavailable_videos != 0 or added_videos != 0:
                if added_videos > 0:
                    playlist_changed_text.append(f"{added_videos} new video(s) were added")
                if deleted_videos > 0:
                    playlist_changed_text.append(f"{deleted_videos} video(s) were deleted")
                if unavailable_videos > 0:
                    playlist_changed_text.append(f"{unavailable_videos} video(s) went private/unavailable")

                playlist.playlist_changed_text = "\n".join(playlist_changed_text)
                playlist.has_playlist_changed = True
                playlist.save()

        elif result[0] == -1:  # playlist changed
            print("!!!Playlist changed")

            current_playlist_vid_count = playlist.video_count
            new_playlist_vid_count = result[1]

            print(current_playlist_vid_count)
            print(new_playlist_vid_count)

            if current_playlist_vid_count > new_playlist_vid_count:
                playlist.playlist_changed_text = f"Looks like {current_playlist_vid_count - new_playlist_vid_count} video(s) were deleted from this playlist on YouTube!"
            else:
                playlist.playlist_changed_text = f"Looks like {new_playlist_vid_count - current_playlist_vid_count} video(s) were added to this playlist on YouTube!"

            playlist.has_playlist_changed = True
            playlist.save()
            print(playlist.playlist_changed_text)
        else:  # no updates found
            return HttpResponse("""
            <div class="alert alert-success alert-dismissible fade show visually-hidden" role="alert">
                No new updates!
            </div>
            """)

        return HttpResponse(f"""
        <div hx-get="/playlist/{playlist_id}/update/auto" hx-trigger="load" hx-target="#view_playlist">
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                {playlist.playlist_changed_text}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
            <div class="d-flex justify-content-center mt-4 mb-3" id="loading-sign">
                <img src="/static/svg-loaders/circles.svg" width="40" height="40">
                <h5 class="mt-2 ms-2">Updating playlist '{playlist.name}', please wait!</h5>
            </div>
        </div>
        """)

    if type == "manual":
        print("MANUAL")
        return HttpResponse(
            f"""<div hx-get="/playlist/{playlist_id}/update/auto" hx-trigger="load" hx-swap="outerHTML">
                    <div class="d-flex justify-content-center mt-4 mb-3" id="loading-sign">
                        <img src="/static/svg-loaders/circles.svg" width="40" height="40">
                        <h5 class="mt-2 ms-2">Refreshing playlist '{playlist.name}', please wait!</h5>
                    </div>
                </div>""")

    print("Attempting to update playlist")
    status, deleted_video_ids, unavailable_videos, added_videos = Playlist.objects.updatePlaylist(request.user, playlist_id)

    playlist = request.user.profile.playlists.get(playlist_id=playlist_id)

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
        for video in added_videos[:3]:
            playlist_changed_text.append(f"--> {video.name}")

        if len(added_videos) > 3:
            playlist_changed_text.append(f"+ {len(added_videos) - 3} more")

    if len(unavailable_videos) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f"{len(unavailable_videos)} went unavailable")
        else:
            playlist_changed_text.append(f"\n{len(unavailable_videos)} went unavailable")
        for video in unavailable_videos:
            playlist_changed_text.append(f"--> {video.name}")
    if len(deleted_video_ids) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f"{len(deleted_video_ids)} deleted")
        else:
            playlist_changed_text.append(f"\n{len(deleted_video_ids)} deleted")

        for video_id in deleted_video_ids:
            video = playlist.videos.get(video_id=video_id)
            playlist_changed_text.append(f"--> {video.name}")
            video.delete()

    if len(playlist_changed_text) == 0:
        playlist_changed_text = ["Successfully refreshed playlist! No new changes found!"]

    return HttpResponse(loader.get_template("intercooler/updated_playlist.html")
        .render(
        {"playlist_changed_text": "\n".join(playlist_changed_text),
         "playlist": playlist,
         "videos": playlist.videos.order_by("video_position")}))
