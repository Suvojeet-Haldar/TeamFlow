from django.shortcuts import render
from .models import Project


def project_list(request):

    user = request.user

    projects = Project.objects.filter(
        organization=user.organization
    )

    return render(request, "projects/project_list.html", {
        "projects": projects
    })