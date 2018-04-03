# -*- coding: utf-8 -*-

from odoo import models, fields, api

class b2b_account_invoice(models.Model):
    _inherit = 'account.invoice'

    supplier = fields.Many2one('res.partner', u'供应商', domain="[('qdoo_func','=','supplier')]")
    distributor = fields.Many2one('res.partner', u'经销商', domain="[('qdoo_func','=','distributor')]")
    origin_doc = fields.Char(u'源单据')