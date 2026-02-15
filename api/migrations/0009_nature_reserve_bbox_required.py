from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0008_bbox_simple_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="naturereserve",
            name="min_lat",
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name="naturereserve",
            name="max_lat",
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name="naturereserve",
            name="min_lon",
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name="naturereserve",
            name="max_lon",
            field=models.FloatField(db_index=True),
        ),
    ]
