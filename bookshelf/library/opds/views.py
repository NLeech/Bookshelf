from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .renderers import OPDSRenderer
from .serializers import build_root_feed
from .throttles import OPDSDayRateThrottle, OPDSMinuteRateThrottle


class OPDSBaseView(APIView):
    """Base class for all OPDS feed views.

    Enforces the shared renderer, throttle, and permission configuration
    used across every OPDS endpoint.  Authentication is intentionally
    disabled at the class level — Phase 1 provides no authentication
    challenge; download-link visibility is enforced per-request inside
    each serializer.
    """

    renderer_classes = [OPDSRenderer]
    throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]
    authentication_classes = []
    permission_classes = [AllowAny]


class RootFeedView(OPDSBaseView):
    """GET /opds/v1/ — root navigation catalog feed.

    Returns a fixed navigation feed with five entries:
    Authors, Genres, Series, Books, Search.
    No database queries are required.
    """

    def get(self, request):
        feed = build_root_feed(request)
        return Response(feed)
