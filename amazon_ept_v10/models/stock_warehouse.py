from openerp import models,fields

class stock_warehouse(models.Model):
    _inherit = "stock.warehouse"
    
    seller_id = fields.Many2one('amazon.seller.ept', string='Amazon Seller')
        

class delivery_carrier(models.Model):
    _inherit = "delivery.carrier"
    
    amazon_code = fields.Char('Amazon Carrier Code')
    

    