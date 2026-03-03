from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Project, Task


@login_required
def project_list(request):
    projects = Project.objects.filter(organization=request.user.organization)
    return render(request, "projects/project_list.html", {"projects": projects})


@login_required
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
            priority=priority,
            assigned_to=None,
        )
        return redirect("project_detail", project_id=project.id)

    context = {
        "project": project,
        "todo_tasks": Task.objects.filter(project=project, status="todo"),
        "progress_tasks": Task.objects.filter(project=project, status="in_progress"),
        "blocked_tasks": Task.objects.filter(project=project, status="blocked"),
        "done_tasks": Task.objects.filter(project=project, status="done"),
    }
    return render(request, "core/project_detail.html", context)