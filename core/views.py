import json
import random
import string
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import JsonResponse
from .models import (
    Project, Task, ActivityLog, CustomUser,
    Organization, Invite, Role, SOPDocument
)
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import logout as auth_logout
from django.db import models
from django.db.models import Q, Case, When, IntegerField
from django.db import models, transaction

def get_role_name(user):
    if user.org_role:
        return user.org_role.name
    if user.role:
        return user.role.capitalize()
    return None


def has_role(user, *role_names):
    return get_role_name(user) in role_names


def is_manager_type(user):
    if user.org_role:
        return user.org_role.is_manager_type
    return False


def get_all_reports(user):
    direct = list(CustomUser.objects.filter(manager=user))
    all_reports = list(direct)
    for report in direct:
        all_reports.extend(get_all_reports(report))
    return all_reports


def get_org_owner(organization):
    return (
        CustomUser.objects.filter(
            organization=organization, org_role__name="Owner"
        ).first()
        or CustomUser.objects.filter(
            organization=organization, role="OWNER"
        ).first()
    )


def user_can_access_project(user, project):
    if has_role(user, "Owner"):
        return project.organization == user.organization
    return project.members.filter(id=user.id).exists()


def generate_username_suggestions(first_name, middle_name, last_name, org):
    first = first_name.lower().strip()
    mid = middle_name.lower().strip() if middle_name else ""
    last = last_name.lower().strip()
    year2 = str(timezone.now().year)[-2:]
    mi = mid[0] if mid else ""

    candidates = [
        f"{first[0]}{last[:8]}",
        f"{first[:3]}{last[:4]}",
        f"{first[0]}.{last[:7]}",
        f"{first[:4]}{year2}",
    ]
    if mi:
        candidates += [
            f"{first[0]}{mi}{last[:6]}",
            f"{first[0]}{mi}.{last[:5]}",
        ]
    else:
        candidates += [
            f"{first[0]}{last[:6]}{year2}",
            f"{first[:5]}{last[0]}",
        ]

    suggestions = []
    seen = set()
    for c in candidates:
        c_clean = c.replace(' ', '').replace('..', '.')
        if len(c_clean) < 3:
            continue
        if c_clean not in seen and not CustomUser.objects.filter(username=c_clean).exists():
            suggestions.append(c_clean)
            seen.add(c_clean)
        if len(suggestions) == 3:
            break

    while len(suggestions) < 3:
        rand = ''.join(random.choices(string.digits, k=3))
        fallback = f"{first[0]}{last[:5]}{rand}"
        if not CustomUser.objects.filter(username=fallback).exists() and fallback not in suggestions:
            suggestions.append(fallback)

    return suggestions


