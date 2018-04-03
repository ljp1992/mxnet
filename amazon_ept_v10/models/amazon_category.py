from openerp import models,fields,api
class amazon_category(models.Model):
    _name="amazon.category.ept"
    
    name=fields.Char("Name",required=True)
    url=fields.Char("URL",required=True)
    category_structure=fields.Text("Category Structure")
    category_sequence=fields.Text("Category Sequence")
    parent_id=fields.Many2one("amazon.category.ept","Parent Category")
    sequence=fields.Integer("Base Category Sequence",default=1)
    child_categ_ids=fields.One2many("amazon.category.ept","parent_id",string="Child Categs")
    
class variation_theme_ept(models.Model):
    _name="amazon.variation.theme.ept"
    
    name=fields.Char("Theme",required=True)
    amazon_categ_id=fields.Many2one("amazon.category.ept",string="Categ",required=True)
    sequence=fields.Integer("Sequence",default=1)