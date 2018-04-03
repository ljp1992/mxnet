# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError

class ProductAttribute(models.Model):
    _inherit= 'product.attribute'

    amazon_name = fields.Char(string=u'亚马逊属性名')

    amazon_categ_ids = fields.Many2many('amazon.category.ept', 'attribute_amazon_categ_rel', 'attribute_id',
                                        'amazon_categ_id', string="Amazon Category")





