from django.utils.deconstruct import deconstructible
from pathlib import Path
import sys
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.deconstruct import deconstructible
import uuid


@deconstructible
class UploadToPathAndRenameImage(object):

    def __init__(self, *args, **kwargs):
        self.upload_to = kwargs.get("upload_to")

    def __call__(self, instance, file_name):
        ext = file_name.split('.')[-1]
        file_path = f"{instance.uuid}__{uuid.uuid4()}.{ext}"
        if not self.upload_to is None:
            upload_to = f"{self.upload_to}/" if not self.upload_to[-1] == "/" else self.upload_to
            file_path = f"{upload_to}{file_path}"
        return file_path


class OptimizeImageSize:
    width_dict = {
        "x-small": 100,
        "small": 400,
        "medium": 800,
        "large": 1600
    }
    quality = 100

    def launch(self, initial_image, size):
        image_file = initial_image.file
        image_name = initial_image.name
        image_file.seek(0)
        image = Image.open(image_file)

        width, height = image.size
        target_width = self.width_dict[size]
        target_width = width if target_width > width else target_width

        ratio = width/float(target_width)
        target_height = height/ratio

        image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        output = BytesIO()
        try:
            image.save(output, format='JPEG', quality=self.quality)
        except:
            image.convert('RGB').save(output, format='JPEG', quality=self.quality)
        output.seek(0)
        image_name = image_name.split(".")[0]
        img = InMemoryUploadedFile(output, "ImageField", f"{image_name}.jpg", 'image/jpeg', sys.getsizeof(output), None)
        return img