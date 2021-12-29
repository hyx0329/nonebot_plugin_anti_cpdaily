import nonebot
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.typing import T_State
from nonebot.adapters import Bot, Event
from nonebot.log import logger

from .config import global_config
from .schedule import anti_cpdaily_check_routine


cpdaily = on_command('cpdaily')
scheduler = nonebot.require("nonebot_plugin_apscheduler").scheduler


async def one_shot_routine():
    scheduler.remove_job('anti_cpdaily_oneshot')
    await anti_cpdaily_check_routine()


@cpdaily.handle()
async def handle_command(bot: Bot, event: Event, state: T_State):
    """ Manually activate the routine in 1 min
    """
    if event.get_user_id() in bot.config.superusers:
        logger.debug('manually activate the cpdaily routine')
        # await anti_cpdaily_check_routine()
        scheduler.add_job(one_shot_routine, trigger='interval', minutes=1, id='anti_cpdaily_oneshot', replace_existing=True)
        logger.debug('manual process end')
        await cpdaily.finish('启动今日校园打卡程序ing')
