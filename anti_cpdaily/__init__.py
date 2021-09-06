# import nonebot
import os
from pathlib import Path
from loguru import logger
from .config import plugin_config

profile_path = Path(plugin_config.anti_cpdaily_profile_path)
logger.debug('anti_cpdaily profile path: "{}"'.format(profile_path))

logger.info('checking whether profile path exists')
if not profile_path.exists():
    logger.error('Profile path not exist! Scheduler will not work!')
else:
    logger.info('check ok, loading tasks')
    from .schedule import (
        check_collection_form_at_6_8_10_12,
        anti_cpdaily_launch
    )
    

# Export something for other plugin
# export = nonebot.export()
# export.foo = "bar"

# @export.xxx
# def some_function():
#     pass
