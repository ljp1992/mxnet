# -*- coding: utf-8 -*-
###########################################################################################
#
#    author:Qingdao Odoo Software Co., Ltd
#    module name for Qdodoo
#    Copyright (C) 2015 qdodoo Technology CO.,LTD. (<http://www.qdodoo.com/>).
#
###########################################################################################

from odoo import models, fields, api
from odoo.osv import osv
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError

class b2b_trader_markup(models.Model):
    """
        商户内部产品分类及价格上浮率
    """
    _name = 'b2b.trader.markup'
    _description = "distributor and shop price markup rate"
    _parent_name = 'parent_id'

    partner = fields.Many2one('res.partner', u'商户', required=True,
                default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id,
                domain = lambda self: [('owner', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)])
    # categ_id = fields.Many2one('product.category', u'产品分类')
    name = fields.Char(u'分类名称', required=True)
    display_name = fields.Char(u'分类全称', compute='_get_full_name')
    # seq = fields.Integer(u'排序')
    search_name = fields.Char(u'全称', compute=lambda self: True, search='_search_display_name')
    parent_id = fields.Many2one('b2b.trader.markup', u'上级分类', index=True, ondelete='cascade')
    children_ids = fields.One2many('b2b.trader.markup', 'parent_id', u'子类别')
    rate = fields.Float(u'上浮率(%)', digits=(16, 2))
    product_disclosure = fields.Selection(u'产品开放级别', related='partner.product_disclosure', readonly=True)
    allow_dist = fields.One2many('b2b.allowed.distributor', 'categ_id', u'开放的经销商')

    def _get_full_name(self):
        def get_names(cat):
            """ Return the list [cat.name, cat.parent_id.name, ...] """
            res = []
            while cat:
                res.append(cat.name)
                cat = cat.parent_id
            return res

        for cat in self:
            cat.display_name = " / ".join(reversed(get_names(cat)))

    @api.multi
    def _search_display_name(self, operator, value):
        obj = self.env['b2b.trader.markup']
        records = obj.search([('name','!=',False)])
        ids = []
        for rec in records:
            if value in rec.display_name :
                ids.append(rec.id)
        return [('id', 'in', ids)]

    @api.one
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion(parent='parent_id'):
            raise ValidationError('上级分类无效!')

    @api.multi
    def write(self, values):
        if values.get('rate'):
            rate = values.get('rate')
            for rec in self:
                prod_tmpl_obj = self.env['product.template'].with_context({'collection_mark':'collected'})
                prod_prod_obj = self.env['product.product'].with_context({'collection_mark': 'collected'})
                prod_attr_price_obj = self.env['product.attribute.price'].sudo()
                dist_prods = prod_tmpl_obj.search([('product_owner','=',rec.partner.id),('trader_categ_id','=',rec.id),('master_product','!=',False)])
                # 更新经销商收录的产品
                if dist_prods:
                    for d_prod in dist_prods:
                        d_prod.list_price = d_prod.master_product.list_price * (1 + rate / 100.0)

                        d_attr_val = d_prod.mapped('attribute_line_ids')
                        for value in d_attr_val:
                            vlu = value[0].id
                            d_attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', d_prod.master_product.id),
                                                                 ('value_id', '=', vlu)])
                            if d_attr_price:
                                d_attr_price.write({'price_extra': d_attr_price.price_extra * (1 + rate /100.0)})
                # 更新店铺中收录的产品
                shop_prods = prod_tmpl_obj.search([('product_owner.parent_id','=',rec.partner.id),('trader_categ_id','=',rec.id)])
                if shop_prods:
                    mod_time = fields.Datetime.now()
                    for s_prod in shop_prods:
                        markup = s_prod.product_owner.shop_markup or 0
                        s_prod.list_price = s_prod.master_product.list_price * (1 + rate / 100.0) * (1 + markup / 100.0)

                        s_attr_val = s_prod.mapped('attribute_line_ids')
                        for value in s_attr_val:
                            vlu = value[0].id
                            s_attr_price = prod_attr_price_obj.search([('product_tmpl_id.master_product', '=', s_prod.id),
                                                                 ('value_id', '=', vlu)])
                            if s_attr_price:
                                s_attr_price.write({'price_extra': s_attr_price.price_extra * (1 + rate /100.0) * (1 + markup / 100.0)})
                        for prod in prod_prod_obj.search([('product_tmpl_id','=',s_prod.id)]):
                            prod._set_product_lst_price()
                            prod.write({'price_update': 'pending', 'price_mod_time': mod_time})
        return super(b2b_trader_markup, self).write(values)


class b2b_allowed_distributor(models.Model):
    """
        针对供应商的内部分类，哪些经销商可以看到该分类下的产品
    """
    _name = 'b2b.allowed.distributor'

    categ_id = fields.Many2one('b2b.trader.markup', u'内部分类', required=True)
    distributor = fields.Many2one('res.partner', u'经销商', domain=[('is_company','=',True),('is_company','=',True),('parent_id','=',False)])

class b2b_amazon_category(models.Model):
    """
        亚马逊中的产品分类
    """
    _name = 'b2b.amazon.category'
    _description = "product categories from Amazon"
    _parent_name = 'parent_id'

    name = fields.Char(u'分类名称', required=True)
    display_name = fields.Char(u'分类全称', compute='_get_full_name')
    search_name = fields.Char(u'全称', compute=lambda self: True, search='_search_display_name')
    parent_id = fields.Many2one('b2b.amazon.category', u'上级分类', index=True, ondelete='cascade')
    children_ids = fields.One2many('b2b.amazon.category', 'parent_id', u'子类别')


    #channel_mapping_ids = fields.One2many(
    #    string='Mappings',
    #    comodel_name='channel.category.mappings',
    #    inverse_name='category_name',
    #    copy=False
    #)

    #channel_category_ids = fields.One2many(
    #    string='Channel Categories',
    #    comodel_name='extra.categories',
    #    inverse_name='category_id',
    #    copy=False
    #)

    def _get_full_name(self):
        def get_names(cat):
            """ Return the list [cat.name, cat.parent_id.name, ...] """
            res = []
            while cat:
                res.append(cat.name)
                cat = cat.parent_id
            return res

        for cat in self:
            cat.display_name = " / ".join(reversed(get_names(cat)))

    @api.multi
    def _search_display_name(self, operator, value):
        obj = self.env['b2b.amazon.category']
        records = obj.search([('name','!=',False)])
        ids = []
        for rec in records:
            if value in rec.display_name :
                ids.append(rec.id)
        return [('id', 'in', ids)]

    @api.one
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion(parent='parent_id'):
            raise ValidationError('上级分类无效!')





