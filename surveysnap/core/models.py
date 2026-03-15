from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


# =========================
# Custom User Manager
# =========================
class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_admin", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_admin") is not True:
            raise ValueError("Superuser must have is_admin=True.")

        return self.create_user(email, password, **extra_fields)


# =========================
# Custom User Model
# =========================
class User(AbstractBaseUser):

    # Basic Information
    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)

    gender_choices = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    )
    gender = models.CharField(max_length=10, choices=gender_choices,default="male", null=True)

    phone_no = models.CharField(
        max_length=15,
        unique=True,
        blank=True,
        null=True
    )

    # Role Section
    role_choice = (
        ("admin", "Admin"),
        ("creator", "Survey Creator"),
        ("respondent", "Respondent"),
    )

    role = models.CharField(
        max_length=15,
        choices=role_choice,
        default="respondent" 
    )

    # Permission Fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    # Login Field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "user"

    def __str__(self):
        return self.email

    # Permission Methods
    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin