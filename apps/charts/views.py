from django.db.models import Count, Q
from django.http import JsonResponse


def channel_videos_distribution(request, playlist_id):
    labels = []
    data = []

    playlist_items = request.user.playlists.get(playlist_id=playlist_id).playlist_items.all()

    queryset = playlist_items.filter(Q(video__is_unavailable_on_yt=False) & Q(video__was_deleted_on_yt=False)).values('video__channel_name').annotate(channel_videos_count=Count('video_position')).order_by(
        '-channel_videos_count')
    for entry in queryset:
        labels.append(entry['video__channel_name'])
        data.append(entry['channel_videos_count'])

    return JsonResponse(data={
        'labels': labels,
        'data': data,
    })
