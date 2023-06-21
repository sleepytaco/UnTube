import bleach
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)


@login_required
def search(request):
    if request.method == 'GET':
        logger.debug(request.GET)
        if 'mode' in request.GET:
            mode = bleach.clean(request.GET['mode'])
        else:
            mode = 'playlists'

        if 'type' in request.GET:
            item_type = bleach.clean(request.GET['type'])
        else:
            item_type = 'all'

        if 'query' in request.GET:
            query = bleach.clean(request.GET['query'])
        else:
            query = ''

        if 'tag' in request.GET:
            pl_tag = bleach.clean(request.GET['tag'])
        else:
            pl_tag = ''

        if 'channel' in request.GET:
            vid_channel_name = bleach.clean(request.GET['channel'])
        else:
            vid_channel_name = ''

        return render(
            request, 'search_untube_page.html', {
                'playlists': request.user.playlists.all(),
                'mode': mode,
                'item_type': item_type,
                'query': query,
                'pl_tag': pl_tag,
                'vid_channel_name': vid_channel_name
            }
        )
    else:
        return redirect('home')


@login_required
@require_POST
def search_UnTube(request):
    search_query = bleach.clean(request.POST['search'])

    if request.POST['search-settings'] == 'playlists':
        playlist_type = bleach.clean(request.POST['playlistsType'])

        all_playlists = request.user.playlists.filter(is_in_db=True)
        if playlist_type == 'Favorite':
            all_playlists = all_playlists.filter(is_favorite=True)
        elif playlist_type == 'Watching':
            all_playlists = all_playlists.filter(marked_as='watching')
        elif playlist_type == 'Plan to Watch':
            all_playlists = all_playlists.filter(marked_as='plan-to-watch')
        elif playlist_type == 'Owned':
            all_playlists = all_playlists.filter(is_user_owned=True)
        elif playlist_type == 'Imported':
            all_playlists = all_playlists.filter(is_user_owned=False)
        elif playlist_type == 'Mix':
            all_playlists = all_playlists.filter(is_yt_mix=True)

        if 'playlist-tags' in request.POST:
            tags = [bleach.clean(t) for t in request.POST.getlist('playlist-tags')]
            for tag in tags:
                all_playlists = all_playlists.filter(tags__name=tag)

        playlists = all_playlists.filter(Q(name__istartswith=search_query) | Q(user_label__istartswith=search_query))

        if not playlists.exists():
            playlists = all_playlists.filter(Q(name__icontains=search_query) | Q(user_label__icontains=search_query))

        if search_query.strip() == '':
            playlists = all_playlists

        order_by = bleach.clean(request.POST['sortPlaylistsBy'])
        if order_by == 'recently-accessed':
            playlists = playlists.order_by('-updated_at')
        elif order_by == 'playlist-duration-in-seconds':
            playlists = playlists.order_by('-playlist_duration_in_seconds')
        elif order_by == 'video-count':
            playlists = playlists.order_by('-video_count')

        return HttpResponse(
            loader.get_template('intercooler/search_untube_results.html').render({
                'playlists': playlists,
                'view_mode': 'playlists',
                'search_query': search_query,
                'playlist_type': playlist_type
            })
        )
    else:
        videos_type = bleach.clean(request.POST['videosType'])

        all_videos = request.user.videos.filter(is_unavailable_on_yt=False)
        if videos_type == 'Liked':
            all_videos = all_videos.filter(liked=True)
        elif videos_type == 'Favorite':
            all_videos = all_videos.filter(is_favorite=True)
        elif videos_type == 'Watched':
            all_videos = all_videos.filter(is_marked_as_watched=True)
        elif videos_type == 'Planned to Watch':
            all_videos = all_videos.filter(is_planned_to_watch=True)
        elif videos_type == 'Unavailable':
            all_videos = all_videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=True))

        if 'channel-names' in request.POST:
            channels = [bleach.clean(name) for name in request.POST.getlist('channel-names')]
            all_videos = all_videos.filter(channel_name__in=channels)

        videos = all_videos.filter(Q(name__istartswith=search_query) | Q(user_label__istartswith=search_query))

        if not videos.exists():
            videos = all_videos.filter(Q(name__icontains=search_query) | Q(user_label__icontains=search_query))

        if search_query.strip() == '':
            videos = all_videos

        order_by = bleach.clean(request.POST['sortVideosBy'])
        if order_by == 'recently-accessed':
            videos = videos.order_by('-updated_at')
        elif order_by == 'video-duration-in-seconds':
            videos = videos.order_by('-duration_in_seconds')
        elif order_by == 'most-liked':
            videos = videos.order_by('-like_count')
        elif order_by == 'most-views':
            videos = videos.order_by('-view_count')
        elif order_by == 'date-uploaded':
            videos = videos.order_by('-published_at')

        if 'has-cc' in request.POST:
            videos = videos.filter(has_cc=True)

        if 'playlist-ids' in request.POST:
            playlist_ids = [bleach.clean(pl_id) for pl_id in request.POST.getlist('playlist-ids')]
            videos = videos.filter(playlists__playlist_id__in=playlist_ids)

        return HttpResponse(
            loader.get_template('intercooler/search_untube_results.html').render({
                'videos': videos,
                'view_mode': 'videos',
                'videos_type': videos_type,
                'search_query': search_query
            })
        )


