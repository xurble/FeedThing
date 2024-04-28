from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin

from django.contrib.auth.models import BaseUserManager

from feeds.models import Post, Subscription


class FTUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError('The email address must be set')

        email = FTUserManager.normalize_email(email)
        user = self.model(
                        email=email,
                        is_staff=False,
                        is_active=True,
                        **extra_fields
                    )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        u = self.create_user(email, password, **extra_fields)
        u.is_staff = True
        u.is_active = True
        u.is_superuser = True
        u.save(using=self._db)
        return u


class User(AbstractBaseUser, PermissionsMixin):

    email = models.EmailField(unique=True, blank=False)
    name = models.CharField(max_length=128, verbose_name="Full Name")
    salutation = models.CharField(max_length=128, null=True, blank=True, verbose_name="What should we call you?")

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    default_to_river = models.BooleanField(default=False, help_text="Set your default home to be a river of all your feeds.")

    USERNAME_FIELD = 'email'

    objects = FTUserManager()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        if self.salutation is None:
            return self.name
        else:
            return self.salutation


class SavedPost(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    subscription = models.ForeignKey(Subscription, null=True, on_delete=models.CASCADE)

    date_saved = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_saved']
        unique_together = (("post", "user"),)
