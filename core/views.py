from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Project, Task, ActivityLog, CustomUser, Organization, Invite, Role
from django.contrib.auth import login, authenticate
from django.contrib import messages


def get_role_name(user):
    if user.org_role:
        return user.org_role.name
    if user.role:
        return user.role.capitalize()
    return None


def has_role(user, *role_names):
    return get_role_name(user) in role_names


def get_all_reports(user):
    """Recursively get all users who report up to this user."""
    direct = list(CustomUser.objects.filter(manager=user))
    all_reports = list(direct)
    for report in direct:
        all_reports.extend(get_all_reports(report))
    return all_reports


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

            for role_name in ['Owner', 'Manager', 'Developer', 'Viewer']:
                Role.objects.create(
                    organization=org,
                    name=role_name,
                    is_default=True,
                    is_manager_type=(role_name == 'Manager')
                )

            owner_role = Role.objects.get(organization=org, name='Owner')

            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                organization=org,
                role="OWNER",
                org_role=owner_role
            )

            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your organization \"{org.name}\" has been created.")
            return redirect("project_list")

    return render(request, "core/register.html", {"error": error})


@login_required
def invite_member(request):
    if not has_role(request.user, "Owner", "Manager"):
        return redirect("project_list")

    invite_link = None
    error = None

    org_roles = Role.objects.filter(
        organization=request.user.organization
    ).exclude(name="Owner")

    org_managers = CustomUser.objects.filter(
        organization=request.user.organization,
        org_role__is_manager_type=True
    )

    if request.method == "POST":
        email = request.POST.get("email")
        role_id = request.POST.get("role_id")
        manager_id = request.POST.get("manager_id")

        selected_role = Role.objects.filter(
            id=role_id,
            organization=request.user.organization
        ).first()

        if not selected_role:
            error = "Invalid role selected."
        elif Invite.objects.filter(
            email=email,
            organization=request.user.organization,
            accepted=False
        ).exists():
            error = "An active invite already exists for this email."
        else:
            manager = None
            if manager_id:
                manager = CustomUser.objects.filter(
                    id=manager_id,
                    organization=request.user.organization,
                    org_role__is_manager_type=True
                ).first()

            invite = Invite.objects.create(
                organization=request.user.organization,
                invited_by=request.user,
                email=email,
                role=selected_role.name,
                assigned_manager=manager
            )
            invite_link = request.build_absolute_uri(
                f"/invite/accept/{invite.token}/"
            )

    return render(request, "core/invite_member.html", {
        "invite_link": invite_link,
        "error": error,
        "org_roles": org_roles,
        "org_managers": org_managers,
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
            invited_role = Role.objects.filter(
                organization=invite.organization,
                name__iexact=invite.role
            ).first()

            user = CustomUser.objects.create_user(
                username=username,
                email=invite.email,
                password=password,
                organization=invite.organization,
                role=invite.role.upper(),
                org_role=invited_role,
                manager=invite.assigned_manager
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
            messages.success(request, f"Welcome back, {user.username}! You are logged in as {get_role_name(user)} at {user.organization}.")
            return redirect("project_list")
        else:
            error = "Invalid username or password."

    return render(request, "registration/login.html", {"error": error})


@login_required
def org_settings(request):
    if not has_role(request.user, "Owner"):
        return redirect("project_list")

    error = None
    roles = Role.objects.filter(organization=request.user.organization)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add":
            name = request.POST.get("role_name", "").strip()
            is_manager_type = request.POST.get("is_manager_type") == "on"
            if not name:
                error = "Role name cannot be empty."
            elif Role.objects.filter(
                organization=request.user.organization,
                name__iexact=name
            ).exists():
                error = f"Role '{name}' already exists."
            else:
                Role.objects.create(
                    organization=request.user.organization,
                    name=name,
                    is_default=False,
                    is_manager_type=is_manager_type
                )
                return redirect("org_settings")

        elif action == "toggle_manager_type":
            role_id = request.POST.get("role_id")
            role = Role.objects.filter(
                id=role_id,
                organization=request.user.organization
            ).exclude(name="Owner").first()
            if role:
                role.is_manager_type = not role.is_manager_type
                role.save()
            return redirect("org_settings")

        elif action == "delete":
            role_id = request.POST.get("role_id")
            role = Role.objects.filter(
                id=role_id,
                organization=request.user.organization,
                is_default=False
            ).first()

            if role:
                users_with_role = CustomUser.objects.filter(org_role=role)
                if users_with_role.exists():
                    user_list = ", ".join([u.username for u in users_with_role])
                    error = f"Cannot delete \"{role.name}\" — the following members still have this role: {user_list}. Reassign them first."
                else:
                    role.delete()
                    return redirect("org_settings")

    return render(request, "core/org_settings.html", {
        "roles": roles,
        "error": error,
    })


@login_required
def team(request):
    org = request.user.organization
    user_role = get_role_name(request.user)

    if user_role == "Owner":
        all_members = CustomUser.objects.filter(
            organization=org
        ).select_related('org_role', 'manager')
    else:
        all_members = CustomUser.objects.filter(
            organization=org
        ).select_related('org_role', 'manager')

    direct_reports = CustomUser.objects.filter(
        manager=request.user,
        organization=org
    ).select_related('org_role')

    org_owner = CustomUser.objects.filter(
        organization=org,
        org_role__name="Owner"
    ).first()

    if not org_owner:
        org_owner = CustomUser.objects.filter(
            organization=org,
            role="OWNER"
        ).first()

    return render(request, "core/team.html", {
        "all_members": all_members,
        "direct_reports": direct_reports,
        "user_role": user_role,
        "org_owner": org_owner,
    })


@login_required
def assign_manager(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser,
        id=user_id,
        organization=request.user.organization
    )

    all_reports = get_all_reports(member)
    excluded_ids = [member.id] + [u.id for u in all_reports]

    org_managers = CustomUser.objects.filter(
        organization=request.user.organization,
        org_role__is_manager_type=True
    ).exclude(id__in=excluded_ids)

    if request.method == "POST":
        manager_id = request.POST.get("manager_id")
        if manager_id:
            manager = CustomUser.objects.filter(
                id=manager_id,
                organization=request.user.organization,
                org_role__is_manager_type=True
            ).exclude(id__in=excluded_ids).first()
            member.manager = manager
        else:
            member.manager = None
        member.save()
        return redirect("team")

    return render(request, "core/assign_manager.html", {
        "member": member,
        "org_managers": org_managers,
    })


@login_required
def reassign_role(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser,
        id=user_id,
        organization=request.user.organization
    )

    if member == request.user:
        return redirect("team")

    org_roles = Role.objects.filter(
        organization=request.user.organization
    ).exclude(name="Owner")

    if request.method == "POST":
        role_id = request.POST.get("role_id")
        new_role = Role.objects.filter(
            id=role_id,
            organization=request.user.organization
        ).exclude(name="Owner").first()

        if new_role:
            member.org_role = new_role
            member.role = new_role.name.upper()
            member.save()
        return redirect("team")

    return render(request, "core/reassign_role.html", {
        "member": member,
        "org_roles": org_roles,
    })


@login_required
def remove_member(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser,
        id=user_id,
        organization=request.user.organization
    )

    if member == request.user:
        return redirect("team")

    if request.method == "POST":
        CustomUser.objects.filter(
            manager=member,
            organization=request.user.organization
        ).update(manager=None)
        member.delete()
        return redirect("team")

    return render(request, "core/confirm_remove.html", {"member": member})