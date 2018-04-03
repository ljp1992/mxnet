# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
import odoo.addons.decimal_precision as dp
from odoo.osv import osv
from odoo.exceptions import UserError, AccessError
import uuid
import itertools
import psycopg2
from odoo.exceptions import ValidationError

class B2bUPCList(models.Model):
    _inherit= "b2b.upc.list"

    @api.one
    def assign_upc_codes(self):
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        product_obj = self.env['product.product'].sudo()
        product = product_obj.search([('product_owner.type', '=', 'shop'),
                                      ('product_owner.parent_id', '=', distributor.id),
                                      ('barcode', '=', False)], limit=1)
        if product:
            if product.upc_code:
                product.write({'barcode': self.name})
            else:
                product.upc_code = self.name
            self.write(({'state': 'taken', 'shop_id': product.product_owner.id, 'product': product.id}))


