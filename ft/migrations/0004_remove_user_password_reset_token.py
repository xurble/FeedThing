# Generated by Django 2.2.5 on 2021-06-07 04:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ft', '0003_user_password_reset_token'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='password_reset_token',
        ),
    ]
