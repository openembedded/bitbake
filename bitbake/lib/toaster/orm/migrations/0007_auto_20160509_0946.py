# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0006_add_cancelled_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='build',
            name='outcome',
            field=models.IntegerField(choices=[(0, 'Succeeded'), (1, 'Failed'), (2, 'In Progress'), (3, 'Cancelled')], default=2),
        ),
        migrations.AlterField(
            model_name='helptext',
            name='area',
            field=models.IntegerField(choices=[(0, 'variable')]),
        ),
        migrations.AlterField(
            model_name='layer',
            name='summary',
            field=models.TextField(null=True, help_text='One-line description of the layer', default=None),
        ),
        migrations.AlterField(
            model_name='layer_version',
            name='local_path',
            field=models.FilePathField(max_length=1024, default='/'),
        ),
        migrations.AlterField(
            model_name='layersource',
            name='sourcetype',
            field=models.IntegerField(choices=[(0, 'local'), (1, 'layerindex'), (2, 'imported')]),
        ),
        migrations.AlterField(
            model_name='logmessage',
            name='level',
            field=models.IntegerField(choices=[(0, 'info'), (1, 'warn'), (2, 'error'), (3, 'critical'), (-1, 'toaster exception')], default=0),
        ),
        migrations.AlterField(
            model_name='package',
            name='installed_name',
            field=models.CharField(max_length=100, default=''),
        ),
        migrations.AlterField(
            model_name='package_dependency',
            name='dep_type',
            field=models.IntegerField(choices=[(0, 'depends'), (1, 'depends'), (3, 'recommends'), (2, 'recommends'), (4, 'suggests'), (5, 'provides'), (6, 'replaces'), (7, 'conflicts')]),
        ),
        migrations.AlterField(
            model_name='recipe_dependency',
            name='dep_type',
            field=models.IntegerField(choices=[(0, 'depends'), (1, 'rdepends')]),
        ),
        migrations.AlterField(
            model_name='release',
            name='branch_name',
            field=models.CharField(max_length=50, default=''),
        ),
        migrations.AlterField(
            model_name='releasedefaultlayer',
            name='layer_name',
            field=models.CharField(max_length=100, default=''),
        ),
        migrations.AlterField(
            model_name='target_file',
            name='inodetype',
            field=models.IntegerField(choices=[(1, 'regular'), (2, 'directory'), (3, 'symlink'), (4, 'socket'), (5, 'fifo'), (6, 'character'), (7, 'block')]),
        ),
        migrations.AlterField(
            model_name='task',
            name='outcome',
            field=models.IntegerField(choices=[(-1, 'Not Available'), (0, 'Succeeded'), (1, 'Covered'), (2, 'Cached'), (3, 'Prebuilt'), (4, 'Failed'), (5, 'Empty')], default=-1),
        ),
        migrations.AlterField(
            model_name='task',
            name='script_type',
            field=models.IntegerField(choices=[(0, 'N/A'), (2, 'Python'), (3, 'Shell')], default=0),
        ),
        migrations.AlterField(
            model_name='task',
            name='sstate_result',
            field=models.IntegerField(choices=[(0, 'Not Applicable'), (1, 'File not in cache'), (2, 'Failed'), (3, 'Succeeded')], default=0),
        ),
    ]
