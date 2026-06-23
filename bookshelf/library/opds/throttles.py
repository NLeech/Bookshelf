from rest_framework.throttling import AnonRateThrottle


class OPDSMinuteRateThrottle(AnonRateThrottle):
    scope = 'opds_anon'


class OPDSDayRateThrottle(AnonRateThrottle):
    scope = 'opds_anon_daily'
