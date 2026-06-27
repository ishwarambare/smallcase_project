"""
Custom Django storage backend using the Supabase Python SDK.
Replaces S3/boto3 — works with Supabase API keys directly.
"""
import os
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class SupabaseStorage(Storage):
    """Django storage backend that stores files in Supabase Storage."""

    def __init__(self):
        from supabase import create_client
        self.base_url = os.environ.get('SUPABASE_URL', '')
        self.key = os.environ.get('SUPABASE_KEY', '')
        self.bucket = os.environ.get('SUPABASE_STORAGE_BUCKET', 'smallcase')
        self.client = create_client(self.base_url, self.key)

    def _open(self, name, mode='rb'):
        name_posix = name.replace('\\', '/')
        response = self.client.storage.from_(self.bucket).download(name_posix)
        return ContentFile(response)

    def _save(self, name, content):
        content.seek(0)
        file_bytes = content.read()

        content_type = 'application/octet-stream'
        if name.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif name.lower().endswith('.png'):
            content_type = 'image/png'
        elif name.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'

        name_posix = name.replace('\\', '/')
        self.client.storage.from_(self.bucket).upload(
            path=name_posix,
            file=file_bytes,
            file_options={"content-type": content_type}
        )
        return name_posix

    def exists(self, name):
        try:
            name_posix = name.replace('\\', '/')
            files = self.client.storage.from_(self.bucket).list(
                path=os.path.dirname(name_posix) or '',
                options={"limit": 1000}
            )
            filename = os.path.basename(name_posix)
            return any(f.get('name') == filename for f in files)
        except Exception:
            return False

    def url(self, name):
        name_posix = name.replace('\\', '/')
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{name_posix}"

    def delete(self, name):
        try:
            name_posix = name.replace('\\', '/')
            self.client.storage.from_(self.bucket).remove([name_posix])
        except Exception:
            pass

    def size(self, name):
        return 0

    def listdir(self, path):
        try:
            path_posix = (path or '').replace('\\', '/')
            files = self.client.storage.from_(self.bucket).list(path=path_posix)
            return [], [f['name'] for f in files]
        except Exception:
            return [], []

