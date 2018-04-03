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

class b2b_product_template_freight(models.Model):
    _inherit = 'product.template'

    partner_id = fields.Many2one('res.partner',u'业务伙伴', required=True,
                 default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id,
                 domain=lambda self: [('owner', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)])
    # freight_template_id = fields.Many2one('b2b.product.freight.template.group', u'运费模板',
    #         domain=[('owner','=', lambda self: self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)])
    freight_template_id = fields.Many2one('b2b.product.freight.template.group', u'运费模板')
    cny_freight = fields.Float(u'基准运费(元）', digits=(16,2))
    freight_line = fields.One2many('b2b.product.freight.line', 'product_id', u'运费明细')

    @api.onchange('freight_template_id')
    def _onchange_freight_template(self):
        if self.freight_template_id:
            lines = []
            freights = self.env['b2b.product.freight.template'].search([('template_id','=',self.freight_template_id.id)])
            # currency_obj = self.env['res.currency']
            for country in freights:
                # exchange = currency_obj.search([('id','=',country.foreigh_currency.id)],limit=1).rate or 1
                # foreign_amount = self.cny_freight * exchange
                lines.append((0, 0, {'country_id': country.country_id.id,
                                     'cny_amount':country.cny_amount,
                                     # 'foreigh_currency':country.foreigh_currency.id,
                                     # 'foreign_amount':foreign_amount,
                                     }))
            self.freight_line = lines

class b2b_product_freight_line(models.Model):
    _name = 'b2b.product.freight.line'

    product_id = fields.Many2one('product.template', u'产品')
    country_id = fields.Many2one('res.country', u'国家')
    cny_amount = fields.Float(u'运费(元）', digits=(16,2))
    foreigh_currency = fields.Many2one('res.currency', u'运费(币种）')
    foreign_amount = fields.Float(u'运费(外币）', digits=(16,2))

class b2b_product_freight_template_group(models.Model):
    _name = 'b2b.product.freight.template.group'
    _rec_name = 'template'

    owner = fields.Many2one('res.partner', u'供应商', required=True,
                        default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    template = fields.Char(u'模板名称', required=True)
    freight_line = fields.One2many('b2b.product.freight.template', 'template_id', u'运费明细')

class b2b_product_freight_template(models.Model):
    _name = 'b2b.product.freight.template'
    _rec_name = 'country_id'

    template_id = fields.Many2one('b2b.product.freight.template.group', u'运费模板')
    country_id = fields.Many2one('res.country', u'国家', required=True)
    cny_amount = fields.Float(u'运费(元）', digits=(16,2))
    foreigh_currency = fields.Many2one('res.currency', u'运费(币种）')
    foreign_amount = fields.Float(u'运费(币别）', digits=(16,2))