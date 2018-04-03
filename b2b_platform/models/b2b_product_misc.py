# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
import odoo.addons.decimal_precision as dp
from odoo.osv import osv
from odoo.exceptions import UserError, AccessError
import uuid
import itertools
import psycopg2
from odoo.exceptions import ValidationError

class b2b_product_category(models.Model):
    _inherit = 'product.category'

    commission_rate = fields.Float(u'平台费率(%)')
    # markup_ids = fields.One2many('b2b.trader.markup', 'categ_id', u'价格上浮')

class B2bProductImage(models.Model):
    _name = 'product.image'
    _inherit = 'product.image'

    # product_prod_ids = fields.Many2many('product.product', 'image_product_product_rel','image_id', 'product_id', string=u'产品图片', domain="[('product_tmpl_id','=', product_tmpl_id)]")


class B2bOperatorCollectProduct(models.TransientModel):
    _name = 'b2b.operator.collect.product'
    _description = 'duplicate products from distributor to shops'

    product_id = fields.Many2one('product.template', u'产品')
    order_line = fields.One2many('b2b.operator.collect.product.line','order_id',u'店铺明细')

    def btn_collect(self):
        if self.order_line:
            for line in self.order_line:
                if not line.select and line.collect:
                    self.product_id.button_shop_collect_product(self.product_id,line.shop)

class B2bOperatorCollectProduct(models.TransientModel):
    _name = 'b2b.operator.collect.product.line'

    order_id = fields.Many2one('b2b.operator.collect.product', u'产品')
    shop = fields.Many2one('res.partner', u'店铺')
    select = fields.Boolean(u'已收录', readonly=True)
    collect = fields.Boolean(u'收录')

class B2bProductAttributevalue(models.Model):
    _inherit = "product.attribute.value"

    # price_ids = fields.One2many('product.attribute.price', 'value_id', 'Attribute Prices', readonly=True,
    #                             domain="[('product_tmpl_id','=',self._context['active_id'])]")

    @api.one
    def _compute_price_extra(self):
        amount = 0
        if self._context.get('active_id'):
            price = self.price_ids.filtered(lambda price: price.product_tmpl_id.id == self._context['active_id'])

            if price:
                for line in price:
                    amount += line.price_extra

            self.price_extra = amount
        else:
            self.price_extra = 0.0


class B2bProductAttributePrice(models.Model):
    _inherit = "product.attribute.price"

    @api.multi
    def write(self, values):
        if values.get('price_extra'):
            new_price = values.get('price_extra')
            for rec in self:
                prod_tmpls = self.env['product.template'].sudo().search([('master_product','=',rec.product_tmpl_id.id)])
                mod_time = fields.Datetime.now()
                for prod_tmpl in prod_tmpls:
                    rate = 0
                    markup = 0
                    if prod_tmpl.categ_id and prod_tmpl.categ_id.commission_rate:
                        rate = prod_tmpl.categ_id.commission_rate
                    else:
                        categ = self.env['product.category'].sudo().search([('parent_id', '=', False)],limit=1)
                        if categ:
                            rate = categ.commission_rate
                    if prod_tmpl.product_owner and prod_tmpl.product_owner.type == 'shop':
                        markup = prod_tmpl.product_owner.shop_markup or 0
                    prod_attr_id = self.search([('product_tmpl_id','=',prod_tmpl.id),('value_id','=',rec.value_id.id)],limit=1)
                    if prod_attr_id:
                        prod_attr_id.price_extra = new_price * (1 + rate/100.0) * (1 + markup/100.0)
                        prod_prod = self.env['product.product'].search(
                            [('product_tmpl_id', '=', prod_tmpl.id), ('attribute_value_ids', 'in', rec.value_id.id)], limit=1)
                        if prod_prod:
                            prod_prod.write({'price_update':'pending', 'price_mod_time':mod_time})
                            prod_prod._set_product_lst_price()
        return super(B2bProductAttributePrice, self).write(values)

