import bleach
from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template import loader
from django.views.decorators.http import require_POST
from backend.main.models import Playlist
from .models import Untube
import logging

logger = logging.getLogger(__name__)


# Create your views here.
def index(request):
    if Untube.objects.all().count() == 0:
        untube = Untube.objects.create()
        untube.save()

    if settings.GOOGLE_OAUTH_CLIENT_ID is NotImplemented or settings.GOOGLE_OAUTH_CLIENT_SECRET is NotImplemented:
        messages.error(request, 'Please fill in your Google OAuth credentials in the local/settings.dev.py file')
    else:
        # messages.success(request, 'Thanks for filling in the YouTube API key')

        if not Site.objects.filter(domain=settings.GOOGLE_OAUTH_URI).exists():
            Site.objects.create(domain=settings.GOOGLE_OAUTH_URI, name=settings.GOOGLE_OAUTH_URI)

        if not SocialApp.objects.filter(provider='google').exists():  # create google OAuth app
            print('Creating Google social app...')
            app = SocialApp.objects.create(
                provider='google',
                name='UnTube OAuth',
                client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
                secret=settings.GOOGLE_OAUTH_CLIENT_SECRET
            )
            site_uri = Site.objects.get(domain=settings.GOOGLE_OAUTH_URI)
            app.sites.add(site_uri)

    if not request.session.exists(request.session.session_key):
        request.session.create()
        request.session['liked_untube'] = False

    return render(
        request, 'index.html', {
            'likes': Untube.objects.all().first().page_likes,
            'users_joined': User.objects.all().count()
        }
    )

    # if request.user.is_anonymous:
    #     return render(request, 'index.html', {'likes': Untube.objects.all().first().page_likes,
    #                                           'users_joined': User.objects.all().count()})
    # else:
    #     return redirect('home')


def about(request):
    return render(request, 'about.html')


@login_required
def profile(request):
    user_playlists = request.user.playlists.all()
    watching = user_playlists.filter(marked_as='watching')

    total_num_playlists = user_playlists.count()

    statistics = {'public_x': 0, 'private_x': 0, 'favorites_x': 0, 'watching_x': 0, 'imported_x': 0}

    if total_num_playlists != 0:
        # x means  percentage
        statistics['public_x'
                   ] = round(user_playlists.filter(is_private_on_yt=False).count() / total_num_playlists, 1) * 100
        statistics['private_x'
                   ] = round(user_playlists.filter(is_private_on_yt=True).count() / total_num_playlists, 1) * 100
        statistics['favorites_x'
                   ] = round(user_playlists.filter(is_favorite=True).count() / total_num_playlists, 1) * 100
        statistics['watching_x'
                   ] = round(user_playlists.filter(marked_as='watching').count() / total_num_playlists, 1) * 100
        statistics['imported_x'
                   ] = round(user_playlists.filter(is_user_owned=False).count() / total_num_playlists, 1) * 100

    return render(
        request, 'profile.html', {
            'total_num_playlists': total_num_playlists,
            'statistics': statistics,
            'watching': watching
        }
    )


@login_required
def user_settings(request):
    return render(request, 'settings.html')


@require_POST
def update_settings(request):
    print(request.POST)
    user = request.user
    username_input = bleach.clean(request.POST['username'].strip())
    message_content = 'Saved!'
    # message_type = 'success'
    if username_input != user.username:
        if User.objects.filter(username__exact=username_input).count() != 0:
            # message_type = 'danger'
            message_content = f'Username {username_input} already taken'
            messages.error(request, message_content)
        else:
            user.username = username_input
            # user.save()
            message_content = f'Username updated to {username_input}!'
            messages.success(request, message_content)

    if 'open search in new tab' in request.POST and user.profile.open_search_new_tab is False:
        user.profile.open_search_new_tab = True
    elif 'open search in new tab' not in request.POST and user.profile.open_search_new_tab is True:
        user.profile.open_search_new_tab = False

    if 'enable gradient bg' in request.POST and user.profile.enable_gradient_bg is False:
        user.profile.enable_gradient_bg = True
    elif 'enable gradient bg' not in request.POST and user.profile.enable_gradient_bg is True:
        user.profile.enable_gradient_bg = False

    if 'confirm before deleting' in request.POST and user.profile.confirm_before_deleting is False:
        user.profile.confirm_before_deleting = True
    elif 'confirm before deleting' not in request.POST and user.profile.confirm_before_deleting is True:
        user.profile.confirm_before_deleting = False

    if 'hide videos' in request.POST and user.profile.hide_unavailable_videos is False:
        user.profile.hide_unavailable_videos = True
    elif 'hide videos' not in request.POST and user.profile.hide_unavailable_videos is True:
        user.profile.hide_unavailable_videos = False

    user.save()

    if message_content == 'Saved!':
        messages.success(request, message_content)

    return redirect('settings')


