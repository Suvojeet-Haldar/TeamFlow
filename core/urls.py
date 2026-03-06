from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("invite/", views.invite_member, name="invite_member"),
    path("invite/accept/<uuid:token>/", views.accept_invite, name="accept_invite"),
    path("invite/check-username/", views.check_username, name="check_username"),
    path("invite/suggest-usernames/", views.suggest_usernames, name="suggest_usernames"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/create/", views.create_project, name="create_project"),
    path("projects/<int:project_id>/", views.project_detail, name="project_detail"),
    path("projects/<int:project_id>/complete/", views.complete_project, name="complete_project"),
    path("projects/<int:project_id>/reactivate/", views.reactivate_project, name="reactivate_project"),
    path("projects/<int:project_id>/assign-manager/", views.assign_project_manager, name="assign_project_manager"),
    path("tasks/<int:task_id>/update-status/", views.update_task_status, name="update_task_status"),
    path("settings/", views.org_settings, name="org_settings"),
    path("team/", views.team, name="team"),
    path("team/<int:user_id>/assign-manager/", views.assign_manager, name="assign_manager"),
    path("team/<int:user_id>/assign-project/", views.assign_project, name="assign_project"),
    path("team/<int:user_id>/reassign-role/", views.reassign_role, name="reassign_role"),
    path("team/<int:user_id>/remove/", views.remove_member, name="remove_member"),
    path("team/<int:user_id>/set-expiry/", views.set_expiry_date, name="set_expiry_date"),
    path("member/<int:user_id>/", views.member_card, name="member_card"),
    path("profile/edit/", views.edit_profile, name="edit_profile"),
    path("", views.landing, name="landing"),
]