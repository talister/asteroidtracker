# Generated by Django 2.1.7 on 2019-03-11 15:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('observe', '0018_auto_20181210_1243'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asteroid',
            name='image_url',
            field=models.FileField(upload_to=''),
        ),
        migrations.AlterField(
            model_name='asteroid',
            name='timelapse_url',
            field=models.FileField(blank=True, null=True, upload_to=''),
        ),
    ]
