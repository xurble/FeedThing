# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-28 15:29
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ft', '0004_webproxy'),
    ]

    operations = [
        migrations.RenameField(
            model_name='source',
            old_name='duePoll',
            new_name='due_poll',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='ETag',
            new_name='etag',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='feedURL',
            new_name='feed_url',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='lastChange',
            new_name='last_change',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='lastModified',
            new_name='last_modified',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='lastPolled',
            new_name='last_polled',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='lastResult',
            new_name='last_result',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='lastSuccess',
            new_name='last_success',
        ),
        migrations.RenameField(
            model_name='source',
            old_name='siteURL',
            new_name='site_url',
        ),
    ]
