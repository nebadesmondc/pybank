from .celery_app import app as celery_app

__all__ = ('celery_app',) # Make sure tasks are always imported