class B2bDistributorAmazonTemplate(models.Model):
    _name = "b2b.distributor.amazon.template"

    name = fields.Char(u'模板名称')
    partner = fields.Many2one('res.partner', u'经销商', required=True,
                  default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id,
                  domain=lambda self: [('id', '=', self.env.user.partner_id.id)])
    supplier_name = fields.Char(u'厂商名称')
    brand = fields.Char(u'产品品牌')
    prefix = fields.Char(u'品名前缀')
    suffix = fields.Char(u'品名后缀')
    declaration = fields.Text(u'重要声明')
    key_points = fields.Text(u'要点说明')
    keywords = fields.Char(u'关键字')
    prefix_description = fields.Text(u'产品描述前缀')
    suffix_description = fields.Text(u'产品描述后缀')

    product_brand_id = fields.Many2one('product.brand', string=u'品牌')
    manufacture_id = fields.Many2one('res.partner', related='product_brand_id.partner_id', store=False,
                                     string=u'制造商')
    browse_node_id = fields.Many2one('amazon.browse.node.ept', string=u'商品类别')
    amazon_categ_id = fields.Many2one("amazon.category.ept", string=u"Amazon Category")
    child_categ_id = fields.Many2one('amazon.category.ept', string=u"Child Category")
    variation_theme_id = fields.Many2one("amazon.variation.theme.ept", string=u"Variation Theme")

class B2bShopCollectConvert(models.TransientModel):
    _name = "b2b.shop.collect.convert"
    _rec_name = 'shop_id'

    template_id = fields.Many2one('b2b.distributor.amazon.template', u'模板')
    shop_id = fields.Many2one('res.partner', u'店铺', required=True,
              domain=lambda self: ['&','|',('parent_id', '=', self.env.user.partner_id.parent_id.id),
                                   ('parent_id', '=', self.env.user.partner_id.id),('type','=','shop')])
    supplier_name = fields.Char(u'厂商名称')
    brand = fields.Char(u'产品品牌')
    prefix = fields.Char(u'品名前缀')
    suffix = fields.Char(u'品名后缀')
    declaration = fields.Text(u'重要声明')
    key_points = fields.Text(u'要点说明')
    keywords = fields.Char(u'关键字')
    prefix_description = fields.Text(u'产品描述前缀')
    suffix_description = fields.Text(u'产品描述后缀')

    have_child_categ = fields.Boolean(compute='_get_have_child_categ', string=u'amazon_categ_id是否有子category')

    country_id = fields.Many2one('res.country', related='shop_id.country_id', string=u'国家')
    browse_node_id = fields.Many2one('amazon.browse.node.ept', string=u'商品类别')
    amazon_categ_id = fields.Many2one("amazon.category.ept", string=u"Amazon Category")
    child_categ_id = fields.Many2one('amazon.category.ept', string=u"Child Category")
    variation_theme_id = fields.Many2one("amazon.variation.theme.ept", string=u"Variation Theme")
    product_brand_id = fields.Many2one('product.brand', string=u'品牌')
    manufacture_id = fields.Many2one('res.partner', related='product_brand_id.partner_id', string=u'制造商')

    @api.multi
    def _get_have_child_categ(self):
        for record in self:
            if record.amazon_categ_id.child_categ_ids:
                record.have_child_categ = True
            else:
                record.have_child_categ = False

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.supplier_name = self.template_id.supplier_name
            self.brand = self.template_id.brand
            self.prefix = self.template_id.prefix
            self.suffix = self.template_id.suffix
            self.declaration = self.template_id.declaration
            self.key_points = self.template_id.key_points
            self.keywords = self.template_id.keywords
            self.prefix_description = self.template_id.prefix_description
            self.suffix_description = self.template_id.suffix_description
            self.product_brand_id = self.template_id.product_brand_id.id
            self.amazon_categ_id = self.template_id.amazon_categ_id.id
            self.browse_node_id = self.template_id.browse_node_id.id

    @api.onchange('shop_id')
    def onchange_shop_id(self):
        if self.browse_node_id and self.shop_id and self.shop_id.country_id != self.browse_node_id.country_id:
            raise UserError(u'店铺与商品类别所属国家不一致！')

    @api.onchange('browse_node_id')
    def onchange_browse_node_id(self):
        if self.browse_node_id and self.shop_id and self.shop_id.country_id != self.browse_node_id.country_id:
            raise UserError(u'店铺与商品类别所属国家不一致！')

    @api.multi
    def create_or_update_amazon_product(self, template):
        '''创建亚马逊产品 v1.0'''
        amazon_product_ept_obj = self.env['amazon.product.ept']
        # print 'template:', template
        instance = template.product_owner.amazon_instance_id
        # print 'instance_id:', instance.id
        products = template.product_variant_ids
        # print 'products:', products
        if len(products) == 1:  # no variation
            product = products[0]
            # standard_product_id_type = self.env['b2b.upc.list'].search([('product', '=', product.id),
            #                                                             ('shop_id', '=', instance.id)])
            val = {
                'instance_id': instance.id,
                'product_id': product.id,
                'seller_sku': product.default_code,
                'product_upc': product.barcode,
                'amazon_browse_node_id': False,
                'condition': instance.condition or 'New',
                'tax_code_id': instance.default_amazon_tax_code_id and instance.default_amazon_tax_code_id.id or False,
                'long_description': template.description or False,
                'variation_data': False,
                'standard_product_id_type': 'UPC',
            }
            amazon_product = amazon_product_ept_obj.create(val)
            # print 'amazon_product:', amazon_product
        elif len(products) > 1:
            for product in products:
                val = {
                    'instance_id': instance.id,
                    'product_id': product.id,
                    'seller_sku': product.default_code,
                    'product_upc': product.barcode,
                    'amazon_browse_node_id': False,
                    'condition': instance.condition or 'New',
                    'tax_code_id': instance.default_amazon_tax_code_id and instance.default_amazon_tax_code_id.id or False,
                    'long_description': template.description or False,
                    'variation_data': 'child',
                    'standard_product_id_type': 'UPC',
                }
                amazon_product = amazon_product_ept_obj.create(val)

