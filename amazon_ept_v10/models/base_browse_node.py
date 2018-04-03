from openerp import models,fields
class amazon_base_browse_node_ept(models.Model):
    _name="amazon.base.browse.node.ept"
    eco_category_code=fields.Char("Code")
    country_id=fields.Many2one("res.country","Country")
    name=fields.Char("Amazon Category")
    