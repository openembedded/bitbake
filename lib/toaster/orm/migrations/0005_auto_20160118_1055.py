# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orm', '0004_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customimagerecipe',
            name='recipe_ptr',
            field=models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='orm.Recipe'),
        ),
    ]
