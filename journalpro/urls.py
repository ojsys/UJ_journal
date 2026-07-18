from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as media_serve

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('journalapp.urls')),
]

# Serve user-uploaded media (profile pictures, hero slides, journal covers,
# uploaded documents, etc.).
#
# WhiteNoise serves STATIC files in production but NOT media, and Django's
# built-in static() media helper only registers a route when DEBUG=True. On
# shared cPanel/Passenger the web server can't serve /media/ directly either,
# so we route media through Django in every environment. This is efficient
# enough for this site's traffic; move to a CDN / object storage if that changes.
_media_prefix = settings.MEDIA_URL.lstrip('/')
urlpatterns += [
    re_path(rf'^{_media_prefix}(?P<path>.*)$', media_serve,
            {'document_root': settings.MEDIA_ROOT}),
]
