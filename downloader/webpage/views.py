from django.shortcuts import render, redirect, HttpResponse
from django.contrib import messages
from django.http import FileResponse
from .spotify import (
    get_playlist_tracks, get_playlist_info, get_track_info,
    get_album_tracks, get_album_info
)
from urllib.parse import urlparse
from django_celery_results.models import TaskResult
from .helpers import *
from uuid import uuid4
import zipfile
from time import sleep
import io
import re
import os


def home(request):
    """Home page"""
    # Delete all logs
    # VideoLog.object.all().delete()

    if request.method == 'POST':
        input_link = request.POST['link']

        parsed_url = urlparse(input_link)
        netloc_dict = {
            'spotify': ['open.spotify.com'],
            'youtube': ['www.youtube.com', 'youtu.be']
        }
        re_playlist = r'/playlist/'
        re_track = r'/track/'
        re_album = r'/album/'

        request.session['link'] = input_link

        if parsed_url.netloc in netloc_dict['youtube']:
            # redirect to youtube link page
            return redirect('youtube')

        elif parsed_url.netloc in netloc_dict['spotify']:
            request.session['parsed_link'] = parsed_url
            if re.match(re_playlist, parsed_url.path):
                return redirect('spotify')
            elif re.match(re_track, parsed_url.path):
                return redirect('spotify track')
            elif re.match(re_album, parsed_url.path):
                return redirect('spotify album')

        else:
            messages.info(request, 'Invalid Link! Use a valid Youtube or Spotify share link')
            return redirect('home')

    return render(request, 'webpage/index.html')


def youtube(request):
    """Youtube audio page"""
    link = request.session.get('link', '')
    yt = YouTube(link, 'WEB')
    duration = calculate_duration(yt.length)

    if request.method == 'POST':
        filename_input = request.POST['filenameinput']

        filename = fix_filename(filename_input)

        file_to_download, filepath = download_song(filename, yt, f_id='yt_audio')

        # Downloading audio to user
        response = FileResponse(open(os.path.join(filepath, file_to_download), 'rb'),
                               as_attachment=True, filename=file_to_download)

        return response

    return render(request, 'webpage/youtube.html',
                  {'link': link, 'yt': yt, 'duration': duration})


