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
    user_playlists = user_profile.playlists.order_by("-num_of_accesses")
    watching = user_profile.playlists.filter(marked_as="watching").order_by("-num_of_accesses")

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
                                         "watching": watching})


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
    user_playlists = user_profile.playlists.all()

    # specific playlist requested
    playlist = user_profile.playlists.get(playlist_id__exact=playlist_id)
    playlist.num_of_accesses += 1
    playlist.save()

    videos = playlist.videos.all()

    if not playlist.has_playlist_changed:
        print("Checking if playlist changed...")
        result = Playlist.objects.checkIfPlaylistChangedOnYT(request.user, playlist_id)

        if result[0] == -1:  # playlist changed
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

    return render(request, 'view_playlist.html', {"playlist": playlist,
                                                  "videos": videos,
                                                  "user_playlists": user_playlists})


@login_required
def all_playlists(request, playlist_type):
    """
    Possible playlist types for marked_as attribute: (saved in database like this)
    "none", "watching", "plan-to-watch"
    """
    playlist_type = playlist_type.lower()

    if playlist_type == "" or playlist_type == "all":
        playlists = request.user.profile.playlists.all()
        playlist_type_display = "All Playlists"
    elif playlist_type == "user-owned":  # YT playlists owned by user
        playlists = request.user.profile.playlists.all().filter(is_user_owned=True)
        playlist_type_display = "Your YouTube Playlists"
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        playlists = request.user.profile.playlists.all().filter(is_user_owned=False)
        playlist_type_display = "Imported playlists"
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        playlists = request.user.profile.playlists.all().filter(is_favorite=True)
        playlist_type_display = "Favorites"
    elif playlist_type.lower() in ["watching", "plan-to-watch"]:
        playlists = request.user.profile.playlists.filter(marked_as=playlist_type.lower())
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
    playlist = request.user.profile.playlists.get(playlist_id=playlist_id)

    if order_by == "popularity":
        videos = playlist.videos.order_by("-like_count")
    elif order_by == "date-published":
        videos = playlist.videos.order_by("-published_at")
    elif order_by == "views":
        videos = playlist.videos.order_by("-view_count")
    elif order_by == "has-cc":
        videos = playlist.videos.filter(has_cc=True)
    elif order_by == "duration":
        videos = playlist.videos.order_by("-duration_in_seconds")
    else:
        return redirect('home')

    return HttpResponse(loader.get_template("intercooler/videos.html").render({"playlist": playlist, "videos": videos}))


@login_required
def order_playlists_by(request, playlist_type, order_by):
    if playlist_type == "" or playlist_type.lower() == "all":
        playlists = request.user.profile.playlists.all().order_by(f"-{order_by.replace('-', '_')}")
        playlist_type = "All Playlists"
    elif playlist_type.lower() == "favorites":
        playlists = request.user.profile.playlists.filter(is_favorite=True).order_by(f"-{order_by.replace('-', '_')}")
        playlist_type = "Favorites"
    elif playlist_type.lower() == "watching":
        playlists = request.user.profile.playlists.filter(on_watch=True).order_by(f"-{order_by.replace('-', '_')}")
        playlist_type = "Watching"
    else:
        return redirect('home')

    return render(request, 'all_playlists.html', {"playlists": playlists, "playlist_type": playlist_type})


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
    else:
        return render('home')

    return HttpResponse(marked_as_response)


@login_required
def playlists_home(request):
    return render(request, 'playlists_home.html')


@login_required
@require_POST
def delete_videos(request):
    print(request.POST)
    return HttpResponse("Worked!")


@login_required
@require_POST
def search_playlists(request, playlist_type):
    print(request.POST)  # prints <QueryDict: {'search': ['aa']}>

    search_query = request.POST["search"]

    if playlist_type == "all":
        try:
            playlists = request.user.profile.playlists.all().filter(name__startswith=search_query)
        except:
            playlists = request.user.profile.playlists.all()
        playlist_type_display = "All Playlists"
    elif playlist_type == "user-owned":  # YT playlists owned by user
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_user_owned=True))
        except:
            playlists = request.user.profile.playlists.filter(is_user_owned=True)
        playlist_type_display = "Your YouTube Playlists"
    elif playlist_type == "imported":  # YT playlists (public) owned by others
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_user_owned=False))
        except:
            playlists = request.user.profile.playlists.filter(is_user_owned=False)
        playlist_type_display = "Imported Playlists"
    elif playlist_type == "favorites":  # YT playlists (public) owned by others
        try:
            playlists = request.user.profile.playlists.filter(Q(name__startswith=search_query) & Q(is_favorite=True))
        except:
            playlists = request.user.profile.playlists.filter(is_favorite=True)
        playlist_type_display = "Your Favorites"
    elif playlist_type in ["watching", "plan-to-watch"]:
        try:
            playlists = request.user.profile.playlists.filter(
                Q(name__startswith=search_query) & Q(marked_as=playlist_type))
        except:
            playlists = request.user.profile.playlists.all().filter(marked_as=playlist_type)
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

    all_playlists = request.user.profile.playlists.all()
    videos = []
    starts_with = False
    contains = False

    if request.POST['search-settings'] == 'starts-with':
        playlists = request.user.profile.playlists.filter(name__startswith=search_query) if search_query != "" else []

        if search_query != "":
            for playlist in all_playlists:
                pl_videos = playlist.videos.filter(name__startswith=search_query)

                if pl_videos.count() != 0:
                    for v in pl_videos.all():
                        videos.append(v)

        starts_with = True
    else:
        playlists = request.user.profile.playlists.filter(name__contains=search_query) if search_query != "" else []

        if search_query != "":
            for playlist in all_playlists:
                pl_videos = playlist.videos.filter(name__contains=search_query)

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
        return HttpResponse("<br><hr><br><h2>Working on this.</h2>")
    elif page == "untube":
        return HttpResponse("<br><hr><br><h2>Coming soon. Maybe.</h2>")
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
    for playlist_link in playlist_links:
        if playlist_link != "":
            pl_id = Playlist.objects.getPlaylistId(playlist_link)
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
