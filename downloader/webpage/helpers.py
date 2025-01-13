import uuid
from .models import VideoLog, KeyLog
from pathlib import Path
from datetime import datetime, timedelta
from .spotify import get_token
from pytubefix import Search, YouTube
from .tasks import download_batch
from celery import group
import time
import os


# File (audio/directory) expiring duration in minutes
EXPIRES_IN = 30


def fix_filename(filename):
    """
    Fixes filename by replacing invalid symbols with empty string('')
    Returns valid filename
    """
    symbols = ['.', '/', '\\', '|', '*', '>', '<', '"', ':', '?']

    if filename:
        for symbol in symbols:
            filename = filename.replace(symbol, '')

    return filename


def calculate_duration(length) -> str:
    """
    Returns duration(as string)
    ...
    Parameter :
    - length(int) : length of the Youtube video in seconds from pytubefix.Youtube
    """
    # Calculating seconds to display in duration
    audio_length = length
    nearest_mul = audio_length // 60
    remaining_secs = audio_length - (nearest_mul * 60)

    if remaining_secs < 10:
        remaining_secs = '0' + str(remaining_secs)
    duration = f'{nearest_mul}:{remaining_secs}'
    return duration


def check_db(filename, f_type='YT', spotify_id=None) -> bool:
    """
    Returns True if filename(pram) or
    spotify_id does not present in database
    ...
    Parameters :
    - filename   : File name that should be checked in the db(VideoLog)
    - f_type     : File type - 'YT' for youtube audio(default) - 'SP' for spotify
    - spotify_id : id of a spotify playlist/album/track)
    """
    # Checking database if the current file already exists
    update_db = True
    if f_type == 'SP':
        all_logs = VideoLog.object.filter(file_metadata__startswith='sp_')
    else:
        all_logs = VideoLog.object.filter(file_metadata__startswith='yt_')

    for file in all_logs:
        if filename and file.file_name == filename:
            update_db = False
        if spotify_id and file.file_metadata.split('__')[-1] == spotify_id:
            update_db = False

    return update_db


def download_song(song_name, yt, f_id):
    """
    Downloads the given song(song_name:param) to the server and stores its info to db(VideoLog)
    OR returns exiting info if file already exists.
    ...
    Parameters :
    - song_name : Name of the song to download (without extension)
    - yt        : pytubefix.Youtube() class's object of the given song
    - f_id     : file_id(str) containing metadata about the function call
                (example : yt_audio or sp_album__123532 - sp : denotes spotify,
                                             album : denotes that this function is called to download spotify album,
                                             123532 : spotify album id)
    returns :
    - song_to_download  : song name with extension - .mp3
    -  filepath         : file path of that song
    """
    CWD_PATH = Path(__file__).resolve().parent.parent
    base_dir = os.path.join(CWD_PATH, '..\\files')
    os.makedirs(base_dir, exist_ok=True)

    filepath = base_dir
    song_to_download = song_name + '.mp3' # or'.m4a' '.aac'

    if f_id.startswith('yt_'):
        do_update = check_db(song_to_download)
    else:
        do_update = check_db('', f_type='SP', spotify_id=f_id.split('__')[-1])

    if do_update:
        # saving song's data to db if it does not already exist
        ys = yt.streams.get_audio_only()
        if ys:
            ys.download(output_path=filepath, filename=song_to_download)
            file_info = VideoLog(
                file_path=filepath,
                file_name=song_to_download,
                file_metadata=f_id,
                expires_at=datetime.now().replace(tzinfo=None) + timedelta(minutes=EXPIRES_IN)
            )
            file_info.save()
        else:
            print(f'Unable to download song')

        return song_to_download, filepath

    else:
        # If the file already exists - just return the filename and filepath
        if f_id == 'yt_audio':
            # If existing song is downloaded from yt, the search using song name
            existing_file = VideoLog.object.get(file_name=song_to_download)
        else:
            # else if it's from spotify > get using its id
            existing_file = VideoLog.object.get(file_metadata__endswith=f_id.split('__')[-1])

        return existing_file.file_name, existing_file.file_path


