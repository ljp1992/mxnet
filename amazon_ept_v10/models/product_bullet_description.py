from openerp import models, fields

class amazon_product_bullet_description(models.Model):
    _name="amazon.product.bullet.description"
    
    amazon_product_id=fields.Many2one('amazon.product.ept',string="Product")
    name=fields.Text(string="Description")
    
class cspi_a_warning(models.Model):
    
    _name="amazon.cspia.warning.ept"
    
    name=fields.Char("CPSIAWarning")

class tsd_warning(models.Model):
    
    _name="amazon.tsd.warning.ept"

    name=fields.Char("TSDWarning")

class tsd_lanauge(models.Model):
    
    _name="amazon.tsd.language.ept" 

    name=fields.Char("TSDLanguage")
class option_payment_type_option(models.Model):
    _name="amazon.payment.type.option.ept"
    
    name=fields.Char("Payment Option")
class amazon_product_used_for(models.Model):
    _name="amazon.product.used.for"
    
    name=fields.Char("Used For")
class amazon_other_item_attributes(models.Model):
    _name="amazon.other.item.attributes"
    
    name=fields.Char("Attribute")
    
class amazon_target_audience(models.Model):
    _name="amazon.target.audience"
    
    name=fields.Char("Target Audience")
    
class amazon_subject_content(models.Model):
    _name="amazon.subject.content"
    
    name=fields.Char("Amazon Subject Content")
    
class amazon_platinum_keyword(models.Model):
    _name="amazon.platinum.keyword"

    name=fields.Char("Amazon Platinum Keyword")
    