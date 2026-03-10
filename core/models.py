import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Organization(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    emp_id_counter = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    def get_emp_id_prefix(self):
        clean = ''.join(c for c in self.name.upper() if c.isalpha())
        return clean[:3] if len(clean) >= 3 else clean.ljust(3, 'X')

    def next_employee_id(self):
        self.emp_id_counter += 1
        self.save(update_fields=['emp_id_counter'])
        return f"{self.get_emp_id_prefix()}-{str(self.emp_id_counter).zfill(4)}"


class Role(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='roles'
    )
    name = models.CharField(max_length=50)
    is_default = models.BooleanField(default=False)
    is_manager_type = models.BooleanField(default=False)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('OWNER', 'Owner'),
        ('MANAGER', 'Manager'),
        ('DEVELOPER', 'Developer'),
        ('VIEWER', 'Viewer'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        related_name='users', null=True, blank=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='VIEWER')
    org_role = models.ForeignKey(
        'Role', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='members'
    )
    manager = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='direct_reports'
    )
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    employee_id = models.CharField(max_length=30, blank=True)
    joined_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.username

    def get_role_name(self):
        if self.org_role:
            return self.org_role.name
        if self.role:
            return self.role.capitalize()
        return None


class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='projects'
    )
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, related_name='created_projects'
    )
    manager = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='managed_projects'
    )
    members = models.ManyToManyField(
        CustomUser, blank=True, related_name='projects'
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SOPDocument(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='sop_documents'
    )
    name = models.CharField(max_length=255)
    sop_file = models.FileField(upload_to='sop/', null=True, blank=True)
    sop_link = models.URLField(blank=True)
    uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_sops'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} — {self.project.name}"

    def is_file(self):
        return bool(self.sop_file)

    def is_link(self):
        return bool(self.sop_link)


class Task(models.Model):
    STATUS_CHOICES = [
        ('todo', 'Todo'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('blocked', 'Blocked'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='tasks'
    )
    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_tasks'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class ActivityLog(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, related_name='activities'
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='activities'
    )
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE,
        related_name='activities', null=True, blank=True
    )
    action = models.CharField(max_length=512)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.action}"


class Invite(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invites'
    )
    invited_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, related_name='sent_invites'
    )
    email = models.EmailField()
    role = models.CharField(max_length=50)
    assigned_manager = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pending_reports'
    )
    contract_expiry = models.DateField(null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} → {self.organization.name}"