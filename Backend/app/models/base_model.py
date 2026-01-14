from datetime import datetime
from typing import Optional, Dict, Any, List

class BaseModel:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        if not data:
            return None

        instance = cls()
        for key, value in data.items():
            if key in cls.__annotations__:
                attr_name = key
            else:
                attr_name = ''.join(['_' + c.lower() if c.isupper() else c for c in key])
                attr_name = attr_name.lstrip('_')

            # Handle datetime conversion
            if attr_name.endswith('_at') and value and isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace('Z', "+00:00"))
                except ValueError:
                    pass

            # Set attribute if it exists on the class
            if hasattr(instance, attr_name):
                setattr(instance, attr_name, value)

        return instance

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for attr_name, attr_value in self.__dict__.items():
            if attr_name.startswith('_'):
                continue

            # Convert datetime to ISO string
            if isinstance(attr_value, datetime):
                attr_value = attr_value.isoformat()

            result[attr_name] = attr_value

        return result

    @staticmethod
    def format_datetime(dt: Optional[datetime]) -> Optional[str]:
        if not dt:
            return None
        return dt.isoformat()