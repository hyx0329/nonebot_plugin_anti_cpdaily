from pydantic import BaseSettings
from nonebot import get_driver


class Config(BaseSettings):

    anti_cpdaily_profile_path: str = 'profiles/anti_cpdaily'

    class Config:
        extra = "ignore"


global_config = get_driver().config
plugin_config = Config(**global_config.dict())
