# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    # shop_retail_price = fields.Float(compute='get_shop_retail_price', store=True, string=u'店铺售价', digits=(16, 2))

    # shop_currency = fields.Many2one('res.currency', compute='get_shop_currency', store=False, string=u'币种')
    # shop_currency2 = fields.Many2one('res.currency', compute='get_shop_currency', store=False, string=u'币种')

    main_images = fields.Many2many('product.image', 'product_main_image_rel', 'product_id', 'image_id', string=u'主图')

    _sql_constraints = [
        ('seller_sku_uniq', 'unique(default_code)', _(u"该sku已存在!")),
    ]

    # def get_shop_currency(self):
    #     for product in self:
    #         product.shop_currency = product.product_owner.shop_currency.id
    #         product.shop_currency2 = product.product_owner.shop_currency.id

    # @api.depends('list_price')
    # def get_shop_retail_price(self):
    #     for product in self:
    #         if product.variation_data == 'parent':
    #             product.shop_retail_price = product.list_price * product.shop_currency.rate

    @api.model
    def create(self, val):
        product = super(ProductProduct, self).create(val)
        product.only_one_main_image()
        return product

    @api.multi
    def write(self, val):
        result = super(ProductProduct, self).write(val)
        self.only_one_main_image()
        return result

    @api.multi
    def only_one_main_image(self):
        '''只能有一张主图'''
        for product in self:
            if len(product.main_images) > 1:
                raise UserError(u'只能选一张主图！')
