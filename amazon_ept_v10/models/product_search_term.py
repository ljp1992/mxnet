from openerp import models, fields

class amazon_product_search_term(models.Model):
    _name="amazon.product.search.term"
    
    amazon_product_id=fields.Many2one('amazon.product.ept',string="Product")
    name=fields.Char(string="Search Term")