""" Contains helper functions that download multiple files """
from django.shortcuts import HttpResponse
from django_celery_results.models import  TaskResult

import io
from uuid import uuid4
import zipfile
from pytubefix import YouTube
from datetime import datetime
from time import sleep

from .helpers import get_youtube_url



def download_20(request, songs_len):
    """Downloads 20 tracks into the zipbuffer and then to client's PC"""
    # Initializing zip buffer
    zip_buffer = io.BytesIO()
    zip_filename = f'{uuid4().hex[:8]}_{datetime.now().strftime("%Y%m%d%H%M%S")}.zip'
    unavailable = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i in range(1, songs_len + 1):
            search_string = request.POST.get(f'song_name_{i}')
            yt_url = get_youtube_url(search_string)
            yt = YouTube(yt_url)
            audio_stream = yt.streams.get_audio_only()

            if audio_stream:
                # Download audio stream into memory without creating any temp file
                audio_buffer = io.BytesIO()
                audio_stream.stream_to_buffer(audio_buffer)
                audio_buffer.seek(0)

                # Add the audio stream into zip archive
                filename = f'{search_string}.mp3'
                zipf.writestr(filename, audio_buffer.read())
            else:
                unavailable.append(search_string)
                continue

    zip_buffer.seek(0) # resets the seek to 0
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'

    print(f'Unavailable tracks : {unavailable}')

    return response

def timeout_mech(songs_fragments, r_batch_id):
    """
    timeout mechanism to check if all the celery workers have logged their jobs
    into django-celer-tasks db table
    """
    # Wait until all tasks are complete
    batch_length = len(songs_fragments)
    print('Batch length : ', batch_length)
    prev, curr = 0, 0
    initial_tasks_length = 0
    repeater = 0
    sleep_time = 15
    while True:
        tasks = TaskResult.objects.all().filter(result=f'"{r_batch_id}"')

        sleep(sleep_time)

        tasks_len = len(tasks)
        print('Sleep time', sleep_time)
        print('tasks length : ', tasks_len)
        print('prev : ', prev, 'curr', curr)
        print('------------------------')
        if tasks_len > initial_tasks_length:
            sleep_time = 6
            # Now the task length has started going up
            curr = tasks_len
            print('printing prev and curr inside if', prev, curr)
            if prev == curr:
                if repeater == 15:
                    print('broken from repeated tasks')
                    break
                repeater += 1
            elif prev != curr and repeater > 1:
                repeater = 1

            prev, curr = curr, 0

        if tasks_len == batch_length:
            print('broken after matching batch_length')
            break

    print(f'Tasks {tasks} with length {len(tasks)}')
