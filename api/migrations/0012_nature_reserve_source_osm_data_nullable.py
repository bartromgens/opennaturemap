from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0011_add_reserve_geojson"),
    ]

    operations = [
        migrations.AddField(
            model_name="naturereserve",
            name="source",
            field=models.CharField(
                choices=[("osm", "OpenStreetMap"), ("wdpa", "Protected Planet")],
                db_index=True,
                default="osm",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="naturereserve",
            name="osm_data",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
