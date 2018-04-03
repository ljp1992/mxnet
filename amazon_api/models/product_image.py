# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _
import urllib2, base64
from odoo.exceptions import UserError

class ProductImage(models.Model):
    _inherit = "product.image"

    oss2_url = fields.Char(string=u'图片')

    tmpl_main = fields.Boolean(string=u'主图', default=False, help=u'template main image')
    # product_main = fields.Boolean(string=u'主图', default=False, help=u'product main image')

    parent_id = fields.Many2one('product.image', string=u'供应商产品图片')

    child_ids = fields.One2many('product.image', 'parent_id', string=u'经销商产品和店铺产品图片')

    products = fields.Many2many('product.product', 'product_product_image_rel', 'image_id', 'product_id', string=u'产品')
    main_products = fields.Many2many('product.product', 'product_main_image_rel', 'image_id', 'product_id', string=u'主产品')

    image_type =  fields.Selection([
        ('Main','Main'),
        ('Swatch','Swatch'),
        ('BKLB','BKLB'),
        ('PT1','PT1'),
        ('PT2','PT2'),
        ('PT3','PT3'),
        ('PT4','PT4'),
        ('PT5','PT5'),
        ('PT6','PT6'),
        ('PT7','PT7'),
        ('PT8','PT8'),
        ('Search','Search'),
        ('PM01','PM01'),
        ('MainOfferImage',
         'MainOfferImage'),
        ('OfferImage1','OfferImage1'),
        ('OfferImage2','OfferImage2'),
        ('OfferImage3','OfferImage3'),
        ('OfferImage4','OfferImage4'),
        ('OfferImage5','OfferImage5'),
        ('PFEE','PFEE'),('PFUK','PFUK'),
        ('PFDE','PFDE'),('PFFR','PFFR'),
        ('PFIT','PFIT'),('PFES','PFES'),
        ('EEGL','EEGL')], string=u'图片类型',deault='Main')

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        '''主图'''
        context = self._context or {}
        result = super(ProductImage, self).search(args, offset, limit, order, count=count)
        if context.has_key('selected_main_images') and context.has_key('selected_other_images'):
            main_images = context['selected_main_images']
            other_images = context['selected_other_images']
            main_image_ids = []
            other_image_ids = []
            if len(main_images) == 1 and len(main_images[0]) == 3:
                main_image_ids = main_images[0][2]
            if len(other_images) == 1 and len(other_images[0]) == 3:
                other_image_ids = other_images[0][2]
            selected_image_ids = set(main_image_ids + other_image_ids)
            show_image_ids = []
            for image in result:
                if image.id not in selected_image_ids:
                    show_image_ids.append(image.id)
            result = self.env['product.image'].browse(show_image_ids)
        return result

    @api.multi
    def write(self, val):
        result = super(ProductImage, self).write(val)
        for image in self:
            template = image.product_tmpl_id
            if len(template.main_images) > 1:
                raise UserError(u'只能选一张主图！')
        return result

    @api.multi
    def set_main_image(self):
        '''设为主图'''
        self.ensure_one()
        self.tmpl_main = True
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.multi
    def set_minor_image(self):
        '''设为副图'''
        self.ensure_one()
        self.tmpl_main = False
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
