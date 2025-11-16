def get_celery():
    from app.celery_config import celery_app
    return celery_app

__all__ = ['get_celery']
