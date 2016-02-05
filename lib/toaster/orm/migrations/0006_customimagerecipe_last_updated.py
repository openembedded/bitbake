# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0005_auto_20160118_1055'),
    ]

    operations = [
        migrations.AddField(
            model_name='customimagerecipe',
            name='last_updated',
            field=models.DateTimeField(default=None, null=True),
        ),
    ]
