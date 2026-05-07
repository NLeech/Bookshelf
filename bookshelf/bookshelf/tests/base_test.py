import shutil
import tempfile

from django.test import TestCase, override_settings



class BaseTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_media_root = tempfile.mkdtemp()
        
        overridden_storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "cloud": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        
        overridden_caches = {
            "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
            "book_chapters": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
        }
        
        cls._base_settings_override = override_settings(
            STORAGES=overridden_storages, 
            MEDIA_ROOT=cls.temp_media_root,
            CACHES=overridden_caches
        )
        cls._base_settings_override.enable()
        super().setUpClass()


    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._base_settings_override.disable()
        shutil.rmtree(cls.temp_media_root, ignore_errors=True)
