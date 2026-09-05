#!/usr/bin/python3

import enchant

lang = "en_US"
try:
    dic = enchant.request_dict(lang)
    print("Dictionary for {0} language is available for use".format(lang))
except enchant.errors.DictNotFoundError:
    print("Dictionary is not installed for use")
