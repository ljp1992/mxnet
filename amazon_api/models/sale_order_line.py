# -*- encoding: utf-8 -*-

from odoo import models, fields

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_currency = fields.Char(related='shop_currency.symbol', store=False)
    order_item_id = fields.Char(string=u'Order Item Id')

    amazon_price_tax = fields.Float(string=u'ItemTax')
    amazon_shipping_price = fields.Float(string=u'运费')
    amazon_shipping_discount = fields.Float(string=u'ShippingDiscount')
    amazon_shipping_tax = fields.Float(string=u'ShippingTax')
    amazon_commission_price = fields.Float(string=u'佣金')

    shop_currency = fields.Many2one('res.currency', related='order_id.currency_id_amazon', store=False, string=u'币种')





