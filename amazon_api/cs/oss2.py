# -*- encoding: utf-8 -*-

import copy,uuid, base64, urllib, xlrd, xlwt, oss2, json

auth = oss2.Auth('LTAIy1XF2bUUWM6N', 'GqomKcGskXOIQdbHVVHmMiIrqjjavp')
bucket = oss2.Bucket(auth, 'http://oss-cn-hangzhou-internal.aliyuncs.com', 'image-hub360-b2b')
# 准备回调参数
callback_dict = {}
callback_dict['callbackUrl'] = 'http://oss-demo.aliyuncs.com:23450'
callback_dict['callbackHost'] = 'oss-cn-hangzhou.aliyuncs.com'
callback_dict['callbackBody'] = 'filename=${object}&size=${size}&mimeType=${mimeType}'
callback_dict['callbackBodyType'] = 'application/x-www-form-urlencoded'
# 回调参数是json格式，并且需要base64编码
callback_param = json.dumps(callback_dict).strip()
base64_callback_body = base64.b64encode(callback_param)
# 回调参数编码后放在header中传给oss
headers = {'x-oss-callback': base64_callback_body}
# 上传并回调
result = bucket.put_object('/Users/king/Desktop/upc.xls', 'a'*1024*1024, headers)
print result