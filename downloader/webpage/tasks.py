from celery import shared_task
from pytubefix import YouTube, Search


@shared_task
def download_batch(batch, batch_id, dir_path):
    """
    Downloads a batch of songs(usually 10) into the given dir_path using celery's @shared_task
    ...
    Parameters :
    - batch     : Contains a list(batch - 10 default) of audio track's names
    - batch_id  : An unique id (15 digits) to denote a batch
    - dir_path  : absolute path to the directory into which all the batch's songs will be downloaded
    Return :
    - batch_id : returns the batch id -> which will be saved in the django_celery_tasks_taskresult table for later use.
    """
    for song in batch:
        yt_url = get_youtube_url(song)
        yt = YouTube(yt_url)
        audio_stream = yt.streams.get_audio_only()
        if audio_stream:
            audio_stream.download(filename=f'{song}.mp3', output_path=dir_path)

    return batch_id

def get_youtube_url(search_query):
    """
    Returns the first result's watch URL from youtube when searched using
    search_query(param) using pytube.Search()
    """
    try:
        searches = Search(search_query + 'official audio')
        _ = searches.videos[0]
    except IndexError:
        searches = Search(search_query)
        search_vid = searches.videos[0]
    else:
        searches = Search(search_query + 'official audio')
        search_vid = searches.videos[0]

    return search_vid.watch_url
