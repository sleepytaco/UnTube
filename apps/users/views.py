from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from allauth.socialaccount.models import SocialToken
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from apps.main.models import Playlist
from django.template import loader


# Create your views here.
def index(request):
    if request.user.is_anonymous:
        return render(request, 'index.html')
    else:
        return redirect('home')


@require_POST
def update_settings(request):
    print(request.POST)
    user = request.user
    username_input = request.POST['username'].strip()
    message_content = "Saved! Refresh to see changes!"
    message_type = "success"
    if username_input != user.username:
        if User.objects.filter(username__exact=username_input).count() != 0:
            message_type = "danger"
            message_content = f"Username {request.POST['username'].strip()} already taken"
        else:
            user.username = request.POST['username'].strip()
            user.save()
            message_content = f"Username updated to {username_input}!"

    return HttpResponse(loader.get_template("intercooler/messages.html").render(
        {"message_type": message_type, "message_content": message_content}))


@login_required
def delete_account(request):
    request.user.profile.delete()
    request.user.delete()
    request.session.flush()
    messages.success(request, "Account data deleted successfully.")

    return redirect('index')


def log_out(request):
    request.session.flush()  # delete all stored session keys
    logout(request)  # log out authenticated user
    return redirect('/')


def test(request):
    return render(request, 'test.html')


def start_import(request):
    '''
    Initializes only the user's playlist data in the database. Returns the progress bar, which will
    keep calling continue_import
    :param request:
    :return:
    '''
    user_profile = request.user.profile

    if user_profile.access_token == "" or user_profile.refresh_token == "":
        user_social_token = SocialToken.objects.get(account__user=request.user)
        user_profile.access_token = user_social_token.token
        user_profile.refresh_token = user_social_token.token_secret
        user_profile.expires_at = user_social_token.expires_at

        request.user.save()

    result = Playlist.objects.getAllPlaylistsFromYT(request.user)
    channel_found = True
    if result["status"] == -1:
        print("User has no YT channel")
        channel_found = False

        return HttpResponse(loader.get_template('intercooler/progress_bar.html').render(
            {"channel_found": channel_found}
        ))
    elif result["status"] == -2:
        print("User has no playlists on YT")

        return HttpResponse(loader.get_template('intercooler/progress_bar.html').render(
            {"total_playlists": 'IMPORTED 0 PLAYLISTS lol',
             "playlists_imported": 0,
             "done": True,
             "progress": 100,
             "channel_found": channel_found}))
    else:
        return HttpResponse(loader.get_template('intercooler/progress_bar.html').render(
            {"total_playlists": result["num_of_playlists"],
             "playlist_name": result["first_playlist_name"],
             "playlists_imported": 0,
             "progress": 0,
             "channel_found": channel_found}
        ))


def continue_import(request):
    if request.user.profile.import_in_progress is False:
        return redirect('home')

    num_of_playlists = request.user.profile.playlists.count()

    try:
        remaining_playlists = request.user.profile.playlists.filter(is_in_db=False)
        playlists_imported = num_of_playlists - remaining_playlists.count() + 1
        playlist = remaining_playlists.order_by("created_at")[0]
        playlist_name = playlist.name
        playlist_id = playlist.playlist_id
        Playlist.objects.getAllVideosForPlaylist(request.user, playlist.playlist_id)
    except:
        playlist_id = -1

    if playlist_id != -1:
        return HttpResponse(loader.get_template('intercooler/progress_bar.html').render(
            {"total_playlists": num_of_playlists,
             "playlists_imported": playlists_imported,
             "playlist_name": playlist_name,
             "progress": round((playlists_imported / num_of_playlists) * 100, 1),
             "channel_found": True}))
    else:
        # request.user.profile.just_joined = False
        request.user.profile.import_in_progress = False
        request.user.save()

        return HttpResponse(loader.get_template('intercooler/progress_bar.html').render(
            {"total_playlists": num_of_playlists,
             "playlists_imported": num_of_playlists,
             "done": True,
             "progress": 100,
             "channel_found": True}))
