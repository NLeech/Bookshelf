from celery import shared_task, chain

from .dump_importer import import_dump
from .book_importer import process_daily_updates, get_filters

@shared_task
def run_import_dump(batch_size=5000, path='', table_filter=''):
    import_dump(
        path=path, 
        table_filter=table_filter, 
        batch_size=batch_size
    )

@shared_task
def run_import_books(genres=None, langs=None, formats=None):
    filters = get_filters(
        genres_filters=genres,
        languages_filters=langs,
        formats_filters=formats
    )
    process_daily_updates(filters=filters)

@shared_task
def trigger_full_import_workflow(**kwargs):
    """
    This is the task scheduled by django-celery-beat.
    If the PeriodicTask in the admin has kwargs:
    {"batch_size": 10000, "genres": ["sf", "fantasy"], "langs": ["ru"], "formats": ["epub"]}
    It will be passed here as **kwargs.
    """
    
    # 1. Extract arguments for the dump task (provide defaults if missing)
    batch_size = kwargs.get('batch_size', 5000)
    dump_path = kwargs.get('dump_path', '')
    table_filter = kwargs.get('table_filter', '')
    
    # 2. Extract arguments for the book task
    genres = kwargs.get('genres')
    langs = kwargs.get('langs')
    formats = kwargs.get('formats')

    # 3. Create the chain using .si() (immutable signatures)
    # This prevents run_import_dump from passing its return value to run_import_books
    workflow = chain(
        run_import_dump.si(
            batch_size=batch_size, 
            path=dump_path, 
            table_filter=table_filter
        ),
        run_import_books.si(
            genres=genres, 
            langs=langs, 
            formats=formats
        )
    )
    
    # 4. Fire the workflow
    workflow.apply_async()
