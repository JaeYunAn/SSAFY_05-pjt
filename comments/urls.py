from django.urls import path

from . import views

app_name = "comments"

urlpatterns = [
    path("", views.index, name="index"),
    path("company/", views.company, name="company"),
    path("<int:pk>/review/", views.review, name="review"),
    path("<int:pk>/", views.result, name="result"),
    path("<int:pk>/summary/", views.summary, name="summary"),
    path("<int:pk>/json/", views.export_json, name="json"),
]
