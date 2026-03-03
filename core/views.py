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
        "columns": [
            ("Todo", Task.objects.filter(project=project, status="todo")),
            ("In Progress", Task.objects.filter(project=project, status="in_progress")),
            ("Blocked", Task.objects.filter(project=project, status="blocked")),
            ("Done", Task.objects.filter(project=project, status="done")),
        ]
    }
    return render(request, "core/project_detail.html", context)

@login_required
def update_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["todo", "in_progress", "blocked", "done"]:
            task.status = new_status
            task.save()

    return redirect("project_detail", project_id=task.project.id)