class B2bDistAssignCateg(models.TransientModel):
    _name = "b2b.dist.assign.categ"
    _rec_name = 'trader_categ_id'

    trader_categ_id = fields.Many2one('b2b.trader.markup', u'商户内部分类')

    def btn_assign(self):
        for product in self._context.get('product_ids'):
            product_id = self.env['product.template'].with_context(collection_mark='collected').browse(product)
            product_id.trader_categ_id = self.trader_categ_id
        return {
            'name': '已收录的产品',
            'view_type': 'form',
            "view_mode": 'tree,form',
            'res_model': 'product.template',
            'type': 'ir.actions.act_window',
            'views': [(False, 'tree'),(False, 'form')],
            'context': {'create': False, 'collection_mark':'collected'},
            'domain': [('distributor_collected_product','=',True)]
            }

class B2bOtherPlatform(models.Model):
    _name = "b2b.other.platform"

    name = fields.Char(u'平台名称')


class B2bUPCList(models.Model):
    _name = "b2b.upc.list"

    name = fields.Char(u'UPC编码', required=True)
    type = fields.Selection([('UPC', u'UPC')], u'类型', default='UPC')
    state = fields.Selection([('vacant', u'未用'),('taken',u'已用')], u'状态', default='vacant')
    owner = fields.Many2one('res.partner', u'经销商',
                            default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    shop_id = fields.Many2one('res.partner', u'店铺')
    product = fields.Many2one('product.product', u'产品')
    SKU_ID = fields.Char(u'SKU ID', related='product.default_code', readonly=True)

    _sql_constraints = [
        ('name_unique', 'unique( name )', u'UPC编码必须唯一')
    ]

    @api.one
    def assign_upc_codes(self):
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        product_obj = self.env['product.product'].sudo()
        # for code in self.search([('owner','=',distributor.id),('state','=','vacant')]):
        product = product_obj.search([('product_owner.type','=','shop'),
                                       ('product_owner.parent_id','=',distributor.id),
                                       ('barcode','=',False)],limit=1)
        if product:
            product.write({'barcode':self.name})
            self.write(({'state':'taken', 'shop_id':product.product_owner.id, 'product':product.id}))


class B2bProductChangeQuantity(models.TransientModel):
    _inherit = "stock.change.product.qty"

    location_id = fields.Many2one('stock.location', 'Location', required=True,
                    domain = lambda self: [('usage', '=', 'internal'),
                                           ('partner_id', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id),
                                           ('location_id', '=', self.env.ref('b2b_platform.stock_location_wh_suppliers').id)])

    @api.model
    def default_get(self, fields):
        res = super(B2bProductChangeQuantity, self).default_get(fields)
        if not res.get('product_id') and self.env.context.get('active_id') and self.env.context.get(
                'active_model') == 'product.template' and self.env.context.get('active_id'):
            res['product_id'] = self.env['product.product'].search(
                [('product_tmpl_id', '=', self.env.context['active_id'])], limit=1).id
        elif not res.get('product_id') and self.env.context.get('active_id') and self.env.context.get(
                'active_model') == 'product.product' and self.env.context.get('active_id'):
            res['product_id'] = self.env['product.product'].browse(self.env.context['active_id']).id
        if 'location_id' in fields:
            res['location_id'] = self.env['stock.location'].search([('usage', '=', 'internal'),
                                ('partner_id', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id),
                                ('location_id', '=', self.env.ref('b2b_platform.stock_location_wh_suppliers').id)]).id or False
        return res