@login_required
@require_POST
def search_library(request, library_type):
    # print_(request.POST)  # prints <QueryDict: {'search': ['aa']}>

    search_query = bleach.clean(request.POST['search'])
    watching = False

    playlists = None
    if library_type == 'all':
        try:
            playlists = request.user.playlists.all().filter(
                Q(is_in_db=True)
            ).filter(Q(name__startswith=search_query) | Q(user_label__startswith=search_query))
        except Exception:
            playlists = request.user.playlists.all().filter(is_in_db=True)
    elif library_type == 'user-owned':  # YT playlists owned by user
        try:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    elif library_type == 'imported':  # YT playlists (public) owned by others
        try:
            playlists = request.user.playlists.filter(Q(is_user_owned=False) & Q(is_in_db=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) & Q(is_in_db=True))
    elif library_type == 'favorites':  # YT playlists (public) owned by others
        try:
            playlists = request.user.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            playlists = request.user.playlists.filter(Q(is_favorite=True) & Q(is_in_db=True))
    elif library_type in ['watching', 'plan-to-watch']:
        try:
            playlists = request.user.playlists.filter(Q(marked_as=library_type) & Q(is_in_db=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            playlists = request.user.playlists.all().filter(Q(marked_as=library_type) & Q(is_in_db=True))
        if library_type == 'watching':
            watching = True
    elif library_type == 'yt-mix':  # YT playlists owned by user
        try:
            playlists = request.user.playlists.filter(Q(is_yt_mix=True) & Q(is_in_db=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            playlists = request.user.playlists.filter(Q(is_yt_mix=True) & Q(is_in_db=True))
    elif library_type == 'unavailable-videos':
        try:
            videos = request.user.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=True)).filter(
                Q(name__startswith=search_query) | Q(user_label__startswith=search_query)
            )
        except Exception:
            videos = request.user.videos.filter(Q(is_unavailable_on_yt=False) & Q(was_deleted_on_yt=True))
        return HttpResponse(loader.get_template('intercooler/video_cards.html').render({'videos': videos}))

    return HttpResponse(
        loader.get_template('intercooler/playlists.html').render({
            'playlists': playlists.order_by('-updated_at'),
            'show_controls': True,
            'watching': watching
        })
    )


@login_required
@require_POST
def search_tagged_playlists(request, tag):
    search_query = bleach.clean(request.POST['search'])
    try:
        playlists = request.user.playlists.all(
        ).filter(Q(is_in_db=True) &
                 Q(tags__name=tag)).filter(Q(name__startswith=search_query) | Q(user_label__startswith=search_query))
    except Exception:
        playlists = request.user.playlists.all().filter(Q(is_in_db=True) & Q(tags__name=tag)).order_by('-updated_at')

    return HttpResponse(loader.get_template('intercooler/playlists.html').render({'playlists': playlists}))