@login_required
def delete_account(request):
    request.user.playlists.all().delete()
    request.user.videos.all().delete()
    request.user.playlist_tags.all().delete()
    request.user.profile.delete()
    request.user.delete()
    request.session.flush()
    messages.success(request, 'Account data deleted successfully.')

    return redirect('index')


@login_required
def log_out(request):
    request.session.flush()  # delete all stored session keys
    logout(request)  # log out authenticated user

    if 'troll' in request.GET:
        print('TROLLED')
        messages.success(request, 'Hee Hee')
    else:
        messages.success(request, 'Successfully logged out. Hope to see you back again!')

    return redirect('/')


@login_required
def cancel_import(request):
    user_profile = request.user.profile
    user_profile.imported_yt_playlists = False
    user_profile.show_import_page = False
    user_profile.save()

    return redirect('home')


@login_required
def import_user_yt_playlists(request):
    request.user.profile.show_import_page = True
    request.user.profile.save(update_fields=['show_import_page'])

    return render(request, 'import_in_progress.html')


@login_required
def start_import(request):
    """
    Initializes only the user's playlist data in the database. Returns the progress bar, which will
    keep calling continue_import
    """
    user_profile = request.user.profile

    result = Playlist.objects.initializePlaylist(request.user)
    if result['status'] == -1:
        print('User has no YT channel')

        return HttpResponse(
            loader.get_template('intercooler/progress_bar.html').render({
                'channel_found': False,
                'error_message': result['error_message']
            })
        )
    elif result['status'] == -2:
        user_profile.import_in_progress = False
        user_profile.imported_yt_playlists = True
        user_profile.show_import_page = True
        user_profile.save()

        print('User has no playlists on YT')

        # if request.user.profile.yt_channel_id == '':
        #     Playlist.objects.getUserYTChannelID(request.user)

        Playlist.objects.initializePlaylist(request.user, 'LL')

        return HttpResponse(
            loader.get_template('intercooler/progress_bar.html').render({
                'total_playlists': 0,
                'playlists_imported': 0,
                'done': True,
                'progress': 100,
                'channel_found': True
            })
        )
    else:
        # if request.user.profile.yt_channel_id == '':
        #     Playlist.objects.getUserYTChannelID(request.user)

        Playlist.objects.initializePlaylist(request.user, 'LL')

        user_profile.import_in_progress = True
        user_profile.save()

        return HttpResponse(
            loader.get_template('intercooler/progress_bar.html').render({
                'total_playlists': result['num_of_playlists'],
                'playlist_name': result['first_playlist_name'],
                'playlists_imported': 0,
                'progress': 0,
                'channel_found': True
            })
        )


@login_required
def continue_import(request):
    if request.user.profile.import_in_progress is False:
        return redirect('home')

    num_of_playlists = request.user.playlists.filter(Q(is_user_owned=True)).exclude(playlist_id='LL').count()
    logger.debug('NUM OF PLAYLISTS', num_of_playlists)
    try:
        remaining_playlists = request.user.playlists.filter(Q(is_user_owned=True) &
                                                            Q(is_in_db=False)).exclude(playlist_id='LL')
        logger.debug(remaining_playlists.count(), 'REMAINING PLAYLISTS')
        playlists_imported = num_of_playlists - remaining_playlists.count() + 1
        playlist = remaining_playlists.order_by('created_at')[0]
        playlist_name = playlist.name
        playlist_id = playlist.playlist_id
        Playlist.objects.getAllVideosForPlaylist(request.user, playlist_id)
    except Exception:
        logger.debug('NO REMAINING PLAYLISTS')
        playlist_id = -1

    if playlist_id != -1:
        return HttpResponse(
            loader.get_template('intercooler/progress_bar.html').render({
                'total_playlists': num_of_playlists,
                'playlists_imported': playlists_imported,
                'playlist_name': playlist_name,
                'progress': round((playlists_imported / num_of_playlists) * 100, 1),
                'channel_found': True
            })
        )
    else:
        # request.user.profile.just_joined = False
        request.user.profile.import_in_progress = False
        request.user.profile.imported_yt_playlists = True
        request.user.profile.show_import_page = True  # set back to true again so as to show users the welcome screen on 'home'
        request.user.save()

        user_pl_count = request.user.playlists.filter(Q(is_user_owned=True) &
                                                      Q(is_in_db=True)).exclude(playlist_id='LL').count()

        return HttpResponse(
            loader.get_template('intercooler/progress_bar.html').render({
                'total_playlists': user_pl_count,
                'playlists_imported': user_pl_count,
                'done': True,
                'progress': 100,
                'channel_found': True
            })
        )


