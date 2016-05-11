# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bldcontrol', '0003_add_cancelling_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buildenvironment',
            name='bbstate',
            field=models.IntegerField(choices=[(0, 'stopped'), (1, 'started')], default=0),
        ),
        migrations.AlterField(
            model_name='buildenvironment',
            name='betype',
            field=models.IntegerField(choices=[(0, 'local')]),
        ),
        migrations.AlterField(
            model_name='buildenvironment',
            name='lock',
            field=models.IntegerField(choices=[(0, 'free'), (1, 'lock'), (2, 'running')], default=0),
        ),
        migrations.AlterField(
            model_name='buildrequest',
            name='state',
            field=models.IntegerField(choices=[(0, 'created'), (1, 'queued'), (2, 'in progress'), (3, 'completed'), (4, 'failed'), (5, 'deleted'), (6, 'cancelling'), (7, 'archive')], default=0),
        ),
    ]
