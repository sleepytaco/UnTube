import random

import bleach
from django.contrib import messages
from django.contrib.auth.decorators import login_required  # redirects user to settings.LOGIN_URL
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.views.decorators.http import require_POST
from .models import Playlist, Tag
from .util import *
import logging

logger = logging.getLogger(__name__)


# Create your views here.
@login_required
def home(request):
    user_profile = request.user

    # FOR NEWLY JOINED USERS
    # channel_found = True
    if user_profile.profile.show_import_page:
        """
        Logic:
        show_import_page is True by default. When a user logs in for the first time (infact anytime), google
        redirects them to 'home' url. Since, show_import_page is True by default, the user is then redirected
        from 'home' to 'import_in_progress' url show_import_page is only set false in the import_in_progress.html
        page, i.e when user cancels YT import
        """
        Playlist.objects.getUserYTChannelID(request.user)

        # after user imports all their YT playlists no need to show_import_page again
        if user_profile.profile.imported_yt_playlists:
            user_profile.profile.show_import_page = False
            user_profile.profile.save(update_fields=['show_import_page'])
            imported_playlists_count = request.user.playlists.filter(Q(is_user_owned=True) &
                                                                     Q(is_in_db=True)).exclude(playlist_id='LL'
                                                                                               ).count()
            return render(
                request, 'home.html', {
                    'import_successful': True,
                    'imported_playlists_count': imported_playlists_count
                }
            )

        return render(request, 'import_in_progress.html')
    ##################################

    watching = user_profile.playlists.filter(Q(marked_as='watching') & Q(is_in_db=True)).order_by('-num_of_accesses')
    recently_accessed_playlists = user_profile.playlists.filter(is_in_db=True).order_by('-updated_at')[:6]
    recently_added_playlists = user_profile.playlists.filter(is_in_db=True).order_by('-created_at')[:6]
    playlist_tags = request.user.playlist_tags.filter(times_viewed_per_week__gte=1).order_by('-times_viewed_per_week')
    videos = request.user.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=False))
    channels = videos.values('channel_name').annotate(channel_videos_count=Count('video_id'))

    return render(
        request, 'home.html', {
            'playlist_tags': playlist_tags,
            'watching': watching,
            'recently_accessed_playlists': recently_accessed_playlists,
            'recently_added_playlists': recently_added_playlists,
            'videos': videos,
            'channels': channels
        }
    )


@login_required
def favorites(request):
    favorite_playlists = request.user.playlists.filter(Q(is_favorite=True) &
                                                       Q(is_in_db=True)).order_by('-last_accessed_on')
    favorite_videos = request.user.videos.filter(is_favorite=True).order_by('-num_of_accesses')

    return render(request, 'favorites.html', {'playlists': favorite_playlists, 'videos': favorite_videos})


@login_required
def planned_to_watch(request):
    planned_to_watch_playlists = request.user.playlists.filter(Q(marked_as='plan-to-watch') &
                                                               Q(is_in_db=True)).order_by('-last_accessed_on')
    planned_to_watch_videos = request.user.videos.filter(is_planned_to_watch=True).order_by('-num_of_accesses')

    return render(
        request, 'planned_to_watch.html', {
            'playlists': planned_to_watch_playlists,
            'videos': planned_to_watch_videos
        }
    )


@login_required
def view_video(request, video_id):
    if request.user.videos.filter(video_id=video_id).exists():
        video = request.user.videos.get(video_id=video_id)

        if video.is_unavailable_on_yt:
            messages.error(request, 'Video went private/deleted on YouTube!')
            return redirect('home')

        video.num_of_accesses += 1
        video.save(update_fields=['num_of_accesses'])

        return render(request, 'view_video.html', {'video': video})
    else:
        messages.error(request, 'No such video in your UnTube collection!')
        return redirect('home')


@login_required
@require_POST
def video_notes(request, video_id):
    if request.user.videos.filter(video_id=video_id).exists():
        video = request.user.videos.get(video_id=video_id)

        if 'video-notes-text-area' in request.POST:
            video.user_notes = bleach.clean(request.POST['video-notes-text-area'], tags=['br'])
            video.save(update_fields=['user_notes', 'user_label'])
            # messages.success(request, 'Saved!')

        return HttpResponse(
            """
            <div hx-ext='class-tools'>
                <div classes='add visually-hidden:2s'>Saved!</div>
            </div>
        """
        )
    else:
        return HttpResponse('No such video in your UnTube collection!')


