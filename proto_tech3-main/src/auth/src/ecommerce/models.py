# /src/ecommerce/models.py
from pydantic import BaseModel
# Odoo often returns category as a list [id, name], we'll model that.
class OdooReference(BaseModel):
    id: int
    name: str

    @classmethod
    def from_odoo(cls, value: list):
        if not value or not isinstance(value, list) or len(value) != 2:
            return None
        return cls(id=value[0], name=value[1])

