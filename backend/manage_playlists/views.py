import bleach
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.views.decorators.http import require_POST
from backend.main.models import Playlist


@login_required
def manage_playlists(request):
    return render(request, 'manage_playlists.html')


@login_required
def manage_view_page(request, page):
    if page == 'import':
        return render(
            request, 'manage_playlists_import.html',
            {'manage_playlists_import_textarea': request.user.profile.manage_playlists_import_textarea}
        )
    elif page == 'create':
        return render(request, 'manage_playlists_create.html')
    else:
        return HttpResponse('Working on this!')


@login_required
@require_POST
def manage_save(request, what):
    if what == 'manage_playlists_import_textarea':
        request.user.profile.manage_playlists_import_textarea = bleach.clean(request.POST['import-playlist-textarea'])
        request.user.save()

    return HttpResponse('')


@login_required
@require_POST
def manage_import_playlists(request):
    playlist_links = [
        bleach.clean(link) for link in request.POST['import-playlist-textarea'].replace(',', '').split('\n')
    ]

    num_playlists_already_in_db = 0
    num_playlists_initialized_in_db = 0
    num_playlists_not_found = 0
    new_playlists = []
    old_playlists = []
    not_found_playlists = []

    done = []
    for playlist_link in playlist_links:
        if playlist_link.strip() != '' and playlist_link.strip() not in done:
            pl_id = Playlist.objects.getPlaylistId(playlist_link.strip())
            if pl_id is None:
                num_playlists_not_found += 1
                continue

            status = Playlist.objects.initializePlaylist(request.user, pl_id)['status']
            if status == -1 or status == -2:
                print('\nNo such playlist found:', pl_id)
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

    request.user.profile.manage_playlists_import_textarea = ''
    request.user.save()

    return HttpResponse(
        loader.get_template('intercooler/manage_playlists_import_results.html').render({
            'new_playlists': new_playlists,
            'old_playlists': old_playlists,
            'not_found_playlists': not_found_playlists,
            'num_playlists_already_in_db': num_playlists_already_in_db,
            'num_playlists_initialized_in_db': num_playlists_initialized_in_db,
            'num_playlists_not_found': num_playlists_not_found
        })
    )


@login_required
@require_POST
def manage_create_playlist(request):
    print(request.POST)
    return HttpResponse('')


@login_required
@require_POST
def manage_nuke_playlists(request):
    print(request.POST)
    return HttpResponse('')
