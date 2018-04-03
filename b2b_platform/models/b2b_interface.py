# -*- coding: utf-8 -*-
###########################################################################################
#
#    author:Qingdao Odoo Software Co., Ltd
#    module name for Qdodoo
#    Copyright (C) 2015 qdodoo Technology CO.,LTD. (<http://www.qdodoo.com/>).
#
###########################################################################################

from odoo import models, fields, api
from odoo.osv import osv
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError

class b2b_amazon_interface_template(models.Model):
    _inherit = 'product.template'
    _description = 'interface data between MX-b2b and amazon module'

    supplier_name = fields.Char(u'厂商名称')
    brand = fields.Char(u'产品品牌')
    # prefix = fields.Char(u'品名前缀')
    # suffix = fields.Char(u'品名后缀')
    declaration = fields.Text(u'重要声明')
    key_points = fields.Text(u'要点说明')
    keywords = fields.Char(u'关键字')
    # prefix_description = fields.Text(u'产品描述前缀')
    # suffix_description = fields.Text(u'产品描述后缀')

    product_status = fields.Selection([('pending', u'待更新'), ('updating', u'更新中'), ('fail', u'失败'),
                                       ('done', u'完成'), ('to_delete', u'待删除'), ('canceled', u'已删除')],
                                      u'产品状态')
    product_mod_time = fields.Datetime(u'产品变更时间')
    product_up_time = fields.Datetime(u'产品更新时间')
    product_feed_id = fields.Char(
        string='Feed ID'
    )
    
    image_update = fields.Selection([('pending', u'待更新'), ('updating', u'更新中'), ('fail', u'失败'),
                                     ('done', u'完成'), ('to_delete', u'待删除'), ('canceled', u'已删除')], u'图片状态')
    image_mod_time = fields.Datetime(u'图片变更时间')
    image_up_time = fields.Datetime(u'图片更新时间')
    image_feed_id = fields.Char(
        string='Feed ID'
    )
    price_update = fields.Selection([('pending', u'待更新'), ('updating', u'更新中'), ('fail', u'失败'),
                                     ('done', u'完成'), ('to_delete', u'待删除'), ('canceled', u'已删除')], u'价格状态')
    price_mod_time = fields.Datetime(u'价格变更时间')
    price_up_time = fields.Datetime(u'价格更新时间')
    price_feed_id = fields.Char(
        string='Feed ID'
    )
    stock_update = fields.Selection([('pending', u'待更新'), ('updating', u'更新中'), ('fail', u'失败'),
                                     ('done', u'完成'), ('to_delete', u'待删除'), ('canceled', u'已删除')], u'库存状态')
    stock_mod_time = fields.Datetime(u'库存变更时间')
    stock_up_time = fields.Datetime(u'库存更新时间')
    stock_feed_id = fields.Char(
        string='Feed ID'
    )
    relation_update = fields.Selection([('pending', u'待更新'), ('updating', u'更新中'), ('fail', u'失败'),
                                        ('done', u'完成'), ('to_delete', u'待删除'), ('canceled', u'已删除')], u'关系状态')
    relation_mod_time = fields.Datetime(u'关系变更时间')
    relation_up_time = fields.Datetime(u'关系更新时间')
    relation_feed_id = fields.Char(
        string='Feed ID'
    )
    shop_mod_list = fields.Boolean(u'店铺更新', compute='_set_shop_mod_list', search='_get_shop_mod_list')

    def _set_shop_mod_list(self):
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        for product in self:
            if product.product_owner.shop_operator == distributor \
                    and (product.product_status == 'pending'
                         or product.image_update == 'pending'
                         or product.price_update == 'pending'
                         or product.stock_update == 'pending'
                         or product.relation_update == 'pending'):
                product.shop_mod_list = True

    def _get_shop_mod_list(self, operator, value):
        list = []
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        products = self.search([('product_owner.parent_id', '=', distributor.id)])
        for product in products:
            if product.product_status in ('pending','to_delete','fail') \
                    or product.image_update in ('pending','to_delete','fail') \
                    or product.price_update in ('pending','to_delete','fail') \
                    or product.stock_update in ('pending','to_delete','fail') \
                    or product.relation_update in ('pending','to_delete','fail'):
                list.append(product.id)
        return [('id', 'in', list)]


class b2b_amazon_interface_product(models.Model):
    _inherit = 'product.product'
    _description = 'interface data between MX-b2b and amazon module'

    shop_price = fields.Float(u'店铺销售价')
    shop_active = fields.Boolean(u'店铺上架')

    product_status = fields.Selection(u'产品状态', related='product_tmpl_id.product_status')
    product_mod_time = fields.Datetime(u'产品变更时间', related='product_tmpl_id.product_mod_time')
    product_up_time = fields.Datetime(u'产品更新时间', related='product_tmpl_id.product_up_time')

    image_update = fields.Selection(u'图片状态', related='product_tmpl_id.image_update')
    image_mod_time = fields.Datetime(u'图片变更时间', related='product_tmpl_id.image_mod_time')
    image_up_time = fields.Datetime(u'图片更新时间', related='product_tmpl_id.image_up_time')

    price_update = fields.Selection(u'价格状态', related='product_tmpl_id.price_update')
    price_mod_time = fields.Datetime(u'价格变更时间', related='product_tmpl_id.price_mod_time')
    price_up_time = fields.Datetime(u'价格更新时间', related='product_tmpl_id.price_up_time')

    stock_update = fields.Selection(u'库存状态', related='product_tmpl_id.stock_update')
    stock_mod_time = fields.Datetime(u'库存变更时间', related='product_tmpl_id.stock_mod_time')
    stock_up_time = fields.Datetime(u'库存更新时间', related='product_tmpl_id.stock_up_time')

    relation_update = fields.Selection(u'关系状态', related='product_tmpl_id.relation_update')
    relation_mod_time = fields.Datetime(u'关系变更时间', related='product_tmpl_id.relation_mod_time')
    relation_up_time = fields.Datetime(u'关系更新时间', related='product_tmpl_id.relation_up_time')


class b2b_amazon_interface_partner(models.Model):
    _inherit = 'res.partner'
    _description = 'interface data between MX-b2b and amazon module'

    sku_prefix = fields.Char(u'SKU-ID前缀')
