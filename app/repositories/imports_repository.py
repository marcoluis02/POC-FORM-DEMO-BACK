from app.models.form_import import FormImport
from app.repositories.base_repository import BaseRepository


class ImportsRepository(BaseRepository[FormImport]):
    model = FormImport
