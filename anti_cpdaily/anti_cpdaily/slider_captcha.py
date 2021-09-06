from typing import Optional, Dict
from io import BytesIO
import base64
import numpy as np
from PIL import Image
from loguru import logger


def solve_captcha(data: dict) -> Optional[Dict[str, int]]:
    """solve slider captcha

    Args:
        data (dict): original data from the server

    Returns:
        Optional[Dict[str, int]]: the paramaters to pass the authentication
    
    The solution: each image given has a white, puzzle-shape borderline, which matches  
    with each other exactly. The small one's borderline is more clearer, as contains only  
    pure white pixel. Search the bigger one with the border from the small one for a minimal  
    distance.
    """
    # load and convert image
    im_big = Image.open(BytesIO(base64.b64decode(data.get('bigImage')))).convert('RGBA')
    # background = Image.new('RGBA', im_big.size, (0,0,0))
    # im_big_com = Image.alpha_composite(background, im_big)
    im_small = Image.open(BytesIO(base64.b64decode(data.get('smallImage')))).convert('RGBA')
    # background = Image.new('RGBA', im_small.size, (0,0,0))
    # im_small_com = Image.alpha_composite(background, im_small)

    # use them as arrays
    ar_big = np.array(im_big)
    ar_small = np.array(im_small)
    logger.debug('image size: big{}, small{}'.format(ar_big.shape, ar_small.shape))

    # drop alpha channel
    ar_big = ar_big[:, :, :3]
    ar_small = ar_small[:, :, :3]

    # get puzzle boundary from small one (and is more accurate)
    boundary = np.where(ar_small == [255,255,255])
    
    # scan the big image and create sum result
    mul_result = np.zeros((ar_big.shape[1] - ar_small.shape[1]))
    logger.debug(f'result shape: {mul_result.shape[0]}')
    selection = [ar for ar in boundary]
    for offset in range(mul_result.shape[0]):
        mul_result[offset] = np.sum(255 - ar_big[tuple(selection)])
        selection[1] += 1

    # now get real offset, apply scale to it
    offset = np.argmin(mul_result) / ar_big.shape[1] * 280
    
    params = {
        'canvasLength': 280,
        'moveLength': int(offset)
    }
    return params
