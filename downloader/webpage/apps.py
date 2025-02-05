from django.apps import AppConfig
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import os
from shutil import rmtree


class WebpageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webpage'

    def ready(self):
        self.deleter()

    def deleter(self):
        scheduler = BackgroundScheduler()
        scheduler.add_job(self.clear_dir_job, 'interval', minutes=5)
        scheduler.add_job(self.clear_expired_keys, 'interval', seconds=30)
        scheduler.add_job(self.clear_django_celery_task_results, 'interval', minutes=1)
        scheduler.start()

    @staticmethod
    def clear_dir_job():
        """
        Deletes the contents of a file if the logged(VideoLog db) time expires.
        """
        from .models import VideoLog
        all_logs = VideoLog.object.all()

        for log in all_logs:
            curr_timestamp = datetime.now().replace(tzinfo=None)
            if log.expires_at.replace(tzinfo=None) < curr_timestamp:
                if log.file_type == 'directory':
                    rmtree(log.file_path)
                else:
                    os.remove(os.path.join(log.file_path, log.file_name))
                log.delete()

    @staticmethod
    def clear_expired_keys():
        """
        Deletes spotify key after it expires (uses KeyLog table) and adds a newone.
        """
        from .models import KeyLog
        from .helpers import get_spotify_token
        all_keys = KeyLog.object.all()

        for key in all_keys:
            curr_timestamp = datetime.now().replace(tzinfo=None)
            if key.expires_at.replace(tzinfo=None) < curr_timestamp:
                key.delete()
                # Adding a new key after one expires
                current_all_keys = KeyLog.object.all()
                if len(current_all_keys) < 2:
                    get_spotify_token(add_new=True)

    @staticmethod
    def clear_django_celery_task_results():
        """
        Clears up all the saved task results from django-celery-db TaskResult table.
        """
        from django_celery_results.models import TaskResult
        TaskResult.objects.delete_expired(timedelta(minutes=15))
