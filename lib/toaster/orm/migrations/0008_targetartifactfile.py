# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0007_auto_20160523_1446'),
    ]

    operations = [
        migrations.CreateModel(
            name='TargetArtifactFile',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('file_name', models.FilePathField()),
                ('file_size', models.IntegerField()),
                ('target', models.ForeignKey(to='orm.Target')),
            ],
        ),
    ]
