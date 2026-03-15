"""
Add privacy detection fields to JobVerification:
- privacy_metadata (JSON): CF Worker privacy scan results
- r2_key: Cloudflare R2 object storage key
- privacy_scrubbed: Whether blur metadata was applied
- ai_opt_out: Whether the Resident opted out of AI processing
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("support", "0005_alter_supportticket_assigned_to"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobverification",
            name="privacy_metadata",
            field=models.JSONField(
                blank=True,
                null=True,
                default=None,
                help_text="Privacy detection results from CF Worker: detected faces, family photos, sensitive documents, blur regions.",
            ),
        ),
        migrations.AddField(
            model_name="jobverification",
            name="r2_key",
            field=models.CharField(
                blank=True,
                null=True,
                default=None,
                max_length=512,
                help_text="Cloudflare R2 object key for stored verification media.",
            ),
        ),
        migrations.AddField(
            model_name="jobverification",
            name="privacy_scrubbed",
            field=models.BooleanField(
                default=False,
                help_text="True if privacy-sensitive content was detected and blur metadata was applied.",
            ),
        ),
        migrations.AddField(
            model_name="jobverification",
            name="ai_opt_out",
            field=models.BooleanField(
                default=False,
                help_text="True if the Resident opted out of AI processing for this verification.",
            ),
        ),
    ]
