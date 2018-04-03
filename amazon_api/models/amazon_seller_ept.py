# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO

class AmazonSellerEpt(models.Model):
    _inherit = 'amazon.seller.ept'

    # import_shipped_fbm_orders = fields.Boolean(u"Import FBM Shipped Orders", default=True)

    def create_instance_ljp(self):
        return {
            'type': 'ir.actions.act_window',
            'name': u'创建店铺',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'res.config.amazon.instance',
            'views': [(self.env.ref('amazon_ept_v10.view_res_config_amazon_instance').id, 'form')],
            'target': 'new',
            'context': {'default_seller_id': self.id},
        }
