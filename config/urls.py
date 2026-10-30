from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("comments/", include("comments.urls")),
    path("", RedirectView.as_view(pattern_name="comments:index", permanent=False)),
]
