# Generated by Django 4.2.3 on 2024-02-12 07:45

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0012_source_last_read_subscription'),
        ('ft', '0004_remove_user_password_reset_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subscriptionsx', to='ft.subscription'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='source',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='subscriptionsx', to='feeds.source'),
        ),
        migrations.AlterField(
            model_name='subscription',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriber', to=settings.AUTH_USER_MODEL),
        ),
    ]
