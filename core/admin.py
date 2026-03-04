from django.contrib import admin
from .models import Organization, CustomUser, Project, Task, ActivityLog, Invite

admin.site.register(Organization)
admin.site.register(CustomUser)
admin.site.register(Project)
admin.site.register(Task)
admin.site.register(ActivityLog)
admin.site.register(Invite)