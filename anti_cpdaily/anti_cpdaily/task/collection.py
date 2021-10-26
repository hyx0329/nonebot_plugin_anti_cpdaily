from typing import Optional, Dict, List, Callable
from Crypto.Cipher import DES, AES
from Crypto.Util.Padding import pad
from datetime import datetime
from httpx import AsyncClient
from copy import deepcopy
import base64, json, uuid
import hashlib
from loguru import logger

from .base import AsyncBaseTask
from ..cpdaily import AsyncCpdailyUser
from ..constant import *


def _des_encrypt_b64(text: str) -> str:
    key = b'b3L26XNL'
    iv = b'\x01\x02\x03\x04\x05\x06\x07\x08'
    des = DES.new(key=key, mode=DES.MODE_CBC, iv=iv)
    data_to_en = pad(text.encode('utf-8'), block_size=8, style='pkcs7')
    encrypted = des.encrypt(data_to_en)
    result = base64.b64encode(encrypted).decode('utf-8')
    return result


def _aes_encrypt_b64(text: str) -> str:
    key = b'ytUQ7l2ZZu8mLvJZ'
    iv = b'\x01\x02\x03\x04\x05\x06\x07\x08\t\x01\x02\x03\x04\x05\x06\x07'
    aes = AES.new(key=key, mode=AES.MODE_CBC, iv=iv)
    data_to_en = pad(text.encode('utf-8'), block_size=8, style='pkcs7')
    encrypted = aes.encrypt(data_to_en)
    result = base64.b64encode(encrypted).decode('utf-8')
    return result


def _generate_extension_signature(extension: Dict) -> str:
    """extract data from extension and generate signature

    Args:
        extension (Dict): extention

    Returns:
        str: signature
    """
    data_tosign = {
        "appVersion": CPDAILY_APP_VERSION,
        "bodyString": extension.get('bodyString'),
        "deviceId": extension.get("deviceId"),
        "lat": extension.get("lat"),
        "lon": extension.get("lon"),
        "model": extension.get("model"),
        "systemName": extension.get("systemName"),
        "systemVersion": extension.get("systemVersion"),
        "userId": extension.get("userId"),
    }

    kv_pairs = list()

    for key, value in zip(form.keys(), form.values()):
        kv_pairs.append("{}={}".format(key,value))
    
    kv_pairs.append(CPDAILY_KEY_AES.decode('utf-8'))
    string_to_hash = "&".join(kv_pairs)
    signature = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
    return signature


