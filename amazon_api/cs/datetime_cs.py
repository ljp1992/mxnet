# -*- encoding: utf-8 -*-

import datetime, string

a = datetime.datetime.strptime('2018-01-24 11:11:11', '%Y-%m-%d %H:%M:%S')
print a,type(a)
b = a.strftime('%Y-%m-%d %H:%M:%S')
print b,type(b)