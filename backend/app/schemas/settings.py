from pydantic import BaseModel
from typing import Optional, Dict


class SettingItem(BaseModel):
    key: str
    category: str
    value: str
    description: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, str]
