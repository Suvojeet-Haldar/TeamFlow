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
    path("settings/", views.org_settings, name="org_settings"),
    path("team/", views.team, name="team"),
    path("team/<int:user_id>/assign-manager/", views.assign_manager, name="assign_manager"),
    path("team/<int:user_id>/reassign-role/", views.reassign_role, name="reassign_role"),
    path("team/<int:user_id>/remove/", views.remove_member, name="remove_member"),
]