def get_youtube_url(search_query):
    """
    Returns the first result's watch URL from youtube when searched using
    search_query(param) using pytube.Search()
    """
    searches = Search(search_query + 'official audio')
    return searches.videos[0].watch_url


def get_spotify_token(add_new=False):
    """
    Checks KeyLog table if api_key already exists - if it does then return existing key,
    else return a new(got from Spotify API) one.
    ...
    Parameter :
    - add_new : used only when called by scheduler
    """
    existing_token = KeyLog.object.first()
    if not existing_token or add_new:
        token = get_token()
        time.sleep(3)
        new_token = KeyLog(
            api_token=token,
            expires_at=datetime.now().replace(tzinfo=None) + timedelta(seconds=3600)
        )
        new_token.save()
        result = token
    else:
        result = existing_token.api_token

    if not add_new:
        return result


def create_song_batches(song_list, batch_size=10):
    """
    Breaks the entire song_list(spotify playlist/album) into fragments(param:fragment_size) and
    returns them in a list
    ...
    Parameters :
    - song_list  : long list of songs (over 20 at least)
    - batch_size : Size of each song batch (10 by default)
    """
    lst_chunks = []
    n = len(song_list)
    rem = n % batch_size

    for i in range(0, n - batch_size + 1, batch_size):
        start = i
        end = start + batch_size
        lst_chunks.append(song_list[start:end])

    if rem > 0:
        print('inhere')
        lst_chunks.append(song_list[n - rem: n + 1: 1])

    return lst_chunks


def get_filename(path):
    """
    Returns the directory name at the end of the file path.
    """
    normalized_path = os.path.normpath(str(path))
    file_name = os.path.basename(normalized_path)
    return file_name


def download_song_fragment(dir_path, song_fgs, f_id):
    """
    Downloads song(song_fgs:param) into a unique directory(param) in the server.
    ...
    Parameters :
    - dir_path : The absolute directory path with the unique directory
    - song_fgs : list of list containing songs in fragments(groups for concurrent download)
    - f_id     : file_id(str) containing metadata about the function call
                (example : sp_album_123532 - sp : denotes spotify,
                                             album : denotes that this function is called to download spotify album,
                                             123532 : spotify album id)
    ...
    Returns :
    - dir_path : absolute directory path with the unique directory name
    - filename : unique directory's name
    """
    if check_db('', f_type='SP', spotify_id=f_id.split('__')[-1]):
        os.mkdir(dir_path)

        file_name = get_filename(dir_path)

        b_id = uuid.uuid4().hex[:15]
        file_info = VideoLog(
            file_path=dir_path,
            file_type='directory',
            file_metadata=f_id,
            expires_at=datetime.now().replace(tzinfo=None) + timedelta(minutes=EXPIRES_IN),
            batch_id=b_id
        )
        file_info.save()

        task_list = []
        for frag in song_fgs:
            # Perform this task using django-celery
            task_list.append(download_batch.s(frag, b_id, dir_path))

        jobs = group(task_list)
        jobs.apply_async()

        return b_id, dir_path, file_name

    else:
        existing_dir = VideoLog.object.get(file_metadata__endswith=f_id.split('__')[-1])
        file_path = existing_dir.file_path
        file_name = get_filename(file_path)

        return None, file_path, file_name


def write_unavailable_songs(songs_list, downloaded_contents, dir_path):
    """
    Writes the list of un-downloaded songs(un-downloaded due to some error while using celery django)
    to a readme.txt file inside unique dir.
    """
    d_contents = set()
    for s in downloaded_contents:
        file_rep = s.replace('.mp3', '')
        file_fix = fix_filename(file_rep)
        d_contents.add(file_fix)

    remaining_songs = []
    for song in songs_list:
        if fix_filename(song) not in d_contents:
            remaining_songs.append(song)

    if remaining_songs:
        # Cannot download remaining songs so write it to a txt file
        with open(os.path.join(dir_path, '000_readme.txt'), 'w') as f:
            f.write('Here is the list of songs that could not be downloaded.\n'
                    ' try downloading them individually.')
            f.write('\n')
            for i, song in enumerate(remaining_songs, start=1):
                f.write(f'{i} - {song}')
                f.write('\n')



