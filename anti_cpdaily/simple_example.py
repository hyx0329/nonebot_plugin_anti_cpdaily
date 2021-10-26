from anti_cpdaily.example import generate_config, auto_submit_collections
from loguru import logger

if __name__ == "__main__":
    logger.info('start running example')

    # to generate a configuration
    generate_config()

    # to submit collections
    # auto_submit_collections(data_file='path/to/username.config.json')

    logger.info('example finished')
