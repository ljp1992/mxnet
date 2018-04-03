# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO

class AmazonInstanceEpt(models.Model):
    _inherit = 'amazon.instance.ept'

    down_sync_product_get_data = fields.Boolean(default=False, help=u'根据此字段来判断，该店铺是否有在后台执行同步产品的'
                                                                    u'获取产品数据的操作')
    down_sync_product_create_update = fields.Boolean(default=False, help=u'根据此字段来判断，该店铺是否有在后台执行同步产品的'
                                                                    u'创建更新产品的操作')

    # def unlink(self):
    #     partners = self.env['res.partner'].search([('amazon_instance_id', 'in', self.ids)])
    #     if partners:
    #         partners.unlink()
    #     return super(AmazonInstanceEpt, self).unlink()

    # def create(self, vals):
    #     result = super(AmazonInstanceEpt, self).create(vals)
    #     return result
    #
    # def write(self, vals):
    #     result = super(AmazonInstanceEpt, self).write(vals)
    #     return result
    #
    # def add_info(self):
    #     instance_exist = self.search([
    #         ('seller_id', '=', self.seller_id.id),
    #         ('marketplace_id', '=', self.marketplace_id.id),
    #     ])
    #     if instance_exist:
    #         raise Warning('Instance already exist with given Credential.')
    #
    #     user = self.env.user
    #     if user.company_id:
    #         company_id = user.company_id.id
    #     else:
    #         company = self.env['res.company'].search([('parent_id', '=', False)])
    #         company_id = company and company[0].id
    #
    #     warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_id)])
    #     if warehouse:
    #         warehouse_id = warehouse[0].id
    #     else:
    #         warehouse = self.env['stock.warehouse'].search([])
    #         warehouse_id = warehouse and warehouse[0].id
    #     marketplace = self.marketplace_id
    #     if marketplace.market_place_id in ['ATVPDKIKX0DER', 'A1PA6795UKMFR9', 'APJ6JRA9NG5V4', 'A13V1IB3VIYZZH',
    #                                        'A1RKKUPIHCS9HS', 'A1F83G8C2ARO7P', 'A2EUQ1WTGCTBG2']:
    #         amazon_encoding = 'iso-8859-1'
    #     elif marketplace.market_place_id in ['A1VC38T7YXB528']:
    #         amazon_encoding = 'Shift_JIS'
    #     else:  # marketplace.name in ['Amazon.cn']:
    #         amazon_encoding = 'UTF-8'
    #     self.update()