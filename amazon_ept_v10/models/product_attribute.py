from openerp import models,fields,api
class product_attribute(models.Model):
    _inherit="product.attribute"    

    @api.one
    @api.depends('amazon_categ_id')
    def get_child_categ(self):
        if self.amazon_categ_id.child_categ_ids:
            self.is_child_categ=True
        else:
            self.is_child_categ=False
    
    @api.onchange('amazon_categ_id')
    def on_change_amazon_categ(self):
        self.child_categ_id=False
    amazon_attribute_id=fields.Many2one("amazon.attribute.ept",string="Amazon Attribute")    
    amazon_categ_id=fields.Many2one("amazon.category.ept",string="Amazon Category")
    child_categ_id=fields.Many2one("amazon.category.ept",string="Child Category")
    is_child_categ=fields.Boolean("Is Child Categ",compute="get_child_categ",store=True)
    
class amazon_attribute_ept(models.Model):
    _name="amazon.attribute.ept"
    _order="sequence"
    name=fields.Char("Name")
    max_occurs=fields.Integer("Max Occurs")
    min_occurs=fields.Integer("Min Occurs")
    sequence=fields.Integer("Sequence")
    amazon_categ_id=fields.Many2one("amazon.category.ept",string="Amazon Category")
    uom_type_id=fields.Many2one("amazon.uom.type.ept",string="UOm")
class attribute_value_ept(models.Model):
    _name="amazon.attribute.value.ept"
    
    name=fields.Char("Value",required=True)
    sequence=fields.Integer("Sequence")
    attribute_id=fields.Many2one("amazon.attribute.ept",string="Attribute")    
class amazon_attribute_line_ept(models.Model):
    _name="amazon.attribute.line.ept"
    
    product_id=fields.Many2one("amazon.product.ept",string="Product")
    attribute_id=fields.Many2one("amazon.attribute.ept",string="Attribute")    
    value_ids=fields.Many2many('amazon.attribute.value.ept','amazon_attribute_line_ept_ref','attribute_id','product_id',string="Values")
    uom_type_id=fields.Many2one("amazon.uom.type.ept",string="UOm",related="attribute_id.uom_type_id",store=False,readonly=True)
    uom_type=fields.Char("Uom",default="unitOfMeasure",readonly=True)
    value_id=fields.Many2one("amazon.uom.value.ept",string="Value")
class amazon_uom_ept(models.Model):
    _name="amazon.uom.type.ept"    
    name=fields.Char("value")
class amazon_uom_value_ept(models.Model):
    _name="amazon.uom.value.ept"    
    name=fields.Char("name")
    uom_type_id=fields.Many2one("amazon.uom.type.ept",string="UOm")