@login_required
def view_playlist(request, playlist_id):
    user_profile = request.user
    user_owned_playlists = user_profile.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))

    # specific playlist requested
    if user_profile.playlists.filter(Q(playlist_id=playlist_id) & Q(is_in_db=True)).exists():
        playlist = user_profile.playlists.get(playlist_id__exact=playlist_id)
        playlist_tags = playlist.tags.all()

        # if its been 1 days since the last full scan, force refresh the playlist
        if playlist.last_full_scan_at + datetime.timedelta(days=2) < datetime.datetime.now(pytz.utc):
            playlist.has_playlist_changed = True
            logger.info('ITS BEEN 15 DAYS, FORCE REFRESHING PLAYLIST')

        # only note down that the playlist as been viewed when 30s has passed since the last access
        if playlist.last_accessed_on + datetime.timedelta(seconds=30) < datetime.datetime.now(pytz.utc):
            playlist.last_accessed_on = datetime.datetime.now(pytz.utc)
            playlist.num_of_accesses += 1
            increment_tag_views(playlist_tags)

        playlist.save(update_fields=['num_of_accesses', 'last_accessed_on', 'has_playlist_changed'])
    else:
        if playlist_id == 'LL':  # liked videos playlist hasnt been imported yet
            return render(request, 'view_playlist.html', {'not_imported_LL': True})
        messages.error(request, 'No such playlist found!')
        return redirect('home')

    if playlist.has_new_updates:
        recently_updated_videos = playlist.videos.filter(video_details_modified=True)

        for video in recently_updated_videos:
            if video.video_details_modified_at + datetime.timedelta(hours=12) < datetime.datetime.now(
                pytz.utc
            ):  # expired
                video.video_details_modified = False
                video.save()

        if not recently_updated_videos.exists():
            playlist.has_new_updates = False
            playlist.save()

    playlist_items = playlist.playlist_items.select_related('video').order_by('video_position')

    user_created_tags = Tag.objects.filter(created_by=request.user)
    # unused_tags = user_created_tags.difference(playlist_tags)

    if request.user.profile.hide_unavailable_videos:
        playlist_items.exclude(Q(video__is_unavailable_on_yt=True) & Q(video__was_deleted_on_yt=False))

    return render(
        request, 'view_playlist.html', {
            'playlist': playlist,
            'playlist_tags': playlist_tags,
            'unused_tags': user_created_tags,
            'playlist_items': playlist_items,
            'user_owned_playlists': user_owned_playlists,
            'watching_message': generateWatchingMessage(playlist),
        }
    )


@login_required
def tagged_playlists(request, tag):
    tag = get_object_or_404(Tag, created_by=request.user, name=tag)
    playlists = request.user.playlists.all().filter(Q(is_in_db=True) & Q(tags__name=tag.name)).order_by('-updated_at')

    return render(request, 'all_playlists_with_tag.html', {'playlists': playlists, 'tag': tag})


@login_required
def library(request, library_type):
    """
    Possible playlist types for marked_as attribute: (saved in database like this)
    'none', 'watching', 'plan-to-watch'
    """
    library_type = library_type.lower()
    watching = False
    if library_type.lower() == 'home':  # displays cards of all playlist types
        return render(request, 'library.html')
    elif library_type == 'all':
        playlists = request.user.playlists.all().filter(is_in_db=True)
        library_type_display = 'All Playlists'
    elif library_type == 'user-owned':  # YT playlists owned by user
        playlists = request.user.playlists.all().filter(Q(is_user_owned=True) & Q(is_in_db=True))
        library_type_display = 'Your YouTube Playlists'
    elif library_type == 'imported':  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_user_owned=False) & Q(is_in_db=True))
        library_type_display = 'Imported playlists'
    elif library_type == 'favorites':  # YT playlists (public) owned by others
        playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
        library_type_display = 'Favorites'
    elif library_type.lower() in ['watching', 'plan-to-watch']:
        playlists = request.user.playlists.filter(Q(marked_as=library_type.lower()) & Q(is_in_db=True))
        library_type_display = library_type.lower().replace('-', ' ')
        if library_type.lower() == 'watching':
            watching = True
    elif library_type.lower() == 'yt-mix':
        playlists = request.user.playlists.all().filter(Q(is_yt_mix=True) & Q(is_in_db=True))
        library_type_display = 'Your YouTube Mixes'
    elif library_type.lower() == 'unavailable-videos':
        videos = request.user.videos.all().filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=True))
        return render(request, 'unavailable_videos.html', {'videos': videos})
    elif library_type.lower() == 'random':  # randomize playlist
        if request.method == 'POST':
            playlists_type = bleach.clean(request.POST['playlistsType'])
            if playlists_type == 'All':
                playlists = request.user.playlists.all().filter(is_in_db=True)
            elif playlists_type == 'Favorites':
                playlists = request.user.playlists.all().filter(Q(is_favorite=True) & Q(is_in_db=True))
            elif playlists_type == 'Watching':
                playlists = request.user.playlists.filter(Q(marked_as='watching') & Q(is_in_db=True))
            elif playlists_type == 'Plan to Watch':
                playlists = request.user.playlists.filter(Q(marked_as='plan-to-watch') & Q(is_in_db=True))
            else:
                return redirect('/library/home')

            if not playlists.exists():
                messages.info(request, f'No playlists in {playlists_type}')
                return redirect('/library/home')
            random_playlist = random.choice(playlists)
            return redirect(f'/playlist/{random_playlist.playlist_id}')
        return render(request, 'library.html')
    else:
        return redirect('home')

    return render(
        request, 'all_playlists.html', {
            'playlists': playlists.order_by('-updated_at'),
            'library_type': library_type,
            'library_type_display': library_type_display,
            'watching': watching
        }
    )


