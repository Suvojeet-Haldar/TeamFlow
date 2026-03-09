from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.landing, name='landing'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('accounts/logout/', views.custom_logout, name='logout'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<int:project_id>/complete/', views.complete_project, name='complete_project'),
    path('projects/<int:project_id>/reactivate/', views.reactivate_project, name='reactivate_project'),
    path('projects/<int:project_id>/assign-manager/', views.assign_project_manager, name='assign_manager'),
    path('tasks/<int:task_id>/update-status/', views.update_task_status, name='update_task_status'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('member/<int:user_id>/', views.member_card, name='member_card'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('team/', views.team, name='team'),
    path('team/<int:user_id>/assign-manager/', views.assign_manager, name='team_assign_manager'),
    path('team/<int:user_id>/assign-project/', views.assign_project, name='assign_project'),
    path('team/<int:user_id>/reassign-role/', views.reassign_role, name='reassign_role'),
    path('team/<int:user_id>/remove/', views.remove_member, name='remove_member'),
    path('team/<int:user_id>/set-expiry/', views.set_expiry_date, name='set_expiry'),
    path('settings/', views.org_settings, name='org_settings'),
    path('invite/', views.invite_member, name='invite_member'),
    path('invite/accept/<uuid:token>/', views.accept_invite, name='accept_invite'),
    path('invite/check-username/', views.check_username, name='check_username'),
    path('org-tree/', views.org_tree, name='org_tree'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'core.views.csrf_failure'