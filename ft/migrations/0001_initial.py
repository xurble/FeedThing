# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-21 20:08
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('name', models.CharField(max_length=128, verbose_name=b'Full Name')),
                ('salutation', models.CharField(blank=True, max_length=128, null=True, verbose_name=b'What should we call you?')),
                ('is_active', models.BooleanField(default=True)),
                ('is_admin', models.BooleanField(default=False)),
                ('is_staff', models.BooleanField(default=False)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'user',
                'verbose_name_plural': 'users',
            },
        ),
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.TextField()),
                ('body', models.TextField()),
                ('link', models.CharField(blank=True, max_length=512, null=True)),
                ('found', models.DateTimeField()),
                ('created', models.DateTimeField(db_index=True)),
                ('guid', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('author', models.CharField(blank=True, max_length=255, null=True)),
                ('index', models.IntegerField(db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('siteURL', models.CharField(blank=True, max_length=255, null=True)),
                ('feedURL', models.CharField(max_length=255)),
                ('lastPolled', models.DateTimeField(blank=True, max_length=255, null=True)),
                ('duePoll', models.DateTimeField()),
                ('ETag', models.CharField(blank=True, max_length=255, null=True)),
                ('lastModified', models.CharField(blank=True, max_length=255, null=True)),
                ('lastResult', models.CharField(blank=True, max_length=255, null=True)),
                ('interval', models.PositiveIntegerField(default=400)),
                ('lastSuccess', models.DateTimeField(null=True)),
                ('lastChange', models.DateTimeField(null=True)),
                ('live', models.BooleanField(default=True)),
                ('status_code', models.PositiveIntegerField(default=0)),
                ('last302url', models.CharField(default=b' ', max_length=255)),
                ('last302start', models.DateTimeField(auto_now_add=True)),
                ('maxIndex', models.IntegerField(default=0)),
                ('num_subs', models.IntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lastRead', models.IntegerField(default=0)),
                ('isRiver', models.BooleanField(default=False)),
                ('name', models.CharField(max_length=255)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ft.Subscription')),
                ('source', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='ft.Source')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='post',
            name='source',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ft.Source'),
        ),
    ]
