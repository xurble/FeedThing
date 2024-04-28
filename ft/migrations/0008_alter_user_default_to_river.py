# Generated by Django 5.0.4 on 2024-04-28 08:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ft', '0007_user_default_to_river'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='default_to_river',
            field=models.BooleanField(default=False, help_text='Set your default home to be a river of all your feeds.'),
        ),
    ]
