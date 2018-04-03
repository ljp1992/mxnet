# -*- coding: utf-8 -*-

import base64
import logging
import json

from odoo import http
from odoo.http import request
from odoo import _
import oss2, uuid

_logger = logging.getLogger(__name__)

class Binary(http.Controller):

    @http.route('/web/binary/upload_formdata/', type='http', auth='user')
    def upload_formdata(self, model, id, ufile, last_file):
        attachment_model = request.env['ir.attachment']
        image_model = request.env['product.image']
        product_model = request.env['product.template']
        product_product_model = request.env['product.product']
        try:
            datas = ''
            raw_data = ufile.read()
            storage = request.env['ir.config_parameter'].get_param('b2b_image_store_location')
            image_system_type = request.env['ir.config_parameter'].get_param('image_system_type')
            oss_key = request.env['ir.config_parameter'].get_param('image_oss_key')
            oss_sec = request.env['ir.config_parameter'].get_param('image_oss_sec')
            oss_internal_url = request.env['ir.config_parameter'].get_param('image_oss_internal_url')
            oss_bucket=request.env['ir.config_parameter'].get_param('image_oss_bucket')
            oss_url = request.env['ir.config_parameter'].get_param('image_oss_url')


            # 图片存储到阿里云OSS
            if storage == 'oss':
                name = str(uuid.uuid1()) + '.jpg'
                auth = oss2.Auth(oss_key,oss_sec)
                try:
                    bucket = oss2.Bucket(auth, oss_internal_url,oss_bucket,
                                         connect_timeout=3)
                    bucket.put_object('item/'+ name, raw_data)
                except Exception,e:
                    _logger.info(e)
                    return request.make_response(json.dumps({'error': u'连接超时！'}), [('Content-Type', 'application/json')])
                attachment = attachment_model.create({
                    'name': ufile.filename,
                    #'datas': base64.encodestring(raw_data),
                    'url':oss_url+name,
                    'datas_fname': ufile.filename,
                    'res_model': model,
                    'res_id': int(id)
                })
            # 图片本地存储
            else:
                datas = base64.encodestring(raw_data)
                attachment = attachment_model.create({
                    'name': ufile.filename,
                    'datas': datas,
                    'datas_fname': ufile.filename,
                    'res_model': model,
                    'res_id': int(id)
                })
                attachment.write({'url': '/attachment/download?attachment_id=' + str(attachment.id)})

            # 将图片关联到产品
            image_id = image_model.create({'name': ufile.filename,
                                           'product_tmpl_id': int(id),
                                           'image_id': attachment.id,
                                           'sequence': 0,
                                            })

            # 如果产品没有变体，则将图片关联到Product.product
            prods = product_product_model.search([('product_tmpl_id','=',int(id))])
            if len(prods) == 1:
                sql = "INSERT INTO product_product_image_rel " \
                      "VALUES (%s, %s); " % (prods.id, image_id.id)
                request._cr.execute(sql)

            # 产品中如果没有图片，则自动添加产品主图
            to_add = False
            if last_file == 'true':
                master_prod = product_model.search([('id', '=', int(id))])
                if master_prod and (not master_prod.image):
                    to_add = True
                    if datas == '':
                        datas = base64.encodestring(raw_data)
                    #master_prod.image = datas
                    master_prod.write({'image': datas,'main_image_attachment_id':attachment.id})

            if image_system_type=='b2b':
                # 在经销商跟店铺收录的产品中添加该图片
                collected_products = product_model.sudo().search([('master_product', '=', int(id))])
                for coll_prod in collected_products:
                    image_model.create({'name': ufile.filename,
                                        'product_tmpl_id': coll_prod.id,
                                        'image_id': attachment.id,
                                        'sequence': 0,
                                        })
                    if to_add:
                        coll_prod.with_context({'collection_mark': 'collected'}).write({
                            'image':datas,'main_image_attachment_id':attachment.id})

            args = {
                'filename': ufile.filename,
                'mimetype': ufile.content_type,
                'id':  attachment.id
            }
        except Exception, e:
            args = dict(error=_("Something horrible happened"), message=e.message)
            _logger.exception("Fail to upload attachment(%s) exception(%s)" % (ufile.filename, e.message))
        return request.make_response(json.dumps(args), [('Content-Type', 'application/json')])
