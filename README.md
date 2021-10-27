# anti_cpdaily NoneBot Plugin

## Intro

This is a project refactored from `fuck_cpdaily`, and currently, contains only
the ability to submit the collections(because I dont need other features now).

CAS login is implemented, and a solution to the slider captcha is introduced.
IAP login is **NOT** implemented.

## How to use

### A quick start

- clone the repo
- move `anti_cpdaily` to your bot's plugin folder
- run the example script `anti_cpdaily/simple_example.py` to get a config example
- edit the config example, fill the necessary parameters(`lon`,`lat`,`qq`)
- also remember to fill the forms, by keeping only the wanted choices
- create a folder names `anti_cpdaily_profiles` where your `bot.py` sits
- move the config generated to `anti_cpdaily_profiles`
- perhaps you need to change the scheduler's config in `anti_cpdaily/schedule.py`
- start your bot

### Explaination

All user configs are stored in jsons. They are loaded using pydantic. The path
of the config folder can be changed in the bot's `.env` via a variable called 
`ANTI_CPDAILY_PROFILE_PATH`. Multiple profiles supported, but in case of an
exception occuring, rest of the profiles are ignored.

## Acknowledgement

- Original project `fuck_cpdaily`
- [SWU-CpDaily](https://github.com/F-19-F/SWU-CpDaily) for a protocol update reference
- My friends(not listed here)

## License

See `LICENSE`.