def spotify(request):
    """Spotify playlist page"""
    link = request.session.get('link', '')
    parsed_link = request.session.get('parsed_link', '')
    playlist_id = parsed_link[2].split('/')[-1]

    token = get_spotify_token()
    playlist_songs = get_playlist_tracks(token, playlist_id)
    playlist_info = get_playlist_info(token, playlist_id)

    if playlist_songs:
        songs_len = len(playlist_songs)
        # print(playlist_songs)

        if request.method == "POST":
            print('downloading playlist')
            if songs_len <= 20:
                try:
                    return download_20(request, songs_len)
                except Exception as e:
                    return HttpResponse(f'Exception occurred {str(e)}', status=500)

            else:
                # download as chunks to the server
                song_inputs = []
                for i in range(1, songs_len + 1):
                    song = request.POST.get(f'song_name_{i}')
                    song_inputs.append(song)

                songs_fragments = create_song_batches(song_inputs)

                dir_filename = f'{uuid4().hex[:8]}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
                CWD_PATH = os.path.join(Path(__file__).resolve().parent.parent, '..\\files')
                dir_path = os.path.join(CWD_PATH, dir_filename)

                r_batch_id, r_dir_path, r_file_name = download_song_fragment(dir_path, songs_fragments, f_id=f'sp_playlist__{playlist_id}')

                if r_batch_id is not None:

                    timeout_mech(songs_fragments, r_batch_id)

                    downloaded_contents = os.listdir(dir_path)

                    if len(song_inputs) != len(downloaded_contents):
                        write_unavailable_songs(song_inputs, downloaded_contents, dir_path)

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for root, dirs, files in os.walk(r_dir_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zip_file.write(file_path, os.path.relpath(file_path, r_dir_path))

                zip_buffer.seek(0)

                response = HttpResponse(zip_buffer, 'application/zip')
                response['Content-Disposition'] = f'attachment; filename={r_file_name}.zip'

                return response


        return render(request, 'webpage/spotify.html',
                       {'link': link, 'link_type': 'spotify',
                               'songs': playlist_songs, 'song_len': songs_len,
                                'info': playlist_info})
    else:
        messages.error(request, 'Error. Try again')
        return redirect('home')


def spotify_album(request):
    """Spotify album page"""
    link = request.session.get('link', '')
    parsed_link = request.session.get('parsed_link', '')
    album_id = parsed_link[2].split('/')[-1]

    token = get_spotify_token()
    album_songs = get_album_tracks(token, album_id)
    album_info = get_album_info(token, album_id)

    if album_songs:
        songs_len = len(album_songs)
        # The downloading part
        if request.method == "POST":
            if songs_len <= 20:
                try:
                    return download_20(request, songs_len)
                except Exception as e:
                    return HttpResponse(f'Exception occurred {str(e)}', status=500)

            else:
                print('in here - album')
                # download as chunks to the server
                print('in here')
                song_inputs = []
                for i in range(1, songs_len + 1):
                    song = request.POST.get(f'song_name_{i}')
                    song_inputs.append(song)

                songs_fragments = create_song_batches(song_inputs)

                dir_filename = f'{uuid4().hex[:8]}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
                CWD_PATH = os.path.join(Path(__file__).resolve().parent.parent, '..\\files')
                dir_path = os.path.join(CWD_PATH, dir_filename)

                r_batch_id, r_dir_path, r_file_name = download_song_fragment(dir_path, songs_fragments, f_id=f'sp_album__{album_id}')

                if r_batch_id is not None:

                    timeout_mech(songs_fragments, r_batch_id)

                    downloaded_contents = os.listdir(dir_path)

                    if len(song_inputs) != len(downloaded_contents):
                        write_unavailable_songs(song_inputs, downloaded_contents, dir_path)

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for root, dirs, files in os.walk(r_dir_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            zip_file.write(file_path, os.path.relpath(file_path, r_dir_path))

                zip_buffer.seek(0)

                response = HttpResponse(zip_buffer, 'application/zip')
                response['Content-Disposition'] = f'attachment; filename={r_file_name}.zip'

                return response


        return render(request, 'webpage/spotify album.html',
                      {'link': link, 'link_type': 'spotify',
                       'songs': album_songs, 'song_len': songs_len,
                       'info': album_info})

    else:
        messages.info(request, 'Error Try again')
        return redirect('home')


def spotify_track(request):
    """Spotify track page"""
    # From Spotify playlist listing page
    api_link = request.GET.get('api_link')

    # From home page
    link = request.session.get('link', '')
    token = get_spotify_token()

    if api_link:
        # got from listing
        track_id = urlparse(api_link).path.split('/')[-1]
    else:
        # got from home page
        parsed_link = urlparse(link)
        track_id = parsed_link.path.split('/')[-1]

    track_info = get_track_info(token=token, track_id=track_id)

    if request.method == "POST":
        file_name = request.POST.get('filenameinput')
        track_id_ip = request.POST.get('track_id_input')
        file_name = fix_filename(file_name)
        yt_url = get_youtube_url(file_name)
        yt = YouTube(yt_url)

        song_to_download, filepath = download_song(file_name, yt, f_id=f'sp_track__{track_id_ip}')
        response = FileResponse(open(os.path.join(filepath, song_to_download), 'rb'),
                                as_attachment=True, filename=song_to_download)

        return response

    return render(request, 'webpage/spotify track.html',
                  {'track': track_info})


def info_page(request):
    """'How to ?' page"""
    return render(request, 'webpage/info.html')
