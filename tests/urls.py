from django.urls import include, path

urlpatterns = [path("", include("origami_auth.urls"))]