@login_required
def order_playlist_by(request, playlist_id, order_by):
    playlist = request.user.playlists.get(Q(playlist_id=playlist_id) & Q(is_in_db=True))

    display_text = 'Nothing in this playlist! Add something!'  # what to display when requested order/filter has no videws
    videos_details = ''

    if order_by == 'all':
        playlist_items = playlist.playlist_items.select_related('video').order_by('video_position')
    elif order_by == 'favorites':
        playlist_items = playlist.playlist_items.select_related('video').filter(video__is_favorite=True
                                                                                ).order_by('video_position')
        videos_details = 'Sorted by Favorites'
        display_text = 'No favorites yet!'
    elif order_by == 'popularity':
        videos_details = 'Sorted by Popularity'
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__like_count')
    elif order_by == 'date-published':
        videos_details = 'Sorted by Date Published'
        playlist_items = playlist.playlist_items.select_related('video').order_by('published_at')
    elif order_by == 'views':
        videos_details = 'Sorted by View Count'
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__view_count')
    elif order_by == 'has-cc':
        videos_details = 'Filtered by Has CC'
        playlist_items = playlist.playlist_items.select_related('video').filter(video__has_cc=True
                                                                                ).order_by('video_position')
        display_text = 'No videos in this playlist have CC :('
    elif order_by == 'duration':
        videos_details = 'Sorted by Video Duration'
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__duration_in_seconds')
    elif order_by == 'new-updates':
        playlist_items = []
        videos_details = 'Sorted by New Updates'
        display_text = 'No new updates! Note that deleted videos will not show up here.'
        if playlist.has_new_updates:
            recently_updated_videos = playlist.playlist_items.select_related('video').filter(
                video__video_details_modified=True
            )

            for playlist_item in recently_updated_videos:
                if playlist_item.video.video_details_modified_at + datetime.timedelta(hours=12
                                                                                      ) < datetime.datetime.now(
                                                                                          pytz.utc
                                                                                      ):  # expired
                    playlist_item.video.video_details_modified = False
                    playlist_item.video.save(update_fields=['video_details_modified'])

            if not recently_updated_videos.exists():
                playlist.has_new_updates = False
                playlist.save(update_fields=['has_new_updates'])
            else:
                playlist_items = recently_updated_videos.order_by('video_position')
    elif order_by == 'unavailable-videos':
        playlist_items = playlist.playlist_items.select_related('video').filter(
            Q(video__is_unavailable_on_yt=False) & Q(video__was_deleted_on_yt=True)
        )
        videos_details = 'Sorted by Unavailable Videos'
        display_text = 'None of the videos in this playlist have gone unavailable... yet.'
    elif order_by == 'channel':
        channel_name = bleach.clean(request.GET['channel-name'])
        playlist_items = playlist.playlist_items.select_related('video').filter(video__channel_name=channel_name
                                                                                ).order_by('video_position')
        videos_details = f'Sorted by Channel "{channel_name}"'
    else:
        return HttpResponse('Something went wrong :(')

    return HttpResponse(
        loader.get_template('intercooler/playlist_items.html').render({
            'playlist': playlist,
            'playlist_items': playlist_items,
            'videos_details': videos_details,
            'display_text': display_text,
            'order_by': order_by
        })
    )


@login_required
def order_playlists_by(request, library_type, order_by):
    watching = False

    if library_type == '' or library_type.lower() == 'all':
        playlists = request.user.playlists.all()
    elif library_type.lower() == 'favorites':
        playlists = request.user.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
    elif library_type.lower() in ['watching', 'plan-to-watch']:
        playlists = request.user.playlists.filter(Q(marked_as=library_type.lower()) & Q(is_in_db=True))
        if library_type.lower() == 'watching':
            watching = True
    elif library_type.lower() == 'imported':
        playlists = request.user.playlists.filter(Q(is_user_owned=False) & Q(is_in_db=True))
    elif library_type.lower() == 'user-owned':
        playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    else:
        return HttpResponse('Not found.')

    if order_by == 'recently-accessed':
        playlists = playlists.order_by('-updated_at')
    elif order_by == 'playlist-duration-in-seconds':
        playlists = playlists.order_by('-playlist_duration_in_seconds')
    elif order_by == 'video-count':
        playlists = playlists.order_by('-video_count')

    return HttpResponse(
        loader.get_template('intercooler/playlists.html').render({
            'playlists': playlists,
            'watching': watching
        })
    )


@login_required
def mark_playlist_as(request, playlist_id, mark_as):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    marked_as_response = '<span></span><meta http-equiv="refresh" content="0" />'

    if mark_as in ['watching', 'on-hold', 'plan-to-watch']:
        playlist.marked_as = mark_as
        playlist.save()
        icon = ''
        if mark_as == 'watching':
            playlist.last_watched = datetime.datetime.now(pytz.utc)
            playlist.save(update_fields=['last_watched'])
            icon = '<i class="fas fa-fire-alt me-2"></i>'
        elif mark_as == 'plan-to-watch':
            icon = '<i class="fas fa-flag me-2"></i>'
        marked_as_response = f'<span class="badge bg-success text-white" >{icon}{mark_as}</span> <meta http-equiv="refresh" content="0" />'
    elif mark_as == 'none':
        playlist.marked_as = mark_as
        playlist.save()
    elif mark_as == 'favorite':
        if playlist.is_favorite:
            playlist.is_favorite = False
            playlist.save()
            return HttpResponse('<i class="far fa-star"></i>')
        else:
            playlist.is_favorite = True
            playlist.save()
            return HttpResponse('<i class="fas fa-star" style="color: #fafa06"></i>')
    else:
        return redirect('home')

    return HttpResponse(marked_as_response)


@login_required
def playlists_home(request):
    return render(request, 'library.html')


