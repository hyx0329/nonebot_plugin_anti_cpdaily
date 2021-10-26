import os
import json
import functools
import nonebot
from pathlib import Path
from datetime import datetime
from loguru import logger

from .anti_cpdaily.cpdaily import AsyncCpdailyUser
from .anti_cpdaily.task import AsyncCollectionTask
from .anti_cpdaily.config import UserConfig
from .config import plugin_config


scheduler = nonebot.require("nonebot_plugin_apscheduler").scheduler


def exception_notification(func):
    @functools.wraps(func)
    async def exception_notification(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error('exception occured: {}'.format(repr(e)))
            logger.warning(f'warning all superusers')
            current_time = str(datetime.now())
            bot = nonebot.get_bot()
            for user_id in bot.config.superusers:
                data = {
                    'user_id': int(user_id),
                    'message': '{time}\nanti_cpdaily exception occured\n{exp}'.format(time=current_time, exp=repr(e))
                }
                res = await bot.call_api('send_msg', **data)
    return exception_notification


@scheduler.scheduled_job("cron", hour='11,12,13,14', minute=30, id='anti_cpdaily_check_routine')
@exception_notification
async def anti_cpdaily_check_routine():
    # TODO: change strategy: add periodic jobs which can remove themselves after form finished when empty form detected
    logger.info('start collecting users for `collection form`')
    config_path = Path(plugin_config.anti_cpdaily_profile_path)
    configs = os.listdir(config_path)
    users = list()
    for cfg in configs:
        if cfg.endswith('config.json'):
            with open(config_path / cfg, encoding='utf-8') as f:
                data = json.load(f)
            user_data = UserConfig(**data)
            users.append(user_data)
    
    logger.info('collected user count: {}'.format(len(users)))
    for current_user in users:
        async with AsyncCpdailyUser(
            username=current_user.username,
            password=current_user.password,
            school_name=current_user.school_name
            ) as cpduser:

            log_in = await cpduser.login()
            if not log_in:
                logger.error('login failed')
                return
            
            collection_task = AsyncCollectionTask(user=cpduser)
            await collection_task.fetch_form()
            logger.info('processing {} collection(s) for user {}'.format(len(collection_task.form_list), current_user.username))
            forms_status = list()
            for form in collection_task.form_list:
                if form.handled:  # ingore finished forms
                    continue
                await form.fetch_detail(root=cpduser.school_api.get('amp_root'), client=cpduser.client)
                if form.fill_form(current_user.dict()):
                    logger.success('form({}) filled'.format(form.subject))
                    logger.info('try to submit collection({})'.format(form.subject))
                    submission_status = await form.post_form(root=cpduser.school_api.get('amp_root'), client=cpduser.client)
                    logger.info(f'submission status: {submission_status}')
                    text_status = 'OK' if submission_status else 'Failed'
                    forms_status.append((form.subject, text_status))
                else:
                    logger.warning('cannot fill form({})'.format(form.subject))
                    forms_status.append((form.subject, 'misbehave'))
            
        # send notification
        if isinstance(current_user.qq, int) and len(forms_status) > 0:
            logger.info('sending notification to {}'.format(current_user.qq))
            result = '\n'.join(map(str, forms_status))
            result = str(datetime.now()) + '\n表格收集填写状况：\n' + result
            data = {
                'user_id': current_user.qq,
                'message': result
            }
            bot = nonebot.get_bot()
            res = await bot.call_api('send_msg', **data)
            logger.debug('notify result: {}'.format(res))
    
    logger.info('operation finished')


@scheduler.scheduled_job('interval', minutes=1, id='anti_cpdaily_launch_notice')
@exception_notification
async def anti_cpdaily_launch():
    """send launch notice to all superusers
    """
    logger.info('send launched notice to all superusers')
    scheduler.remove_job('anti_cpdaily_launch_notice')
    current_time = str(datetime.now())
    bot = nonebot.get_bot()
    for user_id in bot.config.superusers:
        data = {
            'user_id': int(user_id),
            'message': '{time}\nanti_cpdaily started'.format(time=current_time)
        }
        res = await bot.call_api('send_msg', **data)
        logger.debug('notify to {} result: {}'.format(user_id, res))
