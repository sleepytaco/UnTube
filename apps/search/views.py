from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import loader
from django.views.decorators.http import require_POST

from apps.main.models import Video, Tag


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

    channels = []
    if 'channel-names' in request.POST:
        channels = request.POST.getlist('channel-names')

    if request.POST['search-settings'] == 'playlists':
        playlists = all_playlists.filter(Q(name__istartswith=search_query) | Q(
            user_label__istartswith=search_query)) if search_query != "" else all_playlists.none()

        if search_query == "":
            playlists = all_playlists

        return HttpResponse(loader.get_template("intercooler/search_untube_results.html")
                            .render({"playlists": playlists,
                                     "search_query": search_query}))
    else:
        playlists = all_playlists.filter(Q(name__icontains=search_query) | Q(
            user_label__istartswith=search_query)) if search_query != "" else all_playlists.none()

        if search_query == "":
            playlists = all_playlists

        videos = Video.objects.none()
        for playlist in playlists:
            pl_videos = playlist.videos.filter(is_unavailable_on_yt=False)
            videos = videos | pl_videos

        videos = videos.filter(
            Q(name__icontains=search_query) | Q(user_label__istartswith=search_query)).distinct()

        return HttpResponse(loader.get_template("intercooler/search_untube_results.html")
                            .render({"videos": videos[:250],
                                     "show_all_videos": len(channels) > 0}))


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


@login_required
@require_POST
def search_tagged_playlists(request, tag):
    tag = get_object_or_404(Tag, created_by=request.user, name=tag)
    playlists = tag.playlists.all()

    return HttpResponse("yay")
