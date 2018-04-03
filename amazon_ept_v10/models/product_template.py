# -*- encoding: utf-8 -*-

from openerp import models,fields,api

class product_template(models.Model):
    _inherit = 'product.template'
    
    @api.one
    @api.depends('amazon_categ_id')
    def get_child_categ(self):
        if self.amazon_categ_id.child_categ_ids:
            self.is_child_categ=True
        else:
            self.is_child_categ=False
    amazon_categ_id=fields.Many2one("amazon.category.ept",string="Amazon Category")
    child_categ_id=fields.Many2one('amazon.category.ept',string="Child Category")
    is_child_categ=fields.Boolean("Is Child Categ",compute="get_child_categ",store=True)
    variation_theme_id=fields.Many2one("amazon.variation.theme.ept",string="Variation Theme")
    parent_sku=fields.Char("Parent SKU")
    product_brand_id = fields.Many2one('product.brand', 'Brand',
        help='Select a brand for this product.')
    
    @api.onchange("amazon_categ_id","child_categ_id")
    def on_change_product_template(self):
        if self.variation_theme_id:
            if self.variation_theme_id.amazon_categ_id.id not in self.amazon_categ_id.ids+self.child_categ_id.ids:
                self.variation_theme_id=False
        if self.child_categ_id and self.amazon_categ_id and self.child_categ_id.parent_id.id!=self.amazon_categ_id.id:
            self.child_categ_id=False

