# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import xlrd, xlwt, base64, datetime
from cStringIO import StringIO

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    def download_sale_order(self):
        model = 'sale.order'
        id = self.id
        return {
            'type': 'ir.actions.client',
            'tag': 'download_file',
            'context': {'model': model,
                        'order_id':id,
                        }
        }
