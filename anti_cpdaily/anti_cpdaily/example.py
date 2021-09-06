import getpass
import base64
import json
import asyncio
from typing import Optional
from loguru import logger

from anti_cpdaily.cpdaily import AsyncCpdailyUser
from anti_cpdaily.task import AsyncCollectionTask
from anti_cpdaily.config import UserConfig


async def example_helper(
    username: Optional[str] = None,
    password: Optional[str] = None,
    school_name: Optional[str] = None,
    config_path: Optional[str] = None,
    *args, **kwargs):
    """help to generate a complete config template

    Args:
        username (Optional[str], optional): username. if None, will get it from CLI input
        password (Optional[str], optional): password. if None, will get it from CLI input(will not shown)
        school_name (Optional[str], optional): school name. used to determine the api to use. if None, will get it from CLI input
        config_path (Optional[str], optional): the generated file's name(including path). if None, will use './{username}.config.json'
    """
    logger.info('collecting data for minimal example')
    if username == None:
        username = input('your username:')
    if password == None:
        password = getpass.getpass('your password(hidden):')
    if school_name == None:
        school_name = input('your school name:')
    current_user = UserConfig(username=username, password=password, school_name=school_name)
    async with AsyncCpdailyUser(
            username=current_user.username,
            password=current_user.password,
            school_name=current_user.school_name
        ) as user:
        log_in = await user.login()
        print(log_in)
        collection_task = AsyncCollectionTask(user=user)
        await collection_task.fetch_form()
        for form in collection_task.form_list:
            await form.fetch_detail(root=user.school_api.get('amp_root'), client=user.client)
            form_example = form.generate_config()
            current_user.collections.append(form_example)
    config_path = config_path if config_path != None else '{}.config.json'.format(current_user.username)
    with open(config_path, 'w') as f:
        json.dump(current_user.dict(), f, ensure_ascii=False, indent='  ')

def generate_config(*args, **kwargs):
    """warpper for `example_helper`
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(example_helper(*args, **kwargs))


async def fill_and_submit_collections(data_file: str):
    """fill collections using external data

    Args:
        data_file (str): path to external data
    """
    with open(data_file) as f:
        current_user = UserConfig(**json.load(f))
    
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
        for form in collection_task.form_list:
            await form.fetch_detail(root=cpduser.school_api.get('amp_root'), client=cpduser.client)
            if form.fill_form(current_user.dict()):
                logger.success('form({}) filled'.format(form.subject))
                logger.info('try to submit collection({})'.format(form.subject))
                submission_status = await form.post_form(root=cpduser.school_api.get('amp_root'), client=cpduser.client)
                logger.info(f'submission status: {submission_status}')
                pass
            else:
                logger.warning('cannot fill form({})'.format(form.subject))

def auto_submit_collections(*args, **kwargs):
    """warpper for `fill_and_submit_collections`
    """
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fill_and_submit_collections(*args, **kwargs))