class Form:

    subject: str
    wid: Optional[str]
    form_wid: Optional[str]
    school_task_wid: Optional[str]
    source: Optional[str]
    issuer: Optional[str]
    priority: Optional[str]
    created: Optional[datetime]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    fetch_time: Optional[datetime]
    handled: Optional[bool]
    read: Optional[bool]
    description: Optional[Dict]  # server side description of the form
    form_data: Optional[Dict]  # actual form data containing the form entries
    user_data: Optional[Dict]  # user configurations and user information(username, lon, lat, uuid)
    form_to_submit: Optional[List[Dict]]

    def __init__(self, data: Dict):
        """initialize form from summary

        Args:
            data (Dict): form data from server
        """
        self.subject: str = data.get('subject')
        self.wid: Optional[str] = data.get('wid')
        self.form_wid: Optional[str] = data.get('formWid')
        self.source: Optional[str] = data.get('content')
        self.issuer: Optional[str] = data.get('senderUserName')
        self.priority: Optional[str] = data.get('priority')
        self.created: Optional[datetime] = datetime.strptime(data.get('createTime'), r'%Y-%m-%d %H:%M')
        self.start_time: Optional[datetime] = datetime.strptime(data.get('startTime'), r'%Y-%m-%d %H:%M')
        self.end_time: Optional[datetime] = datetime.strptime(data.get('endTime'), r'%Y-%m-%d %H:%M')
        self.fetch_time: Optional[datetime] = datetime.strptime(data.get('currentTime'), r'%Y-%m-%d %H:%M:%S')
        self.handled: Optional[bool] = data.get('isHandled') == 1
        self.read: Optional[bool] = data.get('isRead') == 1
        self.detail = None
        self.form_data = None
        self.school_task_wid = None
        self.form_to_submit = None

    async def fetch_detail(self, root: str, client: Optional[AsyncClient] = None):
        """fetch form detail, including `description` and `form_data`

        Args:
            root (str): the amp_root of the school(TODO: make clearer explaination)
            client (Optional[AsyncClient], optional): The client to use. Defaults to None(create new client).

        Use this method to update `content`.
        """
        # check client, generate new if required
        if not isinstance(client, AsyncClient):
            client = AsyncClient()  # i dont think it will work without cookies

        # load form decription, extract schoolTaskWid
        source_url = root + URI_FORM_DETAIL
        payload = {'collectorWid': self.wid}
        res = await client.post(source_url, json=payload, timeout=10)
        res_j = res.json()
        response_code = res_j.get('code')
        response_message = res_j.get('message')
        logger.debug(f'server response status: code({response_code}), msg({response_message})')
        self.description = res_j.get('datas')
        logger.debug(f'Form({self.wid}) description: {self.description}')
        self.school_task_wid = self.description.get('collector').get('schoolTaskWid')

        # then fetch form entries(fields)
        form_entries_url = root + URI_FORM_ENTRIES
        payload = {
            "pageSize": 100,
            "pageNumber": 1,
            "formWid": self.form_wid,
            "collectorWid": self.wid
        }
        res = await client.post(form_entries_url, json=payload)
        res_j = res.json()
        response_code = res_j.get('code')
        response_message = res_j.get('message')
        logger.debug(f'server response status: code({response_code}), msg({response_message})')
        self.form_data = res_j.get('datas')
        logger.debug(f'form({self.wid}) data: {self.form_data}')

    def fill_form(self, user_data: Dict) -> bool:
        """fill form with given data, also set user data

        Args:
            user_data (Dict): user configuration

        Returns:
            bool: True if a matched form found
        """
        if not isinstance(self.form_data, dict):
            logger.warning('missing form data, please fetch the data first')
            return False
        self.user_data = user_data  # reference attention!
        logger.info(f'filling the form({self.subject})')
        user_defined_form_data = None
        user_forms = self.user_data.get('collections', [])
        logger.info('searching among {} form(s)'.format(len(user_forms)))
        for form in user_forms:
            if form.get('subject') == self.subject:
                user_defined_form_data = form.get('fields')
                break
        if user_defined_form_data == None:
            logger.info('no matching form found')
            return False
        # fill the form
        logger.info('find a matched form, filling the form now')
        form_filled = list()
        for current_form_item in self.form_data.get('rows'):
            # TODO: fill unnecessary items
            if not current_form_item.get('isRequired'):
                continue
            item_title = current_form_item.get('title', '').replace('\xa0', ' ')  # replace non-breaking space to normal space
            item_col_name = current_form_item.get('colName')
            logger.info('next item: "{}"'.format(item_col_name))
            logger.info('item title: "{}"'.format(item_title))

            matched_item = None
            for uitem in user_defined_form_data:  # scanning user provided form data
                # compare items
                match_title = uitem.get('title') == item_title
                match_col_name = uitem.get('col_name') == item_col_name
                if match_title:
                    if match_col_name:
                        matched_item = uitem
                        break
                    else:  # partial match, misbehaved form
                        raise ValueError(
                            'form title match but colName({},{}) not, '
                            'form maybe changed!'
                            .format(item_col_name, uitem.get('col_name'))
                        )
            if matched_item == None:  # no matched entry for a required field, thus forms are different
                logger.warning('missing definition for "{}"'.format(item_title))
                logger.warning('form detail: {}'.format(current_form_item))
                return False
            # fill this item
            new_item = deepcopy(current_form_item)
            logger.debug('fill in item: "{}"'.format(new_item))
            item_type = new_item.get('fieldType')
            answer = matched_item.get('answer')
            if not isinstance(answer, list):
                logger.warning('bad answer list')
                return False
            logger.debug(f'current user definition: {matched_item}')
            logger.debug(f'answer candidates: {answer}')

            if item_type in {'1', '5'}:  # text
                if not len(answer) == 1:
                    logger.warning('expecting one answer but got {}'.format(len(answer)))
                    return False
                new_item['value'] = answer[0]

            elif item_type in {'2', '3'}:  # single/multiple choice
                # only keep those content is in answer
                if item_type == '2':
                    if not len(answer) == 1:
                        logger.warning('expecting one answer but got {}'.format(len(answer)))
                        return False

                new_field_items = list()
                for choice in new_item.get('fieldItems', []):
                    if choice.get('content') in answer:
                        new_field_items.append(choice)

                logger.debug('fill with: {}'.format(new_field_items))
                if not len(new_field_items) > 0:
                    logger.warning('no choice made, bug?')
                    return False
                new_item['fieldItems'] = new_field_items
                new_item['value'] = ' '.join(map(lambda x: x['content'], new_field_items))

            elif item_type == '4':  # ignored choice ?
                logger.warning('found type-4 item, but dont know what to do')
                pass
            else:
                raise ValueError('unexpected item type {}'.format(item_type))

            form_filled.append(new_item)
            logger.info('filled form value: "{}"'.format(new_item['value']))

        self.form_to_submit = form_filled
        logger.debug('form to submit: {}'.format(form_filled))
        return True

    def generate_config(self, only_required: bool = True) -> Optional[Dict]:
        """generate a user-friendly form example

        Args:
            only_required (bool): if ingore unnecessary form entries

        Returns:
            Dict: form data
        """
        if not only_required:
            logger.warning('unnecessary form entries included')
        if not isinstance(self.form_data, dict):
            logger.warning('form data not prepared, fetch them first')
            return None
        logger.info('generating user-friendly form example')
        fields = list()
        form_example = {
            'subject': self.subject,
            'size': 0,
            'original_size': self.form_data.get('totalSize'),
            'only_required': only_required,
            'fields': fields
        }
        fields_data = self.form_data.get('rows')
        for field in fields_data:
            if only_required and not field.get('isRequired'):
                continue
            new_example_field = {
                'title': field.get('title').replace('\xa0', ' '),  # replace non-breaking space to normal space
                'type': field.get('fieldType'),
                'required': field.get('isRequired'),
                'sort_id': field.get('sort'),
                'col_name': field.get('colName'),
                'answer': [item['content'] for item in field.get('fieldItems')]
            }
            fields.append(new_example_field)
        form_example['size'] = len(fields)
        logger.debug(f'form example: {form_example}')
        return form_example

    async def post_form(self, root: str, client: AsyncClient) -> bool:
        """post form to cpdaily

        Args:
            root (str): server root (amp_root)
            client (AsyncClient): client to use

        Returns:
            bool: True if succeeded
        """
        if not isinstance(self.user_data, dict):
            logger.warning('user data not provided')
            return False
        if not isinstance(self.form_to_submit, list):
            logger.warning('form not filled, perhaps no matching form found')
            return False
        # cpdaily encrypted 'Cpdaily-Extension'
        # TODO: utilize 'fetchStuLocation' from original form detail

        payload = {
            "formWid": self.form_wid,
            "address": self.user_data.get('address'),
            "collectWid": self.wid,
            "schoolTaskWid": self.school_task_wid,
            "form": self.form_to_submit,
            "uaIsCpadaily": True,
            "signVersion": "1.0.0"
        }

        extension = {
            "appVersion": APP_VERSION,
            "model": "OPPO R11 Plus",
            "systemName": "android",
            "systemVersion": "9.1.0",
            "userId": self.user_data.get('username'),
            "lon": self.user_data.get('longitude'),
            "lat": self.user_data.get('latitude'),
            "deviceId": self.user_data.get('device_uuid', str(uuid.uuid1())),
            "calVersion": "firstv",
            "version": "first_v2",
            "bodyString": _aes_encrypt_b64(json.dumps(payload)),
        }

        signature = _generate_extension_signature(extension)
        extension['sign'] = signature

        # cpdaily extra headers
        headers = {
            'CpdailyStandAlone': '0',
            'extension': '1',
            'sign': '1',
            'Cpdaily-Extension': _des_encrypt_b64(json.dumps(extension))
        }

        submit_url = root + URI_FORM_SUBMIT
        logger.info('submitting form')
        res = await client.post(submit_url, headers=headers, json=payload, timeout=10)
        res_j = res.json()
        server_code = res_j.get('code')
        server_msg = res_j.get('message')
        logger.debug(f'server response status: code({server_code}), message({server_msg})')
        if server_code == '0':
            logger.success('collection form submitted ("{}")'.format(self.subject))
            return True
        logger.warning('collection form not submitted ("{}")'.format(self.subject))
        return False


class AsyncCollectionTask(AsyncBaseTask):

    form_list: Optional[List[Form]]
    form_ans: Optional[List]

    def __init__(self,
        user: AsyncCpdailyUser,
        form_ans: Optional[List] = None,
        subject_filter: Optional[Callable] = None
        ):
        """collection task

        Args:
            user (AsyncCpdailyUser): user (must logged in)
            form_ans (Optional[List], optional): Form data, containing the answers. Defaults to None.
        """
        self.user = user
        self.form_list = None
        self.form_ans = form_ans

    async def fetch_form(self):
        client = self.user.client
        school_api = self.user.school_api
        source_url = school_api.get('amp_root') + URI_FORM_LIST
        payload = {
            'pageSize': 6,
            "pageNumber": 1
        }
        res = await client.post(source_url, json=payload)
        res_j = res.json()
        response_code = res_j.get('code')
        response_message = res_j.get('message')
        logger.debug(f'server response status: code({response_code}), msg({response_message})')
        if response_code != '0':
            logger.warning('server response status is unusual')
        data = res_j.get('datas')
        logger.debug(f'server response data: {data}')
        form_list = list()
        for form_summary in data.get('rows'):
            form_list.append(Form(form_summary))
        self.form_list = form_list
