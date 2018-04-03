# -*- coding: utf-8 -*-

from odoo import models, fields, api

class product_image(models.Model):
    _name = 'product.image'
    _order = 'sequence, id DESC'

    name = fields.Char('Name')
    description = fields.Text(u'描述')
    sequence = fields.Integer(u'序号')
    image_alt = fields.Text(u'图片标签')
    image_id = fields.Many2one('ir.attachment', u'图片库')
    image = fields.Char(u'图片', related='image_id.url', readonly=True)
    image_small = fields.Binary(u'小图')
    product_tmpl_id = fields.Many2one('product.template', u'产品模板', index=True)
    from_main_image = fields.Boolean(u'来自主图', default=False)
    selectable = fields.Boolean(u'可选', compute='_if_selectable', search='_get_select_list')

    @api.one
    def _if_selectable(self):
        product_id = self._context.get('product')
        product = self.env['product.product'].search([('id','=',product_id)])
        if product.product_tmpl_id == self.product_tmpl_id:
            self.selectable = True

    def _get_select_list(self,operator,value):
        ids = []
        product_id = self._context.get('product')
        product = self.env['product.product'].search([('id', '=', product_id)])
        lines = self.search([('product_tmpl_id','=',product.product_tmpl_id.id)])
        if lines:
            for line in lines:
                ids.append(line.id)
        return [('id', 'in', ids)]


class product_product(models.Model):
    _inherit = 'product.product'

    images = fields.Many2many('product.image', 'product_product_image_rel', 'product_id', 'image_id', string=u'图片')


class product_template(models.Model):
    _inherit = 'product.template'

    images = fields.One2many('product.image', 'product_tmpl_id', string=u'图片')

    # @api.one
    # def action_copy_image_to_images(self):
    #     if not self.image:
    #         return
    #     image = None
    #     for r in self.images:
    #         if r.from_main_image:
    #             image = r
    #             break
    #
    #     if image:
    #         image.image = self.image
    #     else:
    #         vals = {'image': self.image,
    #                 'name': self.name,
    #                 'product_tmpl_id': self.id,
    #                 'from_main_image': True, }
    #         self.env['product.image'].create(vals)
