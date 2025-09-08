from django.test import TestCase


class HealthCheckTest(TestCase):
    def test_health_check(self):
        res = self.client.get('/ping/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b'pong')
