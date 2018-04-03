from openerp import models,fields,api

class amazon_marketplace_ept(models.Model):
    _name="amazon.marketplace.ept"
    
    seller_id = fields.Many2one('amazon.seller.ept',string='Seller')
    name = fields.Char(size=120, string='Name', required=True)
    market_place_id = fields.Char("Marketplace")
    is_participated = fields.Boolean("Marketplace Participation")
    country_id = fields.Many2one('res.country',string='Country')
    amazon_domain = fields.Char(size=120, string='Domain')
    currency_id = fields.Many2one('res.currency',string='Currency')
    lang_id = fields.Many2one('res.lang',string='Language')
    domain=fields.Char("Domain")
    @api.model
    def find_instance(self,seller,sales_channel):
        marketplace = self.search([('seller_id','=',seller.id),('name','=',sales_channel)]) 
        if marketplace:
            instance = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id),('marketplace_id','=',marketplace[0].id)])
            return instance and instance[0]
        return self.env['amazon.instance.ept'].browse()
