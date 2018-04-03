from openerp import models, fields

class product_image_ept(models.Model):
    _name = 'product.image.ept'
    
    product_id = fields.Many2one('product.product', string='Product',required=True)
    name = fields.Char(size=60, string='Name', required=True)
    url = fields.Char(size=600, string='Image URL')    
    image_type =  fields.Selection([('Main','Main'),('Swatch','Swatch'),('BKLB','BKLB'),('PT1','PT1'),('PT2','PT2'),('PT3','PT3'),('PT4','PT4'),('PT5','PT5'),('PT6','PT6'),('PT7','PT7'),('PT8','PT8'),('Search','Search'),('PM01','PM01'),('MainOfferImage','MainOfferImage'),('OfferImage1','OfferImage1'),('OfferImage2','OfferImage2'),('OfferImage3','OfferImage3'),('OfferImage4','OfferImage4'),('OfferImage5','OfferImage5'),('PFEE','PFEE'),('PFUK','PFUK'),('PFDE','PFDE'),('PFFR','PFFR'),('PFIT','PFIT'),('PFES','PFES'),('EEGL','EEGL')], string='Image Type',deault='Main')