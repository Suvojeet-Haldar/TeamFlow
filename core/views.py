from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Project, Task


@login_required
def project_list(request):

    user = request.user

    projects = Project.objects.filter(
        organization=user.organization
    )

    return render(request, "projects/project_list.html", {
        "projects": projects
    })

def project_detail(request, project_id):

    project = get_object_or_404(Project, id=project_id)

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        status = request.POST.get("status")
        priority = request.POST.get("priority")

        Task.objects.create(
            project=project,
            title=title,
            description=description,
            status=status,
            priority=priority
        )
        
    tasks = Task.objects.filter(project=project)

    context = {
        "project": project,
        "tasks": tasks
    }

    return render(request, "core/project_detail.html", context)