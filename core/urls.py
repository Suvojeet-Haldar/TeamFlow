from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("invite/", views.invite_member, name="invite_member"),
    path("invite/accept/<uuid:token>/", views.accept_invite, name="accept_invite"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/create/", views.create_project, name="create_project"),
    path("projects/<int:project_id>/", views.project_detail, name="project_detail"),
    path("tasks/<int:task_id>/update-status/", views.update_task_status, name="update_task_status"),
]