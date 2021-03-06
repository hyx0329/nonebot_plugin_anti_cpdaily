from typing import Optional, List, Dict
from pydantic import BaseModel


class UserConfig(BaseModel):
    username: str
    password: str
    school_name: str
    address: str = ''
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    qq: Optional[int] = None
    collections: List[Dict] = []

    class Config:
        extra = 'allow'