@login_required
def project_list(request):
    user = request.user
    org = user.organization

    if has_role(user, "Owner"):
        active = Project.objects.filter(
            organization=org, is_completed=False
        ).select_related('manager')
        completed = Project.objects.filter(
            organization=org, is_completed=True
        ).select_related('manager')
    else:
        active = Project.objects.filter(
            organization=org, members=user, is_completed=False
        ).select_related('manager')
        completed = Project.objects.filter(
            organization=org, members=user, is_completed=True
        ).select_related('manager')

    return render(request, "projects/project_list.html", {
        "active_projects": active,
        "completed_projects": completed,
    })


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user

    if not user_can_access_project(user, project):
        return redirect("project_list")

    can_create_task = not project.is_completed and (
        has_role(user, "Owner") or is_manager_type(user)
    )
    can_manage_sop = has_role(user, "Owner") or (
        project.manager and project.manager == user
    )
    is_owner = has_role(user, "Owner")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_task" and can_create_task:
            title = request.POST.get("title")
            description = request.POST.get("description")
            status = request.POST.get("status")
            priority = request.POST.get("priority")
            assigned_to_id = request.POST.get("assigned_to")

            assigned_to = None
            if assigned_to_id:
                candidate = CustomUser.objects.filter(
                    id=assigned_to_id,
                    organization=user.organization
                ).first()
                if candidate:
                    assigned_to = candidate

            new_position = Task.objects.filter(
                project=project, status=status, priority=priority
            ).count()
            task = Task.objects.create(
                project=project,
                title=title,
                description=description,
                status=status,
                priority=priority,
                assigned_to=assigned_to,
                task_number=project.next_task_number(),
                position=new_position,
            )
            ActivityLog.objects.create(
                user=user, project=project, task=task,
                action=f"created task \"{task.title}\""
            )
            return redirect("project_detail", project_id=project.id)

        elif action == "upload_sop" and can_manage_sop:
            sop_link_names = request.POST.getlist("sop_link_name[]")
            sop_links      = request.POST.getlist("sop_link[]")
            sop_file_names = request.POST.getlist("sop_file_name[]")
            sop_files      = request.FILES.getlist("sop_file[]")

            # All names already used in this project (to avoid collisions)
            existing_names = set(
                SOPDocument.objects.filter(project=project)
                .values_list('name', flat=True)
            )
            used_this_upload = set()

            def unique_label(base):
                """Ensure the label is unique within this project."""
                name = base
                counter = 2
                while name in existing_names or name in used_this_upload:
                    name = f"{base} ({counter})"
                    counter += 1
                used_this_upload.add(name)
                return name

            # ── Links ──────────────────────────────────────────
            # Links always need a label because raw URLs in logs are
            # a security loophole (deleted link URL stays visible in log).
            # If no label given, fallback is "Link", "Link (2)", etc.
            link_num = 1
            for i, link in enumerate(sop_links):
                link = link.strip()
                if not link:
                    continue
                raw_label = sop_link_names[i].strip() if i < len(sop_link_names) else ""
                base = raw_label if raw_label else "Link"
                label = unique_label(base)
                SOPDocument.objects.create(
                    project=project, name=label,
                    sop_link=link, uploaded_by=user
                )
                ActivityLog.objects.create(
                    user=user, project=project,
                    action=f'uploaded SOP link "{label}"'
                )
                link_num += 1

            # ── Files ──────────────────────────────────────────
            # Use original filename as default — it's already descriptive.
            # Labels override if provided.
            ALLOWED_EXTS = {'pdf', 'docx', 'doc', 'xlsx', 'xls', 'xlsm'}
            for i, f in enumerate(sop_files):
                ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
                if ext not in ALLOWED_EXTS:
                    continue
                raw_label = sop_file_names[i].strip() if i < len(sop_file_names) else ""
                base = raw_label if raw_label else f.name   # original filename as default
                label = unique_label(base)
                SOPDocument.objects.create(
                    project=project, name=label,
                    sop_file=f, uploaded_by=user
                )
                ActivityLog.objects.create(
                    user=user, project=project,
                    action=f'uploaded SOP file "{label}"'
                )

            return redirect("project_detail", project_id=project.id)

        elif action == "rename_sop" and is_owner:
            doc_id = request.POST.get("doc_id")
            new_name = request.POST.get("new_name", "").strip()
            doc = SOPDocument.objects.filter(
                id=doc_id, project=project
            ).first()
            if doc and new_name:
                old_name = doc.name
                doc.name = new_name
                doc.save()
                ActivityLog.objects.create(
                    user=user, project=project,
                    action=f"renamed SOP \"{old_name}\" to \"{new_name}\""
                )
            return redirect("project_detail", project_id=project.id)

        elif action == "delete_sop" and is_owner:
            doc_id = request.POST.get("doc_id")
            doc = SOPDocument.objects.filter(
                id=doc_id, project=project
            ).first()
            if doc:
                ActivityLog.objects.create(
                    user=user, project=project,
                    action=f"deleted SOP \"{doc.name}\""
                )
                doc.delete()
            return redirect("project_detail", project_id=project.id)

    activity_logs = ActivityLog.objects.filter(
        project=project
    ).order_by("-timestamp")[:20]

    assignable_members = project.members.all()

    project_members = project.members.select_related('org_role')
    sop_documents = project.sop_documents.all().order_by('created_at')

    is_pm = project.manager and project.manager == user
    can_reorder = (has_role(user, "Owner") or bool(is_pm)) and not project.is_completed

    context = {
        "project": project,
        "can_create_task": can_create_task,
        "can_manage_sop": can_manage_sop,
        "is_owner": is_owner,
        "can_reorder": can_reorder,
        "columns": [
            ("Todo",        "todo",        Task.objects.filter(project=project, status="todo",        is_archived=False).annotate(porder=Case(When(priority='urgent',then=0),When(priority='high',then=1),When(priority='medium',then=2),When(priority='low',then=3),default=4,output_field=IntegerField())).order_by('porder', 'position')),
            ("In Progress", "in_progress", Task.objects.filter(project=project, status="in_progress", is_archived=False).annotate(porder=Case(When(priority='urgent',then=0),When(priority='high',then=1),When(priority='medium',then=2),When(priority='low',then=3),default=4,output_field=IntegerField())).order_by('porder', 'position')),
            ("Blocked",     "blocked",     Task.objects.filter(project=project, status="blocked",     is_archived=False).annotate(porder=Case(When(priority='urgent',then=0),When(priority='high',then=1),When(priority='medium',then=2),When(priority='low',then=3),default=4,output_field=IntegerField())).order_by('porder', 'position')),
            ("Done",        "done",        Task.objects.filter(project=project, status="done",        is_archived=False).order_by('-completed_at', '-id')),
        ],
        "activity_logs": activity_logs,
        "members": assignable_members,
        "project_members": project_members,
        "sop_documents": sop_documents,
    }
    archived_tasks = Task.objects.filter(
        project=project, is_archived=True
    ).order_by('-updated_at')
    context['archived_tasks'] = archived_tasks
    return render(request, "core/project_detail.html", context)


