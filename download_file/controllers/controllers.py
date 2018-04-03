# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request,content_disposition
import json,base64,cgi

class DownloadFile(http.Controller):

    @http.route(['/web/binary/download_document'], type='http', auth='public')
    def download_file(self, **kwargs):
        model = kwargs.get('model')
        id = kwargs.get('id')
        if type(id) is not int:
            id = int(id)
        order = request.env[model].sudo().browse(id)#销售订单

        content = u"姓名: " + (order.partner_shipping_id.name or '')\
                  + '\r\n' + u"地址: " + (order.partner_shipping_id.street or '')\
                  + '\r\n' + u"城市: " + (order.partner_shipping_id.city or '')\
                  + '\r\n' + u"州省: " + (order.partner_shipping_id.state_id.name or '')\
                  + '\r\n' + u"国家: " + (order.partner_shipping_id.country_id.name or '')\
                  + '\r\n' + u"邮编: " + (order.partner_shipping_id.zip or '')\
                  + '\r\n' + u"电话: " + (order.partner_shipping_id.phone or '')

        filecontent = content or ''
        filename = 'cs.txt'
        return request.make_response(filecontent, [('Content-Type', 'application/octet-stream'),
                                                   ('Content-Disposition', content_disposition(filename))])