@login_required
@require_POST
def playlist_delete_videos(request, playlist_id, command):
    all_ = False
    num_vids = 0
    playlist_item_ids = []
    if 'all' in request.POST:
        if request.POST['all'] == 'yes':
            all_ = True
            num_vids = request.user.playlists.get(playlist_id=playlist_id).playlist_items.all().count()
            if command == 'start':
                playlist_item_ids = [
                    playlist_item.playlist_item_id
                    for playlist_item in request.user.playlists.get(playlist_id=playlist_id).playlist_items.all()
                ]
    else:
        playlist_item_ids = [bleach.clean(item_id) for item_id in request.POST.getlist('video-id', default=[])]
        num_vids = len(playlist_item_ids)

    extra_text = ' '
    if num_vids == 0:
        return HttpResponse("""
            <h5>Select some videos first!</h5><hr>
        """)

    if 'confirm before deleting' in request.POST:
        if request.POST['confirm before deleting'] == 'False':
            command = 'confirmed'

    if command == 'confirm':
        if all_ or num_vids == request.user.playlists.get(playlist_id=playlist_id).playlist_items.all().count():
            hx_vals = """hx-vals='{"all": "yes"}'"""
            delete_text = 'ALL VIDEOS'
            extra_text = ' This will not delete the playlist itself, will only make the playlist empty. '
        else:
            hx_vals = ''
            delete_text = f'{num_vids} videos'

        if playlist_id == 'LL':
            extra_text += "Since you're deleting from your Liked Videos playlist, the selected videos will also be unliked from YouTube. "

        url = f'/playlist/{playlist_id}/delete-videos/confirmed'

        return HttpResponse(
            f"""
                <div hx-ext='class-tools'>
                <div classes='add visually-hidden:30s'>
                    <h5>
                    Are you sure you want to delete {delete_text} from your YouTube playlist?{extra_text}This cannot be undone.</h5>
                    <button hx-post='{url}' hx-include='[id='video-checkboxes']' {hx_vals} hx-target='#delete-videos-confirm-box' type='button' 
                    class='btn btn-outline-danger btn-sm'>Confirm</button>
                    <hr>
                </div>
                </div>
            """
        )
    elif command == 'confirmed':
        if all_:
            hx_vals = """hx-vals='{"all": "yes"}'"""
        else:
            hx_vals = ''
        url = f'/playlist/{playlist_id}/delete-videos/start'
        return HttpResponse(
            f"""
            <div class='spinner-border text-light' role='status' 
            hx-post='{url}' {hx_vals} hx-trigger='load' hx-include='[id='video-checkboxes']' 
            hx-target='#delete-videos-confirm-box'></div><hr>
            """
        )
    elif command == 'start':
        logger.info('Deleting', len(playlist_item_ids), 'videos')
        Playlist.objects.deletePlaylistItems(request.user, playlist_id, playlist_item_ids)
        if all_:
            help_text = 'Finished emptying this playlist.'
        else:
            help_text = 'Done deleting selected videos from your playlist on YouTube.'

        messages.success(request, help_text)
        return HttpResponse(
            """
            <h5>
                Done! Refreshing...
                <script>
            window.location.reload();
            </script>
            </h5>
            <hr>
            """
        )


@login_required
@require_POST
def delete_specific_videos(request, playlist_id, command):
    Playlist.objects.deleteSpecificPlaylistItems(request.user, playlist_id, command)

    help_text = 'Error.'
    if command == 'unavailable':
        help_text = 'Deleted all unavailable videos.'
    elif command == 'duplicate':
        help_text = 'Deleted all duplicate videos.'

    messages.success(request, help_text)

    return HttpResponse(
        """
        <h5>
            Done. Refreshing...
            <script>
            window.location.reload();
            </script>
        </h5>
        <hr>
        """
    )


# MANAGE VIDEOS
@login_required
def mark_video_favortie(request, video_id):
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
def mark_video_planned_to_watch(request, video_id):
    video = request.user.videos.get(video_id=video_id)

    if video.is_planned_to_watch:
        video.is_planned_to_watch = False
        video.save(update_fields=['is_planned_to_watch'])
        return HttpResponse('<i class="far fa-clock"></i>')
    else:
        video.is_planned_to_watch = True
        video.save(update_fields=['is_planned_to_watch'])
        return HttpResponse('<i class="fas fa-clock" style="color: #000000"></i>')


@login_required
def mark_video_watched(request, playlist_id, video_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    video = playlist.videos.get(video_id=video_id)

    if video.is_marked_as_watched:
        video.is_marked_as_watched = False
        video.save(update_fields=['is_marked_as_watched'])

        return HttpResponse(
            f'<i class="far fa-check-circle" hx-get="/playlist/{playlist_id}/get-watch-message" '
            f'hx-trigger="load" hx-target="#playlist-watch-message"></i>'
        )
    else:
        video.is_marked_as_watched = True
        video.save(update_fields=['is_marked_as_watched'])
        playlist.last_watched = datetime.datetime.now(pytz.utc)
        playlist.save(update_fields=['last_watched'])

        return HttpResponse(
            f'<i class="fas fa-check-circle" hx-get="/playlist/{playlist_id}/get-watch-message" '
            f'hx-trigger="load" hx-target="#playlist-watch-message"></i>'
        )


###########


@login_required
def load_more_videos(request, playlist_id, order_by, page):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_items = None
    if order_by == 'all':
        playlist_items = playlist.playlist_items.select_related('video').order_by('video_position')
        logger.debug(f'loading page 1: {playlist_items.count()} videos')
    elif order_by == 'favorites':
        playlist_items = playlist.playlist_items.select_related('video').filter(video__is_favorite=True
                                                                                ).order_by('video_position')
    elif order_by == 'popularity':
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__like_count')
    elif order_by == 'date-published':
        playlist_items = playlist.playlist_items.select_related('video').order_by('published_at')
    elif order_by == 'views':
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__view_count')
    elif order_by == 'has-cc':
        playlist_items = playlist.playlist_items.select_related('video').filter(video__has_cc=True
                                                                                ).order_by('video_position')
    elif order_by == 'duration':
        playlist_items = playlist.playlist_items.select_related('video').order_by('-video__duration_in_seconds')
    elif order_by == 'new-updates':
        playlist_items = []
        if playlist.has_new_updates:
            recently_updated_videos = playlist.playlist_items.select_related('video').filter(
                video__video_details_modified=True
            )

            for playlist_item in recently_updated_videos:
                if playlist_item.video.video_details_modified_at + datetime.timedelta(hours=12
                                                                                      ) < datetime.datetime.now(
                                                                                          pytz.utc
                                                                                      ):  # expired
                    playlist_item.video.video_details_modified = False
                    playlist_item.video.save()

            if not recently_updated_videos.exists():
                playlist.has_new_updates = False
                playlist.save()
            else:
                playlist_items = recently_updated_videos.order_by('video_position')
    elif order_by == 'unavailable-videos':
        playlist_items = playlist.playlist_items.select_related('video').filter(
            Q(video__is_unavailable_on_yt=True) & Q(video__was_deleted_on_yt=True)
        )
    elif order_by == 'channel':
        channel_name = bleach.clean(request.GET['channel-name'])
        playlist_items = playlist.playlist_items.select_related('video').filter(video__channel_name=channel_name
                                                                                ).order_by('video_position')

    if request.user.profile.hide_unavailable_videos:
        playlist_items.exclude(Q(video__is_unavailable_on_yt=True) & Q(video__was_deleted_on_yt=False))

    return HttpResponse(
        loader.get_template('intercooler/playlist_items.html').render({
            'playlist': playlist,
            'playlist_items': playlist_items[50 * page:],  # only send 50 results per page
            'page': page + 1,
            'order_by': order_by
        })
    )


@login_required
@require_POST
def update_playlist_settings(request, playlist_id):
    message_type = 'success'
    message_content = 'Saved!'

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if 'user_label' in request.POST:
        playlist.user_label = bleach.clean(request.POST['user_label'])

    if 'pl-auto-update' in request.POST:
        playlist.auto_check_for_updates = True
    else:
        playlist.auto_check_for_updates = False

    playlist.save(update_fields=['auto_check_for_updates', 'user_label'])

    try:
        valid_title = bleach.clean(request.POST['playlistTitle'])
        valid_description = bleach.clean(request.POST['playlistDesc'])
        details = {
            'title': valid_title,
            'description': valid_description,
            'privacyStatus': True if request.POST['playlistPrivacy'] == 'Private' else False
        }

        status = Playlist.objects.updatePlaylistDetails(request.user, playlist_id, details)
        if status == -1:
            message_type = 'danger'
            message_content = 'Could not save :('
    except Exception:
        pass

    return HttpResponse(
        loader.get_template('intercooler/messages.html').render({
            'message_type': message_type,
            'message_content': message_content
        })
    )


@login_required
def update_playlist(request, playlist_id, command):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if command == 'checkforupdates':
        logger.debug('Checking if playlist changed...')
        result = Playlist.objects.checkIfPlaylistChangedOnYT(request.user, playlist_id)

        if result[0] == 1:  # full scan was done (full scan is done for a playlist if a week has passed)
            deleted_videos, unavailable_videos, added_videos = result[1:]

            logger.debug('CHANGES', deleted_videos, unavailable_videos, added_videos)

            # playlist_changed_text = ['The following modifications happened to this playlist on YouTube:']
            if deleted_videos != 0 or unavailable_videos != 0 or added_videos != 0:
                pass
                # if added_videos > 0:
                #    playlist_changed_text.append(f'{added_videos} new video(s) were added')
                # if deleted_videos > 0:
                #    playlist_changed_text.append(f'{deleted_videos} video(s) were deleted')
                # if unavailable_videos > 0:
                #    playlist_changed_text.append(f'{unavailable_videos} video(s) went private/unavailable')

                # playlist.playlist_changed_text = '\n'.join(playlist_changed_text)
                # playlist.has_playlist_changed = True
                # playlist.save()
            else:  # no updates found
                return HttpResponse(
                    """
                <div hx-ext='class-tools'>

                    <div id='checkforupdates' class='sticky-top' style='top: 0.5em;'>                    
                        <div class='alert alert-success alert-dismissible fade show' classes='add visually-hidden:1s' role='alert'>
                            Playlist upto date!
                        </div>
                    </div>
                </div>
                """
                )
        elif result[0] == -1:  # playlist changed
            logger.debug('Playlist was deleted from YouTube')
            playlist.videos.all().delete()
            playlist.delete()
            return HttpResponse(
                """
                        <div id='checkforupdates' class='sticky-top' style='top: 0.5em;'>
                            <div class='alert alert-danger alert-dismissible fade show sticky-top visually-hidden' role='alert' style='top: 0.5em;'>
                                The playlist owner deleted this playlist on YouTube. It will be deleted for you as well :(
                                <meta http-equiv='refresh' content='1' />
                            </div>
                        </div>
                        """
            )
        else:  # no updates found
            return HttpResponse(
                """
            <div id='checkforupdates' class='sticky-top' style='top: 0.5em;'>
                <div hx-ext='class-tools'>
                <div classes='add visually-hidden:2s' class='alert alert-success alert-dismissible fade show sticky-top visually-hidden' 
                role='alert' style='top: 0.5em;'>
                    No new updates!
                </div>
                </div>
            </div>
            """
            )

        return HttpResponse(
            f"""
        <div hx-get='/playlist/{playlist_id}/update/auto' hx-trigger='load' hx-target='this' class='sticky-top' style='top: 0.5em;'>            
            <div class='alert alert-success alert-dismissible fade show' role='alert'>
            <div class='d-flex justify-content-center' id='loading-sign'>
                <img src='/static/svg-loaders/circles.svg' width='40' height='40'>
                <h5 class='mt-2 ms-2'>Changes detected on YouTube, updating playlist '{playlist.name}'...</h5>
            </div>
            </div>
        </div>
        """
        )

    if command == 'manual':
        logger.debug('MANUAL')
        return HttpResponse(
            f"""<div hx-get='/playlist/{playlist_id}/update/auto' hx-trigger='load' hx-swap='outerHTML'>
                    <div class='d-flex justify-content-center mt-4 mb-3' id='loading-sign'>
                        <img src='/static/svg-loaders/circles.svg' width='40' height='40' 
                        style='filter: invert(0%) sepia(18%) saturate(7468%) hue-rotate(241deg) brightness(84%) contrast(101%);'>
                        <h5 class='mt-2 ms-2'>Refreshing playlist '{playlist.name}', please wait!</h5>
                    </div>
                </div>"""
        )

    logger.debug('Attempting to update playlist')
    status, deleted_playlist_item_ids, unavailable_videos, added_videos = Playlist.objects.updatePlaylist(
        request.user, playlist_id
    )

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if status == -1:
        playlist_name = playlist.name
        playlist.delete()
        return HttpResponse(
            f"""
                <div class='d-flex justify-content-center mt-4 mb-3' id='loading-sign'>
                    <h5 class='mt-2 ms-2'>Looks like the playlist '{playlist_name}' was deleted on YouTube. 
                    It has been removed from UnTube as well.</h5>
                </div>
            """
        )

    logger.debug('Updated playlist')
    playlist_changed_text = []

    if len(added_videos) != 0:
        playlist_changed_text.append(f'{len(added_videos)} added')
        for video in added_videos:
            playlist_changed_text.append(f'--> {video.name}')

        # if len(added_videos) > 3:
        #    playlist_changed_text.append(f'+ {len(added_videos) - 3} more')

    if len(unavailable_videos) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f'{len(unavailable_videos)} went unavailable')
        else:
            playlist_changed_text.append(f'\n{len(unavailable_videos)} went unavailable')
        for video in unavailable_videos:
            playlist_changed_text.append(f'--> {video.name}')
    if len(deleted_playlist_item_ids) != 0:
        if len(playlist_changed_text) == 0:
            playlist_changed_text.append(f'{len(deleted_playlist_item_ids)} deleted')
        else:
            playlist_changed_text.append(f'\n{len(deleted_playlist_item_ids)} deleted')

        for playlist_item_id in deleted_playlist_item_ids:
            playlist_item = playlist.playlist_items.select_related('video').get(playlist_item_id=playlist_item_id)
            video = playlist_item.video
            playlist_changed_text.append(f'--> {playlist_item.video.name}')
            playlist_item.delete()
            if playlist_id == 'LL':
                video.liked = False
                video.save(update_fields=['liked'])
            if not playlist.playlist_items.filter(video__video_id=video.video_id).exists():
                playlist.videos.remove(video)

    if len(playlist_changed_text) == 0:
        playlist_changed_text = [
            'Updated playlist and video details to their latest. No new changes found in terms of modifications made to this playlist!'
        ]

    # return HttpResponse
    return HttpResponse(
        loader.get_template('intercooler/playlist_updates.html').render({
            'playlist_changed_text': '\n'.join(playlist_changed_text),
            'playlist_id': playlist_id
        })
    )