@login_required
def user_playlists_updates(request, action):
    """
    Gets all user created playlist's ids from YouTube and checks them with the user playlists imported on UnTube.
    If any playlist id is on UnTube but not on YouTube, deletes the playlist from YouTube.
    If any new playlist id, imports it to UnTube
    """
    if action == 'check-for-updates':
        user_playlists_on_UnTube = request.user.playlists.filter(Q(is_user_owned=True) &
                                                                 Q(is_in_db=True)).exclude(playlist_id='LL')

        result = Playlist.objects.initializePlaylist(request.user)

        logger.debug(result)
        youtube_playlist_ids = result['playlist_ids']
        untube_playlist_ids = []
        for playlist in user_playlists_on_UnTube:
            untube_playlist_ids.append(playlist.playlist_id)

        deleted_playlist_ids = []
        deleted_playlist_names = []
        for pl_id in untube_playlist_ids:
            if pl_id not in youtube_playlist_ids:  # ie this playlist was deleted on youtube
                deleted_playlist_ids.append(pl_id)
                pl = request.user.playlists.get(playlist_id__exact=pl_id)
                deleted_playlist_names.append(f'{pl.name} (had {pl.video_count} videos)')
                pl.delete()

        if result['num_of_playlists'] == user_playlists_on_UnTube.count() and len(deleted_playlist_ids) == 0:
            logger.info('No new updates')
            playlists = []
        else:
            playlists = request.user.playlists.filter(Q(is_user_owned=True) &
                                                      Q(is_in_db=False)).exclude(playlist_id='LL')
            logger.info(
                f'New updates found! {playlists.count()} newly added and {len(deleted_playlist_ids)} playlists deleted!'
            )
            logger.info(deleted_playlist_names)

        return HttpResponse(
            loader.get_template('intercooler/user_playlist_updates.html').render({
                'playlists': playlists,
                'deleted_playlist_names': deleted_playlist_names
            })
        )
    elif action == 'init-update':
        unimported_playlists = request.user.playlists.filter(Q(is_user_owned=True) &
                                                             Q(is_in_db=False)).exclude(playlist_id='LL').count()

        return HttpResponse(
            f"""
        <div hx-get='/updates/user-playlists/start-update' hx-trigger='load' hx-target='#user-pl-updates'>
            <div class='alert alert-dismissible fade show' role='alert' style='background-color: cadetblue'>
                <div class='d-flex justify-content-center mt-4 mb-3 ms-2' id='loading-sign' >
                    <img src='/static/svg-loaders/spinning-circles.svg' width='40' height='40'>
                    <h5 class='mt-2 ms-2 text-black'>Importing {unimported_playlists} new playlists into UnTube, please wait!</h5>
                </div>
            </div>
        </div>
        """
        )
    elif action == 'start-update':
        unimported_playlists = request.user.playlists.filter(Q(is_user_owned=True) &
                                                             Q(is_in_db=False)).exclude(playlist_id='LL')

        for playlist in unimported_playlists:
            Playlist.objects.getAllVideosForPlaylist(request.user, playlist.playlist_id)

        return HttpResponse(
            """
        <div class='alert alert-success alert-dismissible fade show d-flex justify-content-center' role='alert'>
          <h4 class=''>Successfully imported new playlists into UnTube!</h4>
            <meta http-equiv='refresh' content='0;url=/home/#recent-playlists' />
            <meta http-equiv='refresh' content='2;url=/home/' />

            <button type='button' class='btn-close' data-bs-dismiss='alert' aria-la bel='Close'></button>
        </div>
        """
        )


@login_required
def get_user_liked_videos_playlist(request):
    if not request.user.playlists.filter(Q(playlist_id='LL') & Q(is_in_db=True)).exists():
        Playlist.objects.initializePlaylist(request.user, 'LL')
        Playlist.objects.getAllVideosForPlaylist(request.user, 'LL')
        messages.success(request, 'Successfully imported your Liked Videos playlist!')

    return HttpResponse("""
        <script>
        window.location.reload();
        </script>
    """)


# FOR INDEX.HTML
@require_POST
def like_untube(request):
    untube = Untube.objects.all().first()
    untube.page_likes += 1
    untube.save()

    request.session['liked_untube'] = True
    request.session.save()

    return HttpResponse(
        f"""
            <a hx-post='/unlike-untube/' hx-swap='outerHTML' style='text-decoration: none; color: black'>
            <i class='fas fa-heart' style='color: #d02e2e'></i> {untube.page_likes} likes (p.s glad you liked it!)
          </a>
    """
    )


@require_POST
def unlike_untube(request):
    untube = Untube.objects.all().first()
    untube.page_likes -= 1
    untube.save()

    request.session['liked_untube'] = False
    request.session.save()

    return HttpResponse(
        f"""
                <a hx-post='/like-untube/' hx-swap='outerHTML' style='text-decoration: none; color: black'>
                <i class='fas fa-heart'></i> {untube.page_likes} likes (p.s :/)
              </a>
        """
    )
