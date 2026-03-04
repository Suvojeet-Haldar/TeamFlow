from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Project, Task, ActivityLog, CustomUser, Organization, Invite
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages

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

        assigned_to_id = request.POST.get("assigned_to")
        assigned_to = None
        if assigned_to_id:
            assigned_to = CustomUser.objects.filter(id=assigned_to_id).first()

        task = Task.objects.create(
            project=project,
            title=title,
            description=description,
            status=status,
            priority=priority,
            assigned_to=assigned_to,
        )

        ActivityLog.objects.create(
            user=request.user,
            project=project,
            task=task,
            action=f"created task \"{task.title}\" with status {task.status}"
        )

        return redirect("project_detail", project_id=project.id)

    activity_logs = ActivityLog.objects.filter(project=project).order_by("-timestamp")[:20]

    context = {
        "project": project,
        "columns": [
            ("Todo", Task.objects.filter(project=project, status="todo")),
            ("In Progress", Task.objects.filter(project=project, status="in_progress")),
            ("Blocked", Task.objects.filter(project=project, status="blocked")),
            ("Done", Task.objects.filter(project=project, status="done")),
        ],
        "activity_logs": activity_logs,
        "members": CustomUser.objects.filter(organization=request.user.organization),
    }
    return render(request, "core/project_detail.html", context)


@login_required
def update_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["todo", "in_progress", "blocked", "done"]:
            old_status = task.status
            task.status = new_status
            task.save()

            ActivityLog.objects.create(
                user=request.user,
                project=task.project,
                task=task,
                action=f"moved \"{task.title}\" from {old_status} to {new_status}"
            )

    return redirect("project_detail", project_id=task.project.id)

@login_required
def create_project(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")

        project = Project.objects.create(
            name=name,
            description=description,
            organization=request.user.organization,
            created_by=request.user
        )

        ActivityLog.objects.create(
            user=request.user,
            project=project,
            task=None,
            action=f"created project \"{project.name}\""
        )

        return redirect("project_detail", project_id=project.id)

    return render(request, "core/create_project.html")

def register(request):
    if request.user.is_authenticated:
        return redirect("project_list")

    error = None

    if request.method == "POST":
        org_name = request.POST.get("org_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            error = "Passwords do not match."

        elif CustomUser.objects.filter(username=username).exists():
            error = "Username already taken."

        elif Organization.objects.filter(name=org_name).exists():
            error = "An organization with that name already exists."

        else:
            org = Organization.objects.create(name=org_name)

            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                organization=org,
                role="OWNER"
            )

            login(request, user)
            return redirect("project_list")

    return render(request, "core/register.html", {"error": error})

@login_required
def invite_member(request):
    if request.user.role not in ["OWNER", "MANAGER"]:
        return redirect("project_list")

    invite_link = None
    error = None

    if request.method == "POST":
        email = request.POST.get("email")
        role = request.POST.get("role")

        if Invite.objects.filter(
            email=email,
            organization=request.user.organization,
            accepted=False
        ).exists():
            error = "An active invite already exists for this email."
        else:
            invite = Invite.objects.create(
                organization=request.user.organization,
                invited_by=request.user,
                email=email,
                role=role
            )
            invite_link = request.build_absolute_uri(
                f"/invite/accept/{invite.token}/"
            )

    return render(request, "core/invite_member.html", {
        "invite_link": invite_link,
        "error": error
    })


def accept_invite(request, token):
    invite = get_object_or_404(Invite, token=token, accepted=False)
    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            error = "Passwords do not match."

        elif CustomUser.objects.filter(username=username).exists():
            error = "Username already taken."

        else:
            user = CustomUser.objects.create_user(
                username=username,
                email=invite.email,
                password=password,
                organization=invite.organization,
                role=invite.role
            )
            invite.accepted = True
            invite.save()

            login(request, user)
            return redirect("project_list")

    return render(request, "core/accept_invite.html", {
        "invite": invite,
        "error": error
    })

def login_view(request):
    if request.user.is_authenticated:
        return redirect("project_list")

    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}! You are logged in as {user.role} at {user.organization}.")
            return redirect("project_list")
        else:
            error = "Invalid username or password."

    return render(request, "registration/login.html", {"error": error})