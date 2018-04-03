# -*- encoding: utf-8 -*-

from openerp import models,fields

class product_brand(models.Model):
    _name = 'product.brand'

    name = fields.Char('Brand Name')
    description = fields.Text('Description', translate=True)
    partner_id = fields.Many2one('res.partner', string='Partner',
                                 help='Select a partner for this brand if it exists.',
                                 ondelete='restrict')
    logo = fields.Binary('Logo File')