@login_required
def complete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user

    if not user_can_access_project(user, project):
        return redirect("project_list")

    is_owner = has_role(user, "Owner")
    is_project_manager = (project.manager and project.manager == user)

    if not (is_owner or is_project_manager):
        return redirect("project_detail", project_id=project.id)

    todo_tasks = Task.objects.filter(project=project, status="todo")
    inprogress_tasks = Task.objects.filter(project=project, status="in_progress")
    blocked_tasks = Task.objects.filter(project=project, status="blocked")
    errors = []
    warnings = []

    if todo_tasks.exists():
        errors.append(f"{todo_tasks.count()} task(s) still in Todo — move or remove them first.")
    if inprogress_tasks.exists():
        errors.append(f"{inprogress_tasks.count()} task(s) still In Progress — complete or move them first.")
    if blocked_tasks.exists():
        warnings.append(
            f"{blocked_tasks.count()} blocked task(s) — "
            f"{', '.join([t.title for t in blocked_tasks])} — will be recorded as-is."
        )

    if request.method == "POST" and not errors:
        project.is_completed = True
        project.completed_at = timezone.now()
        project.save()
        ActivityLog.objects.create(
            user=user, project=project, task=None,
            action=f"marked project \"{project.name}\" as completed"
        )
        return redirect("project_list")

    return render(request, "core/complete_project.html", {
        "project": project,
        "errors": errors,
        "warnings": warnings,
    })


@login_required
def reactivate_project(request, project_id):
    if not has_role(request.user, "Owner"):
        return redirect("project_list")

    project = get_object_or_404(
        Project, id=project_id,
        organization=request.user.organization,
        is_completed=True
    )

    if request.method == "POST":
        project.is_completed = False
        project.completed_at = None
        project.save()
        ActivityLog.objects.create(
            user=request.user, project=project, task=None,
            action=f"reactivated project \"{project.name}\""
        )
        return redirect("project_list")

    return render(request, "core/reactivate_project.html", {"project": project})


