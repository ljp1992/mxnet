from openerp import models,fields,api
class res_country(models.Model):
    _inherit="res.country"
    
    amazon_marketplace_code = fields.Char('Amazon Marketplace Code',size=10,default=False)

    @api.model_cr
    def init(self):
        #Here we can set have_marketplace=true for country that have Amazon marketplace
        self._cr.execute("""update res_country set amazon_marketplace_code=code 
                    where code in ('CA','US','DE','ES','FR','IN','IT','JP','CN')""")
        self._cr.execute("""update res_country set amazon_marketplace_code = 'UK' 
                    where code='GB'""") #United Kingdom Amazon marketplace code is UK and Country Code for United Kingdom is GB.
        