# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.exceptions import UserError

class AmazonCategoryEpt(models.Model):
    _inherit = 'amazon.category.ept'


    odoo_attribute_ids = fields.Many2many('product.attribute', 'attribute_amazon_categ_rel', 'amazon_categ_id',
                                          'attribute_id', string=u'odoo attribute')

    @api.multi
    def name_get(self):
        result = []
        for categ in self:
            name = categ.name
            if categ.parent_id:
                name = categ.parent_id.name + '/' + name
            result.append((categ.id, name))
        return result