@login_required
def update_task_status(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if not user_can_access_project(user, task.project):
        return redirect("project_list")

    if task.project.is_completed and not has_role(user, "Owner"):
        return redirect("project_detail", project_id=task.project.id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in ["todo", "in_progress", "blocked", "done"]:
            can_update = (
                task.assigned_to == user or
                has_role(user, "Owner") or
                is_manager_type(user)
            )
            if can_update:
                old_status = task.status
                task.status = new_status
                if new_status == "done":
                    task.completed_at = timezone.now()
                elif old_status == "done":
                    task.completed_at = None
                now = timezone.now()
                if new_status == "todo":
                    task.moved_to_todo_at = now
                elif new_status == "in_progress":
                    task.moved_to_inprogress_at = now
                elif new_status == "blocked":
                    task.moved_to_blocked_at = now
                task.save()
                ActivityLog.objects.create(
                    user=user, project=task.project, task=task,
                    action=f"moved \"{task.title}\" from {old_status} to {new_status}"
                )
    return redirect("project_detail", project_id=task.project.id)


@login_required
def create_project(request):
    if not has_role(request.user, "Owner"):
        return redirect("project_list")

    org_managers = CustomUser.objects.filter(
        organization=request.user.organization
    ).filter(Q(org_role__is_manager_type=True) | Q(role="OWNER"))

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        manager_id = request.POST.get("manager_id")

        manager = None
        if manager_id:
            manager = CustomUser.objects.filter(
                Q(org_role__is_manager_type=True) | Q(role="OWNER"),
                id=manager_id,
                organization=request.user.organization,
            ).first()

        project = Project.objects.create(
            name=name,
            description=description,
            organization=request.user.organization,
            created_by=request.user,
            manager=manager
        )
        project.members.add(request.user)
        if manager:
            project.members.add(manager)

        ActivityLog.objects.create(
            user=request.user, project=project, task=None,
            action=f"created project \"{project.name}\""
        )
        return redirect("project_detail", project_id=project.id)

    return render(request, "core/create_project.html", {"org_managers": org_managers})


@login_required
def assign_project_manager(request, project_id):
    if not has_role(request.user, "Owner"):
        return redirect("project_list")

    project = get_object_or_404(
        Project, id=project_id,
        organization=request.user.organization
    )
    org_managers = CustomUser.objects.filter(
        organization=request.user.organization
    ).filter(Q(org_role__is_manager_type=True) | Q(role="OWNER"))

    if request.method == "POST":
        manager_id = request.POST.get("manager_id")
        if manager_id:
            manager = CustomUser.objects.filter(
                Q(org_role__is_manager_type=True) | Q(role="OWNER"),
                id=manager_id,
                organization=request.user.organization,
            ).first()
            project.manager = manager
            if manager:
                project.members.add(manager)
                for member in project.members.all():
                    if not has_role(member, "Owner") and not is_manager_type(member):
                        member.manager = manager
                        member.save()
        else:
            project.manager = None
        project.save()
        return redirect("project_list")

    return render(request, "core/assign_project_manager.html", {
        "project": project,
        "org_managers": org_managers,
    })


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
            emp_id = org.next_employee_id()

            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                organization=org,
                role="OWNER",
                org_role=owner_role,
                employee_id=emp_id,
                joined_date=timezone.now().date()
            )

            login(request, user)
            messages.success(
                request,
                f"Welcome, {user.username}! Your organization \"{org.name}\" has been created."
            )
            return redirect("project_list")

    return render(request, "core/register.html", {"error": error})


# REPLACE the entire invite_member function in core/views.py

@login_required
def invite_member(request):
    if not has_role(request.user, "Owner"):
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
        contract_expiry = request.POST.get("contract_expiry") or None

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
                assigned_manager=manager,
                contract_expiry=contract_expiry,
                expires_at=timezone.now() + timedelta(days=7),
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


def check_username(request):
    username = request.GET.get("username", "").strip()
    taken = CustomUser.objects.filter(username=username).exists()
    return JsonResponse({"taken": taken})


def suggest_usernames(request):
    first = request.GET.get("first", "").strip()
    last = request.GET.get("last", "").strip()
    if not first and not last:
        return JsonResponse({"suggestions": []})
    suggestions = generate_username_suggestions(first, last, None)
    return JsonResponse({"suggestions": suggestions})


def accept_invite(request, token):
    invite = get_object_or_404(Invite, token=token, accepted=False)
    if invite.is_expired:
        return render(request, 'core/invite_expired.html', {'invite': invite})

    error = None

    if request.method == "POST":
        step = request.POST.get("step", "1")
        first_name = request.POST.get("first_name", "").strip()
        middle_name = request.POST.get("middle_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()

        if step == "1":
            if not first_name or not last_name:
                error = "First and last name are required."
                return render(request, "core/accept_invite.html", {
                    "invite": invite, "error": error, "step": "1"
                })
            suggestions = generate_username_suggestions(
                first_name, middle_name, last_name, invite.organization
            )
            return render(request, "core/accept_invite.html", {
                "invite": invite,
                "suggestions": suggestions,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "step": "2",
            })

        elif step == "2":
            username = request.POST.get("username", "").strip()
            password = request.POST.get("password")
            confirm_password = request.POST.get("confirm_password")
            dob = request.POST.get("dob") or None
            phone = request.POST.get("phone", "")
            profile_photo = request.FILES.get("profile_photo")

            if not username:
                error = "Please choose a username."
            elif CustomUser.objects.filter(username=username).exists():
                error = "Username already taken."
            elif password != confirm_password:
                error = "Passwords do not match."
            else:
                invited_role = Role.objects.filter(
                    organization=invite.organization,
                    name__iexact=invite.role
                ).first()
                emp_id = invite.organization.next_employee_id()
                user = CustomUser.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=invite.email,
                    password=password,
                    organization=invite.organization,
                    role=invite.role.upper(),
                    org_role=invited_role,
                    manager=invite.assigned_manager,
                    dob=dob,
                    phone=phone,
                    employee_id=emp_id,
                    joined_date=timezone.now().date(),
                    expiry_date=invite.contract_expiry
                )
                # Handle cropped photo (base64) or raw file
                cropped_data = request.POST.get("cropped_photo", "").strip()
                if cropped_data and cropped_data.startswith("data:image"):
                    import base64, uuid as _uuid
                    from django.core.files.base import ContentFile
                    fmt, imgstr = cropped_data.split(';base64,')
                    ext = fmt.split('/')[-1]
                    img_data = ContentFile(
                        base64.b64decode(imgstr),
                        name=f"profile_{_uuid.uuid4().hex}.{ext}"
                    )
                    user.profile_photo = img_data
                    user.save()
                elif profile_photo:
                    user.profile_photo = profile_photo
                    user.save()
                invite.accepted = True
                invite.save()
                login(request, user)
                return redirect("project_list")

            suggestions = generate_username_suggestions(
                first_name, middle_name, last_name, invite.organization
            )
            return render(request, "core/accept_invite.html", {
                "invite": invite,
                "error": error,
                "suggestions": suggestions,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "step": "2",
            })

    return render(request, "core/accept_invite.html", {
        "invite": invite, "error": None, "step": "1"
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
            messages.success(
                request,
                f"Welcome back, {user.username}! "
                f"You are logged in as {get_role_name(user)} at {user.organization}."
            )
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
            is_manager_type_flag = request.POST.get("is_manager_type") == "on"
            if not name:
                error = "Role name cannot be empty."
            elif Role.objects.filter(
                organization=request.user.organization, name__iexact=name
            ).exists():
                error = f"Role '{name}' already exists."
            else:
                Role.objects.create(
                    organization=request.user.organization,
                    name=name,
                    is_default=False,
                    is_manager_type=is_manager_type_flag
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
                    error = (
                        f"Cannot delete \"{role.name}\" — "
                        f"the following members still have this role: {user_list}. "
                        f"Reassign them first."
                    )
                else:
                    role.delete()
                    return redirect("org_settings")

    return render(request, "core/org_settings.html", {"roles": roles, "error": error})


@login_required
def team(request):
    user = request.user
    user_role = get_role_name(user)
    org = user.organization

    if not (has_role(user, "Owner") or is_manager_type(user)):
        return redirect("project_list")

    org_owner = get_org_owner(org)

    if has_role(user, "Owner"):
        from django.db.models import Q
        direct_reports = CustomUser.objects.filter(
            organization=org
        ).exclude(id=user.id).filter(
            Q(manager=user) | Q(manager__isnull=True)
        ).exclude(
            org_role__name="Owner"
        ).exclude(
            role="OWNER"
        ).select_related('org_role', 'manager')

        direct_report_ids = set(direct_reports.values_list('id', flat=True))

        all_members = CustomUser.objects.filter(
            organization=org
        ).exclude(id=user.id).exclude(
            id__in=direct_report_ids
        ).exclude(
            org_role__name="Owner"
        ).exclude(
            role="OWNER"
        ).select_related('org_role', 'manager')
    else:
        direct_reports = CustomUser.objects.filter(
            manager=user, organization=org
        ).select_related('org_role', 'manager')
        all_members = None

    return render(request, "core/team.html", {
        "direct_reports": direct_reports,
        "all_members": all_members,
        "user_role": user_role,
        "org_owner": org_owner,
    })


@login_required
def assign_manager(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )
    all_reports = get_all_reports(member)
    excluded_ids = [member.id] + [u.id for u in all_reports]

    member_projects = member.projects.filter(is_completed=False)
    if member_projects.exists():
        org_managers = CustomUser.objects.filter(
            organization=request.user.organization,
            org_role__is_manager_type=True,
            projects__in=member_projects
        ).exclude(id__in=excluded_ids).distinct()
    else:
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
def assign_project(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )
    if member == request.user:
        return redirect("team")

    org_projects = Project.objects.filter(
        organization=request.user.organization, is_completed=False
    )
    current_projects = member.projects.filter(organization=request.user.organization)

    if request.method == "POST":
        project_id = request.POST.get("project_id")
        action = request.POST.get("action")
        if project_id:
            project = Project.objects.filter(
                id=project_id, organization=request.user.organization
            ).first()
            if project:
                if action == "add":
                    project.members.add(member)
                    if project.manager and not has_role(member, "Owner"):
                        member.manager = project.manager
                        member.save()
                    ActivityLog.objects.create(
                        user=request.user, project=project,
                        action=f"added {member.username} to project"
                    )
                elif action == "remove":
                    project.members.remove(member)
                    ActivityLog.objects.create(
                        user=request.user, project=project,
                        action=f"removed {member.username} from project"
                    )
        return redirect("team")

    return render(request, "core/assign_project.html", {
        "member": member,
        "org_projects": org_projects,
        "current_projects": current_projects,
    })


@login_required
def set_expiry_date(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )
    if request.method == "POST":
        expiry = request.POST.get("expiry_date") or None
        member.expiry_date = expiry
        member.save()
    return redirect("member_card", user_id=member.id)


@login_required
def member_card(request, user_id):
    viewer = request.user
    org = viewer.organization

    try:
        member = CustomUser.objects.get(id=user_id, organization=org)
    except CustomUser.DoesNotExist:
        return render(request, "core/access_denied.html", status=403)

    is_own_page = (member == viewer)

    if not is_own_page:
        if has_role(viewer, "Owner"):
            pass  # owners see all
        elif is_manager_type(viewer):
            # Managers see: direct reports + members of projects they manage
            direct_report_ids = set(
                CustomUser.objects.filter(
                    manager=viewer, organization=org
                ).values_list('id', flat=True)
            )
            managed_project_member_ids = set(
                CustomUser.objects.filter(
                    projects__manager=viewer,
                    organization=org
                ).values_list('id', flat=True)
            )
            visible_ids = direct_report_ids | managed_project_member_ids | {viewer.id}
            if member.id not in visible_ids:
                return render(request, "core/access_denied.html", status=403)
        else:
            # Regular employees: can only see own profile and their direct manager
            is_viewing_own_manager = (
                viewer.manager and viewer.manager.id == member.id
            )
            if not is_viewing_own_manager:
                return render(request, "core/access_denied.html", status=403)

    org_owner = get_org_owner(org)
    is_direct_manager = (member.manager == viewer)
    viewer_is_own_manager = (
        not is_own_page and
        viewer.manager and
        viewer.manager.id == member.id
    )

    # Sensitive fields: owner + self + direct manager only
    can_see_expiry = (
        has_role(viewer, "Owner") or
        is_own_page or
        is_direct_manager
    )
    # When viewing your manager: hide their sensitive fields
    viewing_manager_limited = viewer_is_own_manager and not has_role(viewer, "Owner")

    user_role = get_role_name(viewer)

    return render(request, "core/member_card.html", {
        "member": member,
        "org_owner": org_owner,
        "is_own_page": is_own_page,
        "can_see_expiry": can_see_expiry,
        "user_role": user_role,
        "viewing_manager_limited": viewing_manager_limited,
    })


@login_required
def edit_profile(request):
    user = request.user

    if request.method == "POST":
        dob = request.POST.get("dob") or None
        phone = request.POST.get("phone", "")
        profile_photo = request.FILES.get("profile_photo")
        cropped_data = request.POST.get("cropped_photo", "").strip()

        user.dob = dob
        user.phone = phone

        if cropped_data and cropped_data.startswith("data:image"):
            import base64, uuid as _uuid
            from django.core.files.base import ContentFile
            fmt, imgstr = cropped_data.split(';base64,')
            ext = fmt.split('/')[-1]
            img_data = ContentFile(
                base64.b64decode(imgstr),
                name=f"profile_{_uuid.uuid4().hex}.{ext}"
            )
            user.profile_photo = img_data
        elif profile_photo:
            user.profile_photo = profile_photo

        if 'profile_photo' in request.FILES:
            photo = request.FILES['profile_photo']
            if photo.size > 5 * 1024 * 1024:
                error = "Profile photo must be under 5MB."
                # don't save

        user.save()
        return redirect("member_card", user_id=user.id)

    return render(request, "core/edit_profile.html", {})


@login_required
def reassign_role(request, user_id):
    if not has_role(request.user, "Owner"):
        return redirect("team")

    member = get_object_or_404(
        CustomUser, id=user_id, organization=request.user.organization
    )
    if member == request.user:
        return redirect("team")

    org_roles = Role.objects.filter(
        organization=request.user.organization
    ).exclude(name="Owner")

    if request.method == "POST":
        role_id = request.POST.get("role_id")
        new_role = Role.objects.filter(
            id=role_id, organization=request.user.organization
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
        CustomUser, id=user_id, organization=request.user.organization
    )
    if member == request.user:
        return redirect("team")

    if request.method == "POST":
        CustomUser.objects.filter(
            manager=member, organization=request.user.organization
        ).update(manager=None)
        member.delete()
        return redirect("team")

    return render(request, "core/confirm_remove.html", {"member": member})

# ── Landing page ───────────────────────────────────────────────────────────────
def landing(request):
    if request.user.is_authenticated:
        return redirect('project_list')
    return render(request, 'core/landing.html')

# ── CSRF failure — graceful redirect ──────────────────────────────────────────
def csrf_failure(request, reason=""):
    from django.shortcuts import redirect
    return redirect('/login/?csrf_error=1')

# ── Org Tree ───────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
#  REPLACE the existing org_tree view in core/views.py with this.
#  Also add this import at the top if not already present:
#  from django.db import models
from django.db.models import Q
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
#  REPLACE the org_tree view in core/views.py with this.
# ══════════════════════════════════════════════════════════

@login_required
def org_tree(request):
    user = request.user
    org  = user.organization

    # Get the org owner (always at top of every chain)
    owner = CustomUser.objects.filter(organization=org).filter(
        models.Q(role='OWNER') | models.Q(org_role__name__iexact='Owner')
    ).first()

    def build_node(u, depth=0):
        if depth > 12:
            return {'user': u, 'reports': []}
        # Direct reports: anyone whose manager = u
        direct = list(
            CustomUser.objects.filter(manager=u, organization=org)
            .order_by('username')
        )
        # For the owner node: also pull in anyone with no manager
        # (they implicitly report to the owner)
        if u == owner:
            no_manager = list(
                CustomUser.objects.filter(
                    organization=org, manager__isnull=True
                ).exclude(id=owner.id).order_by('username')
            )
            # Merge, deduplicate
            seen = {r.id for r in direct}
            for nm in no_manager:
                if nm.id not in seen:
                    direct.append(nm)
            direct.sort(key=lambda x: x.username)

        return {
            'user': u,
            'reports': [build_node(r, depth + 1) for r in direct]
        }

    def get_chain_up(u):
        """Walk manager chain upward. Always append owner at top if not already there."""
        chain, cursor, visited = [], u.manager, set()
        while cursor and cursor.id not in visited:
            visited.add(cursor.id)
            chain.insert(0, cursor)
            cursor = cursor.manager
        # If owner not in chain, prepend them
        if owner and (not chain or chain[0].id != owner.id) and u.id != owner.id:
            chain.insert(0, owner)
        return chain

    is_owner   = has_role(user, 'Owner')
    is_manager = is_manager_type(user)

    if is_owner:
        tree_nodes = [build_node(owner)]
        chain_up   = []
    else:
        tree_nodes = [build_node(user)]
        chain_up   = get_chain_up(user)

    return render(request, 'core/org_tree.html', {
        'tree_nodes': tree_nodes,
        'chain_up':   chain_up,
        'is_owner':   is_owner,
        'is_manager': is_manager,
    })

# ── Register — 2-step with username suggestions for owner ─────────────────────
def register_view(request):
    error = None
    if request.method == 'POST':
        step = request.POST.get('step', '1')
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        org_name   = request.POST.get('org_name', '').strip()

        if step == '1':
            if not first_name or not last_name or not org_name:
                error = 'Organization name, first name, and last name are required.'
                return render(request, 'core/register.html',
                              {'error': error, 'step': '1'})
            suggestions = generate_username_suggestions(first_name, middle_name, last_name, None)
            return render(request, 'core/register.html', {
                'step': '2',
                'first_name': first_name,
                'middle_name': middle_name,
                'last_name': last_name,
                'org_name': org_name,
                'suggestions': suggestions,
            })

        elif step == '2':
            username         = request.POST.get('username', '').strip()
            email            = request.POST.get('email', '').strip()
            password         = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            dob              = request.POST.get('dob') or None
            phone            = request.POST.get('phone', '')
            profile_photo    = request.FILES.get('profile_photo')
            cropped_data     = request.POST.get('cropped_photo', '').strip()

            if not username:
                error = 'Please choose a username.'
            elif CustomUser.objects.filter(username=username).exists():
                error = 'Username already taken.'
            elif password != confirm_password:
                error = 'Passwords do not match.'
            elif Organization.objects.filter(name__iexact=org_name).exists():
                error = f'An organization named "{org_name}" already exists.'
            else:
                org = Organization.objects.create(name=org_name)
                # Create default roles
                Role.objects.bulk_create([
                    Role(name='Owner',     organization=org, is_default=True, is_manager_type=False),
                    Role(name='Manager',   organization=org, is_default=True, is_manager_type=True),
                    Role(name='Developer', organization=org, is_default=True, is_manager_type=False),
                    Role(name='Viewer',    organization=org, is_default=True, is_manager_type=False),
                ])
                owner_role = Role.objects.get(organization=org, name='Owner')
                emp_id = org.next_employee_id()
                user = CustomUser.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    organization=org,
                    role='OWNER',
                    org_role=owner_role,
                    dob=dob,
                    phone=phone,
                    employee_id=emp_id,
                    joined_date=timezone.now().date(),
                )
                # Handle photo
                if cropped_data and cropped_data.startswith('data:image'):
                    import base64, uuid as _uuid
                    from django.core.files.base import ContentFile
                    fmt, imgstr = cropped_data.split(';base64,')
                    ext = fmt.split('/')[-1]
                    user.profile_photo = ContentFile(
                        base64.b64decode(imgstr),
                        name=f'profile_{_uuid.uuid4().hex}.{ext}'
                    )
                    user.save()
                elif profile_photo:
                    user.profile_photo = profile_photo
                    user.save()

                login(request, user)
                return redirect('project_list')

            suggestions = generate_username_suggestions(first_name, middle_name, last_name, None)
            return render(request, 'core/register.html', {
                'step': '2', 'error': error,
                'first_name': first_name, 'middle_name': middle_name,
                'last_name': last_name, 'org_name': org_name,
                'suggestions': suggestions,
            })

    return render(request, 'core/register.html', {'step': '1'})

@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if not user_can_access_project(user, task.project):
        return redirect("project_list")

    is_owner = has_role(user, "Owner")
    is_pm = task.project.manager and task.project.manager == user
    is_assignee = task.assigned_to == user
    can_edit_task = is_owner or is_pm

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "edit_description" and can_edit_task:
            new_description = request.POST.get("description", "").strip()
            old_description = task.description
            task.description = new_description
            task.save()
            ActivityLog.objects.create(
                user=user, project=task.project, task=task,
                action=f"updated description of \"{task.title}\""
            )
            return redirect("task_detail", task_id=task.id)
        elif action == "edit_title" and can_edit_task:
            new_title = request.POST.get("title", "").strip()
            if new_title:
                old_title = task.title
                task.title = new_title
                task.save()
                ActivityLog.objects.create(
                    user=user, project=task.project, task=task,
                    action=f"renamed task \"{old_title}\" to \"{new_title}\""
                )
            return redirect("task_detail", task_id=task.id)

        elif action == "update_status" and is_assignee:
            new_status = request.POST.get("status")
            if new_status in ["todo", "in_progress", "blocked", "done"]:
                old_status = task.status
                task.status = new_status
                if new_status == "done":
                    task.completed_at = timezone.now()
                elif old_status == "done":
                    task.completed_at = None
                now = timezone.now()
                if new_status == "todo":
                    task.moved_to_todo_at = now
                elif new_status == "in_progress":
                    task.moved_to_inprogress_at = now
                elif new_status == "blocked":
                    task.moved_to_blocked_at = now
                task.save()
                ActivityLog.objects.create(
                    user=user, project=task.project, task=task,
                    action=f"moved \"{task.title}\" from {old_status} to {new_status}"
                )
            return redirect("task_detail", task_id=task.id)

    return render(request, "core/task_detail.html", {
        "task": task,
        "project": task.project,
        "can_edit_task": can_edit_task,
        "is_assignee": is_assignee,
        "is_owner": is_owner,
    })

@login_required
def reorder_task(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if not user_can_access_project(user, task.project):
        return JsonResponse({'error': 'Access denied'}, status=403)

    is_owner = has_role(user, 'Owner')
    is_pm = task.project.manager and task.project.manager == user

    if not (is_owner or is_pm):
        return JsonResponse({'error': 'Permission denied — owner or PM only'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    ordered_ids = [int(x) for x in data.get('ordered_ids', [])]
    column = data.get('column')
    new_priority = data.get('new_priority')

    if column not in ['todo', 'in_progress', 'blocked']:
        return JsonResponse({'error': 'Invalid column'}, status=400)

    PRIORITY_ORDER = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}

    tasks_map = {t.id: t for t in Task.objects.filter(
        project=task.project, status=column, id__in=ordered_ids
    )}

    if len(tasks_map) != len(ordered_ids):
        return JsonResponse({'error': 'Task ID mismatch'}, status=400)

    # Apply new priority in memory for validation
    if new_priority and new_priority in PRIORITY_ORDER:
        tasks_map[task.id].priority = new_priority

    # Validate priority order is non-decreasing (urgent first)
    prev_p = -1
    for tid in ordered_ids:
        p = PRIORITY_ORDER.get(tasks_map[tid].priority, 99)
        if p < prev_p:
            return JsonResponse({'error': 'Priority order violated'}, status=400)
        prev_p = p

    with transaction.atomic():
        for idx, tid in enumerate(ordered_ids):
            t = tasks_map[tid]
            t.position = idx
            update_fields = ['position']
            if tid == task.id and new_priority and new_priority in PRIORITY_ORDER:
                t.priority = new_priority
                update_fields.append('priority')
            t.save(update_fields=update_fields)

        if new_priority and new_priority in PRIORITY_ORDER:
            ActivityLog.objects.create(
                user=user, project=task.project, task=task,
                action=f'changed priority of "{task.title}" to {new_priority}'
            )

    return JsonResponse({'ok': True})

@login_required
def archive_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    user = request.user

    if not user_can_access_project(user, task.project):
        return redirect('project_list')

    if not has_role(user, 'Owner'):
        return redirect('task_detail', task_id=task.id)

    if request.method == 'POST':
        task.is_archived = True
        task.save(update_fields=['is_archived'])
        ActivityLog.objects.create(
            user=user, project=task.project, task=task,
            action=f'archived "{task.title}"'
        )
    return redirect('project_detail', project_id=task.project.id)

def custom_logout(request):
    auth_logout(request)
    return redirect('/')