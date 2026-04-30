from celery import shared_task, chain

from .dump_importer import import_dump
from .book_importer import process_daily_updates, get_filters

@shared_task
def run_import_dump(**kwargs):

    batch_size = kwargs.get('batch_size', 5000)
    path = kwargs.get('path', '')
    table_filter = kwargs.get('table_filter', '')
    
    import_dump(
        path=path, 
        table_filter=table_filter, 
        batch_size=batch_size
    )

@shared_task
def run_import_books(**kwargs):
    genres = kwargs.get('genres')
    langs = kwargs.get('langs')
    formats = kwargs.get('formats')

    filters = get_filters(
        genres_filters=genres,
        languages_filters=langs,
        formats_filters=formats
    )
    process_daily_updates(filters=filters)

@shared_task
def trigger_full_import_workflow(**kwargs):

    # Create the chain using .si() (immutable signatures)
    # This prevents run_import_dump from passing its return value to run_import_books
    workflow = chain(
        run_import_dump.si(kwargs),
        run_import_books.si(kwargs)
    )
    # 4. Fire the workflow
    workflow.apply_async()
