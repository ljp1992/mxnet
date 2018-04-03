from odoo import models, fields
class amazon_sale_order_fee_ept(models.Model):
    _name="amazon.sale.order.fee.ept"
    
    fee_type=fields.Char(string="Fee Type")
    amount=fields.Float(string="Amount")
    is_refund=fields.Boolean(string="Is Refund")
    amazon_sale_order_line_id=fields.Many2one("amazon.sale.order.line.ept",string="Amazon Sale Order Line")
    