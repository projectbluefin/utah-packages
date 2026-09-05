#!/usr/bin/python3

import enchant

wdlst = [ "hello", "tea", "morning"]
dic = enchant.Dict("en_US")
for wd in wdlst:
    dic.check(wd)
    print("input word = {0}, Suggestions => {1}".format(wd, dic.suggest(wd)))
