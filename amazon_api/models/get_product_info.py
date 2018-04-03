# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products


class GetProductInfo(models.Model):
    _name = 'get.product.info'

    name = fields.Char(default=u'获取产品信息')
    code = fields.Char(string=u'编码')

    instance_id = fields.Many2one('amazon.instance.ept', string=u'店铺')

    result = fields.Text(string=u'返回结果')

    type = fields.Selection([
        ('ASIN', 'ASIN'),
        ('SellerSKU', 'SellerSKU'),
        ('UPC', 'UPC'),
    ], default='ASIN', string=u'类型')

    def query_code(self):
        '''查询产品信息'''
        seller = self.instance_id.seller_id
        marketplaceid = self.instance_id.market_place_id
        print seller.access_key, seller.secret_key, seller.merchant_id, seller.country_id.amazon_marketplace_code
        mws_obj = Products(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                           account_id=str(seller.merchant_id),
                           region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                           proxies={})
        if self.type in ('ASIN', 'SellerSKU'):
            result = mws_obj.get_matching_product_for_id(marketplaceid=marketplaceid, type=self.type, ids=[self.code])
            self.result = result.parsed
        elif self.type == 'UPC':
            result = mws_obj.list_matching_products(marketplaceid=marketplaceid, query=self.code, contextid=None)
            self.result = result.parsed

