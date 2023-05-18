from django.db import models
import uuid
from django.utils.text import slugify


class BaseModel(models.Model):
    is_active = models.BooleanField(default=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, auto_now=False, null=True)
    updated = models.DateTimeField(auto_now_add=False, auto_now=True)

    # objects = IsActiveModelManager()

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.id}"


class BaseDictModel(BaseModel):
    name = models.CharField(max_length=128, blank=True, null=True, default=None)
    slug = models.SlugField(max_length=128, blank=True, null=True, default=None, editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        if self.name:
            self.slug = slugify(self.name)
        else:
            self.slug = None
        super().save(*args, **kwargs)