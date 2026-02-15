from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_nature_reserve_bbox_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="naturereserve",
            name="protect_class",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
