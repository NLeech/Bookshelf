import logging
from django.core.management.base import BaseCommand

from third_part_libraries.sevices import FlibustaInterface

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def handle(self, *args, **options):

        interface = FlibustaInterface()
        interface.update_authors()

        logger.info("Flibusta authors was updated successfully!")
