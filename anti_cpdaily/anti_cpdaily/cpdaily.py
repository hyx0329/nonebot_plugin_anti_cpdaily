from typing import Optional, Dict
from copy import deepcopy
import random
import base64
import re
from httpx import AsyncClient
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from loguru import logger

from .constant import *
from .slider_captcha import solve_captcha


def _aes_encrypt_b64(text: str, key: str) -> str:
    random_letters = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
    rand_string = ''.join(random.choices(random_letters, k=64))
    rand_iv = ''.join(random.choices(random_letters, k=16))
    aes = AES.new(key=key.encode('utf-8'), mode=AES.MODE_CBC, iv=rand_iv.encode('utf-8'))
    data = rand_string + text
    amount_to_pad = AES.block_size - (len(data) % AES.block_size)
    if amount_to_pad == 0:
        amount_to_pad = AES.block_size
    data = data + chr(amount_to_pad) * amount_to_pad
    encrypted = aes.encrypt(data.encode('utf-8'))
    result = base64.b64encode(encrypted).decode('utf-8')
    return result


class AsyncCpdailyUser:

    username: str
    password: str
    school_name: Optional[str]
    school_info: Optional[Dict]
    client: Optional[AsyncClient]
    school_api: Optional[Dict]

    def __init__(self,
        username: str,
        password: str,
        school_name: Optional[str] = None,
        *args, **kwargs):
        self.username = username
        self.password = password
        self.school_name = school_name
        self.school_api = None
        self.school_info = None
        self.client = AsyncClient(verify=False)
        self.client.headers = {'User-Agent': USER_AGENT_LOGIN}
    
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if isinstance(self.client, AsyncClient):
            await self.client.aclose()
    
    async def shutdown(self):
        if isinstance(self.client, AsyncClient):
            await self.client.aclose()
            self.client = None

    async def login(self) -> bool:
        logger.info('start to login')
        logger.info('getting school api')
        await self._get_school_api()
        logger.info('try to login')
        if '/iap' in self.school_api['amp_login_path']:
            return await self._iap_login()
        else:
            return await self._cas_login()

    async def _get_school_api(self) -> Dict:
        # get a list about available schools and find target based on name
        res = await self.client.get(URL_SCHOOL_LIST, timeout=10)  # data is a bit long
        schools = res.json().get('data')
        logger.debug('available school count: {}'.format(len(schools)))
        school_idx = -1
        for idx, school in enumerate(schools):
            if school.get('name') == self.school_name:
                school_idx = idx
                break
        if school_idx < 0:
            logger.error('school not found')
            raise ValueError(f'Unsupported school! {self.school_name}')
        # school is supported, load detail infomation
        school = schools[school_idx]
        self.school_info = school  # save current school info
        school_param = {
            'ids': school['id']
        }
        res = await self.client.get(URL_SCHOOL_INFO, params=school_param)
        res_json = res.json()
        logger.debug('cpdaily response status: {}'.format(res.status_code))
        logger.debug('cpdaily response detail: {},{}'.format(res_json.get('errCode'), res_json.get('errMsg')))
        school_info = res_json.get('data')[0]
        logger.debug(f'school info: {school_info}')
        # WTF? generate parameters?
        school_api = {
            'tenant_id': school_info['id'],
            'ids_url': school_info['idsUrl'],
            'amp_root': '',
            'amp_login_path': '',
            'amp_login_params': {},
        }
        url_candidates = [school_info.get('ampUrl2'), school_info.get('ampUrl')]  # pay attention to the order
        for candidate in url_candidates:
            if 'campusphere' in candidate or 'cpdaily' in candidate:
                parse_result = urlparse(candidate)
                school_api['amp_root'] = parse_result.scheme + r'://' + parse_result.netloc
                school_api['amp_login_path'] = parse_result.path + '/login'
                school_api['amp_login_params']['service'] = parse_result.scheme + r'://' + parse_result.netloc + r'/portal/login'
                break
        self.school_api = school_api
        return school_api

    async def _iap_login(self) -> bool:
        raise NotImplementedError()

    async def _cas_login(self) -> bool:
        logger.info('start cas login')
        login_url = self.school_api['amp_root'] + self.school_api['amp_login_path']
        amp_params = self.school_api['amp_login_params']
        logger.debug('fetching web page')
        res = await self.client.get(login_url, params=amp_params, follow_redirects=True, timeout=10)  # server speed is slow
        logger.debug('current history: {}', res.history)
        logger.debug('current url: {}', res.url)
        cas_target_url = res.url
        raw_page_html = res.text
        soup = BeautifulSoup(raw_page_html, 'lxml')
        logger.debug('searching for cas login form')
        cas_login_form = soup.select('#casLoginForm')
        if len(cas_login_form) < 1:  # no form found
            logger.error('cas form tag not found')
            raise RuntimeError('unable to find cas login form from raw html')
        else:
            logger.debug('form found: {}'.format(cas_login_form))

        # check if captcha required, and mark the status
        cas_root = cas_target_url.scheme + '://' + cas_target_url.host
        logger.debug(f'cas root: {cas_root}')
        check_captcha_url = cas_root + '/authserver/needCaptcha.html'
        res = await self.client.get(check_captcha_url, params={'username': self.username})
        flag = res.text
        need_captcha = flag in {'true', 'True'}
        logger.debug(f'if need captcha: {need_captcha}(flag: {flag})')

        # extract the form from html
        logger.debug('extract form components to make params')
        form = soup.select('#casLoginForm > input')
        required_fields = {'username', 'password', 'lt', 'dllt', 'execution', '_eventId', 'rmShown', 'sign'}
        login_params = {}
        for entry in form:
            logger.debug('form entry: {}'.format(entry))
            if (entry_name := entry.get('name', '')) in required_fields:
                login_params[entry_name] = entry.get('value', '')
        # especially, the salt
        salt_tag = soup.select("#pwdDefaultEncryptSalt")
        logger.debug('salt component from html: {}'.format(salt_tag))
        salt = None
        if len(salt_tag) > 0:
            salt = salt_tag[0].get_text()
        else:
            # on mobile, the salt is stored in a javascript variable
            salt_result = re.search('(?<=var pwdDefaultEncryptSalt = ")\w{16}(?=")', raw_page_html)
            if salt_result is not None:
                logger.debug(f'salt from embedded javascript: {salt_result}')
                salt = salt_result[0]
            else:
                logger.warning('no #pwdDefaultEncryptSalt found')

        # prepare identity and captcha, try to login
        login_params['username'] = self.username
        if salt == None:
            login_params['password'] = self.password
        else:
            login_params['password'] = _aes_encrypt_b64(self.password, salt)
        # solve the slider captcha
        # TODO: identify slider captcha and text captcha
        if need_captcha:
            logger.info('solving the captcha')
            img_url = cas_root + '/authserver/sliderCaptcha.do'
            verify_url = cas_root + '/authserver/verifySliderImageCode.do'
            res = await self.client.get(img_url, params={'username': self.username})
            data = res.json()
            params = solve_captcha(data)
            logger.debug(f'solution: {params}')
            res = await self.client.get(verify_url, params=params)
            signature = res.json()
            server_code = signature.get('code')
            server_msg = signature.get('message')
            logger.debug(f'server response status: code({server_code}), message({server_msg})')
            if signature.get('code') != 0:
                logger.warning('server rejects the captcha')
            login_params['sign'] = signature.get('sign', '')

        # post form
        logger.info('posting form')
        logger.debug('form data: {}'.format(login_params))
        logger.debug('target url: {}'.format(cas_target_url))

        res = await self.client.post(cas_target_url, params=login_params, follow_redirects=True, timeout=10)
        logger.debug('post status: {}', res.status_code)
        logger.debug('current history: {}', res.history)
        logger.debug('current url: {}', res.url)
        logger.debug('client cookie: {}', self.client.cookies)

        if len(res.history) > 0:  # if have redirections (code 302)
            current_host = urlparse(res.history[0].headers['Location'])
            expected_host = urlparse(self.school_api.get('amp_root'))
            logger.debug(f'expecting host: {expected_host}, current host: {current_host}')
            if current_host.netloc == expected_host.netloc:  # must redirect back
                logger.success('login success')
                logger.debug('client cookie: {}', self.client.cookies)
                return True
        
        logger.warning('login conditions not satisfied')

        # parse last response, search for error message
        soup = BeautifulSoup(res.text, 'lxml')
        error_msg = soup.select('#errorMsg')
        if len(error_msg) > 0:
            logger.warning('error message from server: {}'.format(error_msg[0].get_text()))
        logger.warning('login failed')
        return False