@login_required
def view_playlist_settings(request, playlist_id):
    try:
        playlist = request.user.playlists.get(playlist_id=playlist_id)
    except Playlist.DoesNotExist:
        messages.error(request, 'No such playlist found!')
        return redirect('home')

    return render(request, 'view_playlist_settings.html', {'playlist': playlist})


@login_required
def get_playlist_tags(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    playlist_tags = playlist.tags.all()

    return HttpResponse(
        loader.get_template('intercooler/playlist_tags.html').render({
            'playlist_id': playlist_id,
            'playlist_tags': playlist_tags
        })
    )


@login_required
def get_unused_playlist_tags(request, playlist_id):
    # playlist = request.user.playlists.get(playlist_id=playlist_id)

    user_created_tags = Tag.objects.filter(created_by=request.user)
    # playlist_tags = playlist.tags.all()

    # unused_tags = user_created_tags.difference(playlist_tags)

    return HttpResponse(
        loader.get_template('intercooler/playlist_tags_unused.html').render({'unused_tags': user_created_tags})
    )


@login_required
def get_watch_message(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    return HttpResponse(loader.get_template('intercooler/playlist_watch_message.html').render({'playlist': playlist}))


@login_required
@require_POST
def create_playlist_tag(request, playlist_id):
    tag_name = bleach.clean(request.POST['createTagField'])

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

    return HttpResponse(
        f"""
            Created and Added!
              <span class='visually-hidden' hx-get='/playlist/{playlist_id}/get-tags' hx-trigger='load' hx-target='#playlist-tags'></span>
    """
    )


@login_required
@require_POST
def add_playlist_tag(request, playlist_id):
    tag_name = bleach.clean(request.POST['playlistTag'])

    if tag_name == 'Pick from existing unused tags':
        return HttpResponse('Pick something! >w<')

    try:
        tag = request.user.playlist_tags.get(name__iexact=tag_name)
    except Exception:
        return HttpResponse('Uh-oh, looks like this tag was deleted :(')

    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_tags = playlist.tags.all()
    if not playlist_tags.filter(name__iexact=tag_name).exists():  # tag not on this playlist, so add it
        # add it to playlist
        playlist.tags.add(tag)
    else:
        return HttpResponse('Already Added >w<')

    return HttpResponse(
        f"""
                Added!
                  <span class='visually-hidden' hx-get='/playlist/{playlist_id}/get-tags' hx-trigger='load' hx-target='#playlist-tags'></span>
        """
    )


@login_required
@require_POST
def remove_playlist_tag(request, playlist_id, tag_name):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    playlist_tags = playlist.tags.all()
    if playlist_tags.filter(name__iexact=tag_name).exists():  # tag on this playlist, remove it it
        tag = Tag.objects.filter(Q(created_by=request.user) & Q(name__iexact=tag_name)).first()

        logger.debug('Removed tag', tag_name)
        # remove it from the playlist
        playlist.tags.remove(tag)
    else:
        return HttpResponse('Whoops >w<')

    return HttpResponse('')


@login_required
def delete_playlist(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    if request.GET['confirmed'] == 'no':
        return HttpResponse(
            f"""
            <a href='/playlist/{playlist_id}/delete-playlist?confirmed=yes' hx-indicator='#delete-pl-loader' class='btn btn-danger'>Confirm Delete</a>
            <a href='/playlist/{playlist_id}' class='btn btn-secondary ms-1'>Cancel</a>
        """
        )

    if not playlist.is_user_owned:  # if playlist trying to delete isn't user owned
        video_ids = [video.video_id for video in playlist.videos.all()]
        playlist.delete()
        for video_id in video_ids:
            video = request.user.videos.get(video_id=video_id)
            if video.playlists.all().count() == 0:
                video.delete()

        messages.success(request, 'Successfully deleted playlist from UnTube.')
    else:
        # deletes it from YouTube first then from UnTube
        status = Playlist.objects.deletePlaylistFromYouTube(request.user, playlist_id)
        if status[0] == -1:  # failed to delete playlist from youtube
            # if status[2] == 404:
            #    playlist.delete()
            #    messages.success(request, 'Looks like the playlist was already deleted on YouTube. Removed it from UnTube as well.')
            #    return redirect('home')
            messages.error(request, f'[{status[1]}] Failed to delete playlist from YouTube :(')
            return redirect('view_playlist_settings', playlist_id=playlist_id)

        messages.success(request, 'Successfully deleted playlist from YouTube and removed it from UnTube as well.')

    return redirect('home')


@login_required
def reset_watched(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)

    for video in playlist.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=False)):
        video.is_marked_as_watched = False
        video.save(update_fields=['is_marked_as_watched'])

    # messages.success(request, 'Successfully marked all videos unwatched.')

    return redirect(f'/playlist/{playlist.playlist_id}')


@login_required
@require_POST
def playlist_move_copy_videos(request, playlist_id, action):
    playlist_ids = [bleach.clean(pl_id) for pl_id in request.POST.getlist('playlist-ids', default=[])]
    playlist_item_ids = [bleach.clean(item_id) for item_id in request.POST.getlist('video-id', default=[])]

    # basic processing
    if not playlist_ids and not playlist_item_ids:
        return HttpResponse("""<span class='text-warning'>Mistakes happen. Try again >w<</span>""")
    elif not playlist_ids:
        return HttpResponse("""<span class='text-danger'>First select some playlists to {action} to!</span>""")
    elif not playlist_item_ids:
        return HttpResponse(f"""<span class='text-danger'>First select some videos to {action}!</span>""")

    success_message = f"""
                <div hx-ext='class-tools'>
                <span classes='add visually-hidden:5s' class='text-success'>Successfully {'moved' if action == 'move' else 'copied'} 
                {len(playlist_item_ids)} video(s) to {len(playlist_ids)} other playlist(s)!
                Go visit those playlist(s)!</span>
                </div>
                """
    if action == 'move':
        result = Playlist.objects.moveCopyVideosFromPlaylist(
            request.user,
            from_playlist_id=playlist_id,
            to_playlist_ids=playlist_ids,
            playlist_item_ids=playlist_item_ids,
            action='move'
        )
        if result['status'] == -1:
            if result['status'] == 404:
                return HttpResponse(
                    '<span class="text-danger">You cannot copy/move unavailable videos! De-select them and try again.</span>'
                )
            return HttpResponse('Error moving!')
    else:  # copy
        status = Playlist.objects.moveCopyVideosFromPlaylist(
            request.user,
            from_playlist_id=playlist_id,
            to_playlist_ids=playlist_ids,
            playlist_item_ids=playlist_item_ids
        )
        if status[0] == -1:
            if status[1] == 404:
                return HttpResponse(
                    '<span class="text-danger">You cannot copy/move unavailable videos! De-select them and try again.</span>'
                )
            return HttpResponse('Error copying!')

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

    return HttpResponse(
        f"""
        <h5 class='text-warning'>Playlist completion times:</h5>
        <h6>At 1.25x speed: {getHumanizedTimeString(playlist_duration / 1.25)}</h6>
        <h6>At 1.5x speed: {getHumanizedTimeString(playlist_duration / 1.5)}</h6>
        <h6>At 1.75x speed: {getHumanizedTimeString(playlist_duration / 1.75)}</h6>
        <h6>At 2x speed: {getHumanizedTimeString(playlist_duration / 2)}</h6>
    """
    )


@login_required
def video_completion_times(request, video_id):
    video_duration = request.user.videos.get(video_id=video_id).duration_in_seconds

    return HttpResponse(
        f"""
        <h5 class='text-warning'>Video completion times:</h5>
        <h6>At 1.25x speed: {getHumanizedTimeString(video_duration / 1.25)}</h6>
        <h6>At 1.5x speed: {getHumanizedTimeString(video_duration / 1.5)}</h6>
        <h6>At 1.75x speed: {getHumanizedTimeString(video_duration / 1.75)}</h6>
        <h6>At 2x speed: {getHumanizedTimeString(video_duration / 2)}</h6>
    """
    )


@login_required
@require_POST
def add_video_user_label(request, video_id):
    video = request.user.videos.get(video_id=video_id)
    if 'user_label' in request.POST:
        video.user_label = bleach.clean(request.POST['user_label'])
        video.save(update_fields=['user_label'])
    return redirect('video', video_id=video_id)


@login_required
@require_POST
def edit_tag(request, tag):
    tag = request.user.playlist_tags.get(name=tag)

    if 'tag_name' in request.POST:
        tag.name = bleach.clean(request.POST['tag_name'])
        tag.save(update_fields=['name'])
        messages.success(request, "Successfully updated the tag's name!")

    return redirect('tagged_playlists', tag=tag.name)


@login_required
@require_POST
def delete_tag(request, tag):
    tag = request.user.playlist_tags.get(name__iexact=tag)
    tag.delete()
    messages.success(request, f'Successfully deleted the tag "{tag.name}"')
    return redirect('/library/home')


@login_required
@require_POST
def add_playlist_user_label(request, playlist_id):
    playlist = request.user.playlists.get(playlist_id=playlist_id)
    if 'user_label' in request.POST:
        playlist.user_label = bleach.clean(request.POST['user_label'].strip())
        playlist.save(update_fields=['user_label'])
    return redirect('playlist', playlist_id=playlist_id)


@login_required
@require_POST
def playlist_add_new_videos(request, playlist_id):
    textarea_input = bleach.clean(request.POST['add-videos-textarea'])
    video_links = textarea_input.strip().split('\n')[:25]

    video_ids = []
    for video_link in video_links:
        if video_link.strip() == '':
            continue
        video_id = getVideoId(video_link)
        if video_id is None or video_id in video_ids:
            continue
        video_ids.append(video_id)
    result = Playlist.objects.addVideosToPlaylist(request.user, playlist_id, video_ids)
    added = result['num_added']
    max_limit_reached = result['playlistContainsMaximumNumberOfVideos']
    if max_limit_reached and added == 0:
        message = 'Could not add any new videos to this playlist as the max limit has been reached :('
        messages.error(request, message)
    elif max_limit_reached and added != 0:
        message = f'Only added the first {added} video link(s) to this playlist as the max playlist limit has been reached :('
        messages.warning(request, message)
    # else:
    #    message = f'Successfully added {added} videos to this playlist.'
    #    messages.success(request, message)

    return HttpResponse(
        """
        Done! Refreshing...
            <script>
            window.location.reload();
            </script>
    """
    )


@login_required
@require_POST
def playlist_create_new_playlist(request, playlist_id):
    playlist_name = bleach.clean(request.POST['playlist-name'].strip())
    playlist_description = bleach.clean(request.POST['playlist-description'])
    if playlist_name == '':
        return HttpResponse('Enter a playlist name first!')

    unclean_playlist_item_ids = request.POST.getlist('video-id', default=[])
    clean_playlist_item_ids = [bleach.clean(playlist_item_id) for playlist_item_id in unclean_playlist_item_ids]
    playlist_items = request.user.playlists.get(playlist_id=playlist_id
                                                ).playlist_items.filter(playlist_item_id__in=clean_playlist_item_ids)

    if not playlist_items.exists():
        return HttpResponse('Select some videos first!')
    else:
        result = Playlist.objects.createNewPlaylist(request.user, playlist_name, playlist_description)
        if result['status'] == 0:  # playlist created on youtube
            new_playlist_id = result['playlist_id']
        elif result['status'] == -1:
            return HttpResponse('Error creating playlist!')
        elif result['status'] == 400:
            return HttpResponse('Max playlists limit reached!')

    video_ids = []
    for playlist_item in playlist_items:
        video_ids.append(playlist_item.video.video_id)

    result = Playlist.objects.addVideosToPlaylist(request.user, new_playlist_id, video_ids)

    added = result['num_added']
    max_limit_reached = result['playlistContainsMaximumNumberOfVideos']
    if max_limit_reached:
        message = f'Only added the first {added} video link(s) to the new playlist as the max playlist limit has been reached :('
    else:
        message = f"""Successfully created '{playlist_name}' and added {added} videos to it. Visit the 
        <a href='/home/' target='_blank' style='text-decoration: none; color: white' class='ms-1 me-1'>dashboard</a> to import it into UnTube."""

    return HttpResponse(message)
