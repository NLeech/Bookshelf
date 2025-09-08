import logging
from django.core.management.base import BaseCommand

from library.sevices import update_authors_from_flibusta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):

        update_authors_from_flibusta()

        logger.info("Authors were updated successfully!")
