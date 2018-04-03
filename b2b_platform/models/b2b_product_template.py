# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
import odoo.addons.decimal_precision as dp
from odoo.osv import osv
from odoo.exceptions import UserError, AccessError
import uuid
import itertools
import psycopg2
from odoo.exceptions import ValidationError
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Feeds

class b2b_product_template(models.Model):
    _inherit = 'product.template'

    list_price = fields.Float(
        'Sale Price', default=1.0,
        digits=dp.get_precision('Product Price'),
        help="Base price to compute the customer price. Sometimes called the catalog price.",
        track_visibility='onchange')
    dist_price = fields.Float(u'成本价', digits=(16,2))

    trader_categ_id = fields.Many2one('b2b.trader.markup', inverse='_seller_add_price', string=u'商户内部分类')
    product_owner = fields.Many2one('res.partner', u'产品所有者', index=True,
                    default=lambda self:self.env['res.users'].sudo().browse(self._uid).partner_id.parent_id or
                                        self.env['res.users'].sudo().browse(self._uid).partner_id)
    browse_node_id = fields.Many2one('amazon.browse.node.ept', string=u'商品类别')
    manufacture_id = fields.Many2one('res.partner', related='product_brand_id.partner_id', store=False, string=u'制造商')
    master_product = fields.Many2one('product.template', u'平台主产品', index=True)
    shop_operator = fields.Many2one('res.partner', u'店铺管理员', related='product_owner.shop_operator', readonly=True)
    distributor = fields.Many2one('res.partner', u'所属经销商', related='product_owner.parent_id', readonly=True)

    platform_published = fields.Boolean(u'已发布到平台')
    user_is_product_owner = fields.Boolean(u'自有产品', compute='_is_own_product', search='_search_own_product_list')
    platform_is_product_owner = fields.Boolean(u'平台产品目录', compute='_search_platform_product_list', search='_search_platform_product_list')
    distributor_collected_product = fields.Boolean(u'已收录产品', compute='_search_collected_product_list', search='_search_collected_product_list')
    product_in_own_shops = fields.Boolean(u'商铺产品', compute='_template_in_user_shop', search='_search_shop_product_list')
    collected_mark = fields.Boolean(u'收录', compute='_set_collection_mark')
    to_collect_mark = fields.Boolean(u'待收录', compute='_to_collect_mark')
    shop_collected = fields.Boolean(u'店铺已收录', compute='_set_shop_collection_mark')

    modify_state = fields.Selection([('new', u'已接收'), ('confirmed', u'已确认')], u'价格变更', index=True)
    prod_mod_state = fields.Selection([('new', u'已接收'), ('confirmed', u'已确认')], u'产品变更', index=True)
    image_mod_state = fields.Selection([('new', u'已接收'), ('confirmed', u'已确认')], u'图片变更', index=True)
    stock_mod_state = fields.Selection([('new', u'已接收'), ('confirmed', u'已确认')], u'库存变更', index=True)
    variant_mod_state = fields.Selection([('new', u'已接收'), ('confirmed', u'已确认')], u'关系变更', index=True)

    overall_avail_qty = fields.Float(u'总库存', related='master_product.qty_available')
    #
    # type = fields.Selection([
    #     ('consu', 'Consumable')),
    #     ('service', _('Service'))], string='Product Type', default='consu', required=True,)

    # amazon_categ_id = fields.Many2one('b2b.amazon.category', u'亚马逊分类')

    customs_unit_price = fields.Float(u'申报单价', digits=(16,2))
    declaration_chinese = fields.Text(u'申报中文')
    declaration_english = fields.Text(u'申报英文')

    system_id = fields.Char(u'系统编号')
    brand = fields.Char(u'品牌名称')
    prod_source = fields.Char(u'产品来源网址')
    pack_weight = fields.Float(u'包装重量')
    pack_method = fields.Char(u'包装方式')
    material = fields.Char(u'产品材料')
    has_battery = fields.Boolean(u'是否带电池')
    cp_violation = fields.Many2many('b2b.other.platform', 'id', u'侵权平台')
    target_users = fields.Char(u'适合人群')

    product_chinese = fields.Boolean(u'中文内容', default=True)
    product_english = fields.Boolean(u'英文内容')
    product_german = fields.Boolean(u'德文内容')
    product_french = fields.Boolean(u'法文内容')
    product_spanish = fields.Boolean(u'西班牙文内容')
    product_italian = fields.Boolean(u'意大利文内容')
    product_japanese = fields.Boolean(u'日文内容')

    product_title = fields.Char(u'产品标题')
    product_keyword = fields.Char(u'关键词')
    product_briefing = fields.Text(u'重点说明')
    product_description = fields.Text(u'产品描述')

    product_title_english = fields.Char(u'产品标题(英文)')
    product_keyword_english = fields.Char(u'关键词(英文)')
    product_briefing_english = fields.Text(u'重点说明(英文)')
    product_description_english = fields.Text(u'产品描述(英文)')

    product_title_german = fields.Char(u'产品标题(德文)')
    product_keyword_german = fields.Char(u'关键词(德文)')
    product_briefing_german = fields.Text(u'重点说明(德文)')
    product_description_german = fields.Text(u'产品描述(德文)')

    product_title_french = fields.Char(u'产品标题(法文)')
    product_keyword_french = fields.Char(u'关键词(法文)')
    product_briefing_french = fields.Text(u'重点说明(法文)')
    product_description_french = fields.Text(u'产品描述(法文)')

    product_title_spanish = fields.Char(u'产品标题(西班牙文)')
    product_keyword_spanish = fields.Char(u'关键词(西班牙文)')
    product_briefing_spanish = fields.Text(u'重点说明(西班牙文)')
    product_description_spanish = fields.Text(u'产品描述(西班牙文)')

    product_title_italian = fields.Char(u'产品标题(意大利文)')
    product_keyword_italian = fields.Char(u'关键词(意大利文)')
    product_briefing_italian = fields.Text(u'重点说明(意大利文)')
    product_description_italian = fields.Text(u'产品描述(意大利文)')

    product_title_japanese = fields.Char(u'产品标题(日文)')
    product_keyword_japanese = fields.Char(u'关键词(日文)')
    product_briefing_japanese = fields.Text(u'重点说明(日文)')
    product_description_japanese = fields.Text(u'产品描述(日文)')
    main_image_attachment_id = fields.Many2one('ir.attachment', u'主图片附件Id')

    ############################# ljp added #######################################################

    deal_days = fields.Integer(string=u'处理天数', default=1)

    cost_price = fields.Monetary(string=u'供应商成本价')
    platform_price = fields.Monetary(string=u'平台价格')
    seller_price = fields.Monetary(string=u'经销商价格')
    shop_price = fields.Monetary(string=u'店铺价格')

    seller_template_id = fields.Many2one('product.template', string=u'经销商产品')

    b2b_type = fields.Selection([
        ('supplier', u'供应商'),
        ('seller', u'经销商'),
        ('shop', u'店铺')], default='supplier', string=u'产品类型')

    def _seller_add_price(self):
        for template in self:
            seller_rate = (template.trader_categ_id and template.trader_categ_id.rate or 0) / 100
            template.seller_price = template.master_product.platform_price * (1 + seller_rate)
            for product in template.product_variant_ids:
                print product.master_product
                print product.master_product.platform_price
                product.seller_price = product.master_product.platform_price * (1 + seller_rate)

    @api.multi
    def name_get(self):
        return [(template.id, '%s' % template.name[0:50] + '...' if len(template.name) > 50 else template.name)
                for template in self]
        # return [(template.id, '%s%s' % (template.default_code and '[%s] ' % template.default_code or '', template.name))
        #         for template in self]

    # @api.multi
    # def _is_own_product(self):
    #     user_id = self.env.user
    #     # 所有者是供应商管理员
    #     if self.product_owner and self.product_owner == user_id.partner_id and not self.master_product:
    #         self.user_is_product_owner = True
    #     # 所有者是供应商
    #     elif self.product_owner and user_id.partner_id.parent_id and self.product_owner == user_id.partner_id.parent_id and not self.master_product:
    #         self.user_is_product_owner = True
    #     # 都不是
    #     else:
    #         self.user_is_product_owner = False

    @api.multi
    def button_operator_collect_product(self):
        return {
            'type': 'ir.actions.act_window',
            'name': u'发布到店铺',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'b2b.shop.collect.convert',
            # 'views': [(self.env.ref('amazon_api.get_product_data_wizard').id, 'form')],
            'target': 'current',
        }

    @api.multi
    def _is_own_product(self):
        partner = self.env.user.partner_id
        parent_partner = partner.parent_id or partner
        for template in self:
            template.user_is_product_owner = False
            if template.master_product:
                product_owner = template.product_owner
                if product_owner == parent_partner or product_owner.parent_id == parent_partner:
                    template.user_is_product_owner = True
            else:
                if template.product_owner == parent_partner:
                    template.user_is_product_owner = True

    def _search_own_product_list(self, operator, value):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        lines = self.search([('product_owner', '=', partner.id)])
        return [('id', 'in', lines.ids)]

    def _search_platform_product_list(self, operator, value):
        # 产品目录库内要展示的产品包括： 完全开放的供应商所辖的产品，部分开放的供应商其下公开的产品分类下的产品，以及供应商可查看自己发布的产品
        # 前提条件： 平台主产品字段为空（即供应商的产品），已发布字段为True
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        allow_obj = self.env['b2b.allowed.distributor'].sudo()
        ids = []
        lines = self.search([('master_product', '=', False), ('platform_published','=',True)])
        for line in lines:
            level = line.product_owner.product_disclosure
            if level == 'open':
                ids.append(line.id)
            elif level == 'semi' and allow_obj.search([('categ_id','=',line.trader_categ_id.id),('distributor','=',partner.id)]):
                ids.append(line.id)
            elif line.product_owner == partner:
                ids.append(line.id)
        return [('id', 'in', ids)]

    def _search_collected_product_list(self, operator, value):
        root_partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        lines = self.search([('master_product', '!=', False), ('product_owner', '=', root_partner.id)])
        return [('id', 'in', lines.ids)]

    @api.one
    def _set_collection_mark(self):
        user_id = self.env.user
        products = self.env['product.template']
        if user_id.partner_id.parent_id:
            collections = products.search([('master_product', '=', self.id), ('product_owner', '=', user_id.partner_id.parent_id.id)], limit=1)
        else:
            collections = products.search([('master_product','=',self.id), ('product_owner', '=', user_id.partner_id.id)], limit=1)
        if collections:
            self.collected_mark = True
        else:
            self.collected_mark = False

    @api.multi
    def _to_collect_mark(self):
        user_id = self.env.user
        distributor = user_id.partner_id.parent_id or user_id.partner_id
        product_obj = self.env['product.template']
        products = product_obj.search([('master_product', '!=', False),('product_owner','=',distributor.id)])
        shops = self.env['res.partner'].search([('shop_operator', '=', user_id.partner_id.id)])
        if products and shops:
            for product in products:
                product.to_collect_mark = False
                for shop in shops:
                    shop_collection = product.search([('master_product', '=', product.master_product.id),('product_owner','=',shop.id)])
                    if not shop_collection:
                        product.to_collect_mark = True
                        continue

    @api.one
    def _set_shop_collection_mark(self):
        partner = self.env.user.partner_id
        prod_tmpl_obj = self.env['product.template']

        # 如果登录用户是店铺账号
        if partner.type == 'shop' and self.product_owner == partner:
            self.shop_collected = True
        # 如果是非管理员， 并且产品所有者为经销商
        elif partner.parent_id and self.product_owner == partner.parent_id:
            shop_prod = prod_tmpl_obj.search([('master_product','=',self.master_product.id),('product_owner','=',partner.id)])
            if shop_prod:
                self.shop_collected = True
            else:
                self.shop_collected = False
        # 如果是商户管理员
        elif not partner.parent_id:
            shop_prod = prod_tmpl_obj.search([('master_product', '=', self.master_product.id), ('product_owner.parent_id', '=', partner.id)])
            if shop_prod:
                self.shop_collected = True
            else:
                self.shop_collected = False
        else:
            self.shop_collected = False

    def _template_in_user_shop(self):
        '''判断该产品是否为该用户店铺的产品'''
        distributor = self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id
        for template in self:
            if template.distributor.id == distributor:
                template.product_in_own_shops = True
            else:
                template.product_in_own_shops = False

    def _search_shop_product_list(self, operator, value):
        distributor = self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id
        lines = self.search([('distributor', '=', distributor)])
        return [('id', 'in', lines.ids)]

    @api.onchange('dist_price')
    def _onchange_dist_price(self):
        # 根据产品分类计算平台销售价格
        if self.categ_id and self.categ_id.commission_rate:
            rate = self.categ_id.commission_rate
        else:
            categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
            rate = categ.commission_rate if categ else 0

        list_price = self.dist_price * (1 + rate/100)
        self.list_price = list_price
        self.standard_price = self.dist_price

    @api.multi
    def create_variant_ids(self):
        ############################################################
        # 源码
        Product = self.env["product.product"]
        for tmpl_id in self.with_context(active_test=False):
            # adding an attribute with only one value should not recreate product
            # write this attribute on every product to make sure we don't lose them
            variant_alone = tmpl_id.attribute_line_ids.filtered(lambda line: len(line.value_ids) == 1).mapped(
                'value_ids')
            for value_id in variant_alone:
                updated_products = tmpl_id.product_variant_ids.filtered(
                    lambda product: value_id.attribute_id not in product.mapped('attribute_value_ids.attribute_id'))
                updated_products.write({'attribute_value_ids': [(4, value_id.id)]})

            # list of values combination
            existing_variants = [set(variant.attribute_value_ids.filtered(lambda r: r.attribute_id.create_variant).ids)
                                 for variant in tmpl_id.product_variant_ids]
            variant_matrix = itertools.product(*(line.value_ids for line in tmpl_id.attribute_line_ids if
                                                 line.value_ids and line.value_ids[0].attribute_id.create_variant))
            variant_matrix = map(
                lambda record_list: reduce(lambda x, y: x + y, record_list, self.env['product.attribute.value']),
                variant_matrix)
            to_create_variants = filter(lambda rec_set: set(rec_set.ids) not in existing_variants, variant_matrix)

            # check product
            variants_to_activate = self.env['product.product']
            variants_to_unlink = self.env['product.product']
            for product_id in tmpl_id.product_variant_ids:
                if not product_id.active and product_id.attribute_value_ids.filtered(
                        lambda r: r.attribute_id.create_variant) in variant_matrix:
                    variants_to_activate |= product_id
                elif product_id.attribute_value_ids.filtered(
                        lambda r: r.attribute_id.create_variant) not in variant_matrix:
                    variants_to_unlink |= product_id
            if variants_to_activate:
                variants_to_activate.write({'active': True})

            # create new product
            for variant_ids in to_create_variants:
                val = {
                    'product_tmpl_id': tmpl_id.id,
                    'attribute_value_ids': [(6, 0, variant_ids.ids)]
                }
                new_variant = Product.create(val)

            # unlink or inactive product
            for variant in variants_to_unlink:
            ############################################################
            # 以下为添加的内容
                collected_prods = self.env['product.product'].with_context(active_test=False).sudo().search([('master_product','=',variant.id)])
                if collected_prods:
                    raise UserError(u'%s 已被商户收录，不能删除或变更，但允许将该产品下架。' % variant.name)

            ############################################################
                try:
                    with self._cr.savepoint(), tools.mute_logger('odoo.sql_db'):
                        variant.unlink()
                # We catch all kind of exception to be sure that the operation doesn't fail.
                except (psycopg2.Error):
                # except (psycopg2.Error, except_orm):
                    variant.write({'active': False})
                    pass
        return True
        ############################################################

    # 修改产品数据时更新被收录的产品
    @api.multi
    def write(self, vals):
        user = self.env.user
        owner = user.partner_id.parent_id or user.partner_id
        # 如果不是产品所有者，也不是该产品平台产品的所有者，不允许修改
        if self._context.get('collection_mark') != 'collected':
            if (not self.user_is_product_owner) and (self.master_product.product_owner != owner) and \
                    (not self.product_owner.parent_id == user.partner_id):
                raise UserError(u'非该产品所有者，不允许进行修改')

        tools.image_resize_images(vals)
        res = super(b2b_product_template, self).write(vals)
        prod_prod_obj = self.env['product.product'].sudo()
        prod_attr_price_obj = self.env['product.attribute.price'].sudo()
        prod_attr_ln_obj = self.env['product.attribute.line']
        mod_time = fields.Datetime.now()
        # 修改产品变体或者产品从无效重新变为有效时
        if 'attribute_line_ids' in vals or vals.get('active'):
            self.create_variant_ids()
            tmpl_products = prod_prod_obj.search([('product_tmpl_id','=',self.id)])
            copied_tmpls = self.search([('master_product','=',self.id)])
            for copied_tmpl in copied_tmpls:
                cp_attr_pair = []
                for cp_prod in copied_tmpl.attribute_line_ids:
                    for cp_value in cp_prod.value_ids:
                        cp_attr_pair.append((cp_prod.attribute_id.id, cp_value.id))
                distributor = copied_tmpl.product_owner.parent_id or copied_tmpl.product_owner
                # 复制出新产品的属性
                if self.attribute_line_ids:
                    for attr_line in self.attribute_line_ids:
                        # 复制新的产品属性
                        exist = False
                        for item in cp_attr_pair:
                            if attr_line.attribute_id.id == item[0]:
                                exist = True
                                break
                        if not exist:
                            new_attr_line = prod_attr_ln_obj.create({'product_tmpl_id': copied_tmpl.id,
                                                                     'attribute_id': attr_line.attribute_id.id,
                                                                     })
                            # 复制属性值
                            for att_val in attr_line.value_ids:
                                sql = "INSERT INTO product_attribute_line_product_attribute_value_rel " \
                                      "VALUES (%s, %s); " % (new_attr_line.id, att_val.id)
                                self._cr.execute(sql)
                        # 复制原有产品属性的新属性值
                        else:
                            for attr_line_val in attr_line.value_ids:

                                if (attr_line.attribute_id.id, attr_line_val.id) not in cp_attr_pair:
                                    old_attr_line = prod_attr_ln_obj.search([('product_tmpl_id', '=', copied_tmpl.id),
                                                                             ('attribute_id', '=', attr_line.attribute_id.id)
                                                                             ],limit=1)
                                    if old_attr_line:
                                        # 复制新属性值
                                        sql = "INSERT INTO product_attribute_line_product_attribute_value_rel " \
                                              "VALUES (%s, %s); " % (old_attr_line.id, attr_line_val.id)
                                        self._cr.execute(sql)
                    copied_tmpl.create_variant_ids()
                    markup_lines = self.env['b2b.trader.markup'].search(
                        [('partner', '=', distributor.id), ('id', '=', self.trader_categ_id.id)], limit=1)
                    markup = markup_lines.rate or 0
                    shop_markup = copied_tmpl.product_owner.shop_markup or 0
                    added_prods = prod_prod_obj.search([('product_tmpl_id','=',copied_tmpl.id),('master_product', '=', False)])
                    for added_prod in added_prods:
                        attr_val = added_prod.mapped('attribute_value_ids')
                        for tmpl_product in tmpl_products:
                            m_attr_val = tmpl_product.mapped('attribute_value_ids')
                            if m_attr_val == attr_val:
                                # 关联平台主产品
                                added_prod.update({'master_product': tmpl_product.id,
                                                   'default_code': str(uuid.uuid4()).upper(),
                                                   'relation_update': 'pending',
                                                   'relation_mod_time': mod_time,
                                                   'active': tmpl_product.active})
                                # 复制变体的附加价格
                                rate = 0
                                if self.categ_id and self.categ_id.commission_rate:
                                    rate = self.categ_id.commission_rate
                                else:
                                    categ = self.env['product.category'].sudo().search([('parent_id', '=', False)],
                                                                                       limit=1)
                                    if categ:
                                        rate = categ.commission_rate
                                for value in m_attr_val:
                                    vlu = value[0].id
                                    amt = 0
                                    attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', self.id),
                                                                             ('value_id', '=', vlu)])
                                    if attr_price:
                                        for rec in attr_price:
                                            amt += rec.price_extra
                                        list_price = amt * (1 + rate / 100.0) * (1 + markup / 100.0) * (1 + shop_markup / 100.0)
                                        if not prod_attr_price_obj.search([('product_tmpl_id', '=', copied_tmpl.id),
                                                                           ('value_id', '=', vlu),
                                                                           ('price_extra', '=', list_price)
                                                                           ]):
                                            prod_attr_price_obj.create({'product_tmpl_id': copied_tmpl.id,
                                                                        'value_id': vlu,
                                                                        'price_extra': list_price})
                                    # 将供应商产品的平台价写入经销商的成本价
                                    added_prod.update({'standard_price': tmpl_product.lst_price})
        if 'active' in vals and not vals.get('active'):
            self.with_context(active_test=False).mapped('product_variant_ids').write({'active': vals.get('active')})

        prod_flag = False
        image_flag = False
        price_flag = False
        rel_flag = False

        # 修改产品信息时
        if vals.get('active') == False or vals.get('active') == True:
        # if vals.get('categ_id',False) or vals.get('uom_id',False) or vals.get('product_description',False) or vals.get('images',False) or vals.get('freight_line',False) or vals.get('active',False):
            prod_flag = True
        # 修改产品图片时
        if vals.get('images'):
            image_flag = True
        # 修改产品属性时
        if vals.get('attibute_line_ids'):
            rel_flag = True
        # 修改价格时
        if vals.get('list_price'):
            price_flag = True
            # 更新经销商和店铺收录的该产品的成本价格
            list_price = vals.get('list_price')
            prod_templates = self.env['product.template'].search([('master_product', '=', self.id)])
            if prod_templates:
                for prod in prod_templates:

                    rate = 0
                    if prod.categ_id and prod.categ_id.commission_rate:
                        rate = prod.categ_id.commission_rate
                    else:
                        categ = self.env['product.category'].sudo().search([('parent_id', '=', False)],
                                                                           limit=1)
                        if categ:
                            rate = categ.commission_rate
                    markup_lines = self.env['b2b.trader.markup'].search(
                        [('partner', '=', prod.product_owner.parent_id.id or prod.product_owner.id), ('id', '=', prod.trader_categ_id.id)], limit=1)
                    markup = markup_lines.rate or 0
                    shop_markup = prod.product_owner.shop_markup or 0
                    col_list_price = list_price * (1 + rate / 100.0) * (1 + prod.product_owner.shop_markup / 100.0)

                    prod.with_context({'collection_mark': 'collected'}).write({'standard_price':list_price, 'dist_price':list_price, 'list_price':col_list_price, 'modify_state':'new'})
                    products = prod_prod_obj.search([('product_tmpl_id', '=', prod.id)])
                    for product in products:
                        product.with_context({'collection_mark': 'collected'}).write({'price_update': 'pending', 'price_mod_time': mod_time})
                    # 更新供应商采购价格
                    if self.product_owner in prod.seller_ids.mapped('name'):
                        prod.seller_ids.with_context({'collection_mark': 'collected'}).write({'price': vals.get('dist_price')})
            # 更新供应商采购价格
            if self.product_owner in self.seller_ids.mapped('name'):
                self.seller_ids.write({'price':vals.get('dist_price')})

        if vals.get('dist_price'):
            dist_price = vals.get('dist_price')
            to_uom = None
            if 'uom' in self._context:
                to_uom = self.env['product.uom'].browse([self._context['uom']])
            # 如果是供应商产品
            if not self.master_product:
                # 获取平台分类的加价率
                if self.categ_id and self.categ_id.commission_rate:
                    rate = self.categ_id.commission_rate
                else:
                    categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                    rate = categ.commission_rate if categ else 0
                for var in self.product_variant_ids:
                    if to_uom:
                        d_price = var.uom_id._compute_price(dist_price, to_uom)
                    else:
                        d_price = dist_price
                    std_price = d_price + var.variant_adj_price
                    var.with_context({'collection_mark': 'collected'}).write({'b2b_price': dist_price,'standard_price': std_price})
            # 如果是经销商产品
            else:
                # 获取平台分类的加价率
                if self.categ_id and self.categ_id.commission_rate:
                    rate = self.categ_id.commission_rate
                else:
                    categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                    rate = categ.commission_rate if categ else 0
                for var in self.product_variant_ids:
                    if to_uom:
                        dist_price = var.uom_id._compute_price(var.master_product.b2b_price, to_uom)
                    else:
                        dist_price = var.master_product.b2b_price
                    cost_price = (dist_price + var.master_product.variant_adj_price) * (1 + rate/100)
                    var.with_context({'collection_mark': 'collected'}).write({'b2b_price': cost_price})

        if prod_flag or image_flag or price_flag or rel_flag:
            # 如果是供应商产品
            if not self.master_product:
                prod_templates = self.search([('master_product', '=', self.id)])
            # 如果是经销商收录的产品
            elif not self.product_owner.parent_id:
                prod_templates = self.search([('master_product', '=', self.master_product.id),('product_owner.parent_id', '=', self.product_owner.id)])
            # 如果是店铺中收录的产品
            elif self.product_owner.type == 'shop':
                prod_templates = self
            if prod_templates:
                for prod_tmpl in prod_templates:
                    if prod_flag:
                        prod_tmpl.write({'prod_mod_state': 'new'})
                        products = prod_prod_obj.search([('product_tmpl_id','=',prod_tmpl.id)])
                        for product in products:
                            if vals.get('active') == False:
                                product.with_context({'collection_mark': 'collected'}).write({'product_status':'to_delete', 'product_mod_time': mod_time})
                            elif vals.get('active') == True:
                                product.with_context({'collection_mark': 'collected'}).write({'product_status':'pending', 'product_mod_time':mod_time})
                    if image_flag:
                        prod_tmpl.write({'image_mod_state': 'new'})
                        products = prod_prod_obj.search([('product_tmpl_id', '=', prod_tmpl.id)])
                        for product in products:
                            product.with_context({'collection_mark': 'collected'}).write({'image_update': 'pending', 'image_mod_time': mod_time})
                        if not self.master_product:  # 只需对供应商产品进行处理，将收录的产品更新图片
                            # 供应商添加图片时会自动插入到收录的产品中，此处只需将供应商删除的图片从收录的产品中删除
                            image_list = []
                            for my_image in self.images:
                                image_list.append(my_image.image_id.id)
                            collected_tmpls = self.search([('master_product','=',self.id)])
                            for coll_tmpl in collected_tmpls:
                                for image in coll_tmpl.images:
                                    if image.image_id.id not in image_list:
                                        image.unlink()
                    if rel_flag:
                        prod_tmpl.write({'variant_mod_state': 'new'})
                        products = prod_prod_obj.search([('product_tmpl_id', '=', prod_tmpl.id)])
                        for product in products:
                            product.with_context({'collection_mark': 'collected'}).write({'relation_update': 'pending', 'relation_mod_time': mod_time})
                        if not self.master_product:            # 只需对供应商产品进行更新
                            prod_attr_ln_obj = self.env['product.attribute.line']
                            prod_attr_price_obj = self.env['product.attribute.price'].sudo()
                            if self.attribute_line_ids:
                                for a__line in self.attribute_line_ids:
                                    collected_prods = self.env['product.template'].sudo().search([('master_product','=',self.id)])
                                    if collected_prods:
                                        for coll_prod in collected_prods:
                                            # 复制出产品的新属性
                                            if a__line.attribute_id not in coll_prod.attribute_line_ids:
                                                # 复制产品属性
                                                new_attr_line = prod_attr_ln_obj.create({'product_tmpl_id': coll_prod.id,
                                                                                     'attribute_id': a__line.attribute_id.id,
                                                                                     })
                                                # 复制属性值
                                                sql = "INSERT INTO product_attribute_line_product_attribute_value_rel " \
                                                      "SELECT %s, product_attribute_value_id " \
                                                      "FROM product_attribute_line_product_attribute_value_rel " \
                                                      "WHERE product_attribute_line_id = %s;" % (new_attr_line.id, a__line.id)
                                                self._cr.execute(sql)
                                                # 根据属性生成变体产品
                                                coll_prod.create_variant_ids()
                                                # 将产品中产品变体的价格附加价格复制到经销商收录的产品中
                                                for product in coll_prod.product_variant_ids:
                                                    if not product.master_product:
                                                        attr_val = product.mapped('attribute_value_ids')
                                                        m_products = self.env['product.product'].sudo().search([('product_tmpl_id', '=', self.id)])
                                                        for m_product in m_products:
                                                            m_attr_val = m_product.mapped('attribute_value_ids')
                                                            if m_attr_val == attr_val:
                                                                # 关联平台主产品
                                                                product.update({'master_product': m_product.id, 'active': m_product.active})
                                                                # 复制变体的附加价格
                                                                rate = 0
                                                                if self.categ_id and self.categ_id.commission_rate:
                                                                    rate = self.categ_id.commission_rate
                                                                else:
                                                                    categ = self.env['product.category'].sudo().search([('parent_id', '=', False)],
                                                                                                                       limit=1)
                                                                    if categ:
                                                                        rate = categ.commission_rate

                                                                for value in m_attr_val:
                                                                    vlu = value[0].id
                                                                    amt = 0
                                                                    attr_price = prod_attr_price_obj.search(
                                                                        [('product_tmpl_id', '=', self.id),
                                                                         ('value_id', '=', vlu)])
                                                                    if attr_price:
                                                                        for rec in attr_price:
                                                                            amt += rec.price_extra
                                                                        if not product.product_owner.parent_id:  # 对于经销商收录的产品
                                                                            list_price = amt * (1 + rate / 100.0)
                                                                        else:                                   # 对于店铺中的产品
                                                                            list_price = amt * (1 + rate / 100.0) * (1 + product.product_owner.shop_markup / 100.0)
                                                                        if not prod_attr_price_obj.search([('product_tmpl_id', '=', coll_prod.id),
                                                                                                           ('value_id', '=', vlu)]):
                                                                            prod_attr_price_obj.create({'product_tmpl_id': coll_prod.id,
                                                                                                        'value_id': vlu,
                                                                                                        'price_extra': list_price})
                                                                        # 将供应商产品的平台价写入经销商的成本价
                                                                        product.update({'standard_price': m_product.lst_price})

            # prod_prods = self.env['product.product'].search([('product_tmpl_id.master_product', '=', self.id),
            #                                                  ('product_tmpl_id.product_owner.type', '=', 'shop')])
            # if prod_flag:
            #     prod_prods.write({'product_status':'pending'})
            # if image_flage:
            #     prod_prods.write({'image_update':'pending'})
            # if price_flage:
            #     prod_prods.write({'price_update':'pending'})
            # if rel_flag:
            #     prod_prods.write({'relation_update':'pending'})
        return res

    # 修改价格信息
    @api.one
    def button_modify_confirm(self):
        for prod in self.product_variant_ids:
            prod.write({'price_update':'pending', 'price_mod_time':fields.Datetime.now()})
        self.modify_state = 'confirmed'

    # 修改产品信息
    @api.one
    def button_prod_status_confirm(self):
        for prod in self.product_variant_ids:
            prod.write({'product_status': 'pending', 'product_mod_time': fields.Datetime.now()})
        self.prod_mod_state = 'confirmed'

    # 修改图片信息
    @api.one
    def button_image_status_confirm(self):
        for prod in self.product_variant_ids:
            prod.write({'image_update': 'pending', 'image_mod_time': fields.Datetime.now()})
        self.image_mod_state = 'confirmed'

    # 修改库存信息
    @api.one
    def button_stock_status_confirm(self):
        for prod in self.product_variant_ids:
            prod.write({'stock_update': 'pending', 'stock_mod_time': fields.Datetime.now()})
        self.stock_mod_state = 'confirmed'

    # 修改变体关系信息
    @api.one
    def button_variant_status_confirm(self):
        for prod in self.product_variant_ids:
            prod.write({'relation_update': 'pending', 'relation_mod_time': fields.Datetime.now()})
        self.variant_mod_state = 'confirmed'

    # 产品所有者将产品发布到平台
    @api.multi
    def button_publish(self):
        if not self.product_owner:
            raise osv.except_osv("不能判断您所属哪个供应商，请联系平台运营人员核对您的账号数据")

        partner = self.product_owner

        # 允许手工指定系统编号，如果不指定，则系统生成
        if not self.system_id:
            system_id = str(partner.id).zfill(3) + '-' + self.env['ir.sequence'].next_by_code('b2b.system.id.seq')
            self.write({'system_id': system_id})

        if partner not in self.seller_ids.mapped('name'):
            currency = partner.property_purchase_currency_id or self.env.user.company_id.currency_id
            supplierinfo = {
                'name': partner.id,
                'sequence': max(self.seller_ids.mapped('sequence')) + 1 if self.seller_ids else 1,
                'product_uom': self.uom_id.id,
                'min_qty': 1.0,
                'price': self.dist_price,
                # 'price': self.currency_id.compute(self.list_price, currency),
                'currency_id': currency.id,
                'delay': 0,
            }
            vals = {
                'seller_ids': [(0, 0, supplierinfo)],
            }
            self.write(vals)
        self.write({'purchase_method':'purchase',
                    'master_product':False,
                    'invoice_policy':'order',
                    'platform_published':True,
                    })
        # 如果供应商同时也是经销商，则将该产品同时收录到自己经销商的目录中
        if self.user_has_groups('b2b_platform.group_qdoo_distributor_user'):
            self.platform_add_price()
            self.button_collect_product()

    @api.multi
    def platform_add_price(self):
        '''发布产品，平台加价'''
        for template in self:
            platform_rate = (template.categ_id and template.categ_id.commission_rate or 0) / 100
            template.platform_price = template.cost_price * (1 + platform_rate)
            for product in template.product_variant_ids:
                product.platform_price = product.cost_price * (1 + platform_rate)


    # 产品所有者从平台下架
    @api.one
    def button_cancel_publish(self):
        self.platform_published = False

    # # 平台上被收录的产品不允许删除
    # @api.multi
    # def unlink(self):
    #    for ids in self:
    #        products = self.env['product.template'].sudo().search([('master_product','=',ids.id)])
    #        if products:
    #            raise osv.except_osv("该产品已被平台经销商收录，不能删除，但允许从平台下架。")
    #        dist_products = self.env['product.template'].sudo().search([('master_product', '=', ids.master_product.id),
    #                                                                    ('product_owner.parent_id','=', ids.product_owner.id)])
    #        if dist_products:
    #            raise osv.except_osv("该产品已被店铺收录，不能删除。")
    #    return super(b2b_product_template, self).unlink()

    # 平台上被收录的产品不允许删除
    @api.multi
    def unlink(self):
        template_obj = self.env['product.template']
        for template in self:
            templates = template_obj.sudo().search([('master_product', '=', template.id)])
            if templates:
                raise osv.except_osv("该产品已被平台经销商收录，不能删除，但允许从平台下架。")
            shop_templates = template_obj.sudo().search([
                ('master_product', '=', template.master_product.id),
                ('product_owner.parent_id', '=', template.product_owner.id)])
            if shop_templates:
                raise osv.except_osv("该产品已被店铺收录，不能删除。")
        return super(b2b_product_template, self).unlink()

    # 产品所有者从平台下架
    @api.one
    def button_cancel_publish(self):
            self.platform_published = False

    # 供应商批量发布自己的产品
    @api.multi
    def btn_publish_multi_collect(self, cr, uid, active_ids):
        prod_check = self.env['product.template'].browse(active_ids[0])
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not (prod_check.product_owner == partner and not prod_check.platform_published):
            raise UserError(u'只能发布自己的产品')
        for product_id in active_ids:
            product = self.browse(product_id)
            if not product.platform_published and product.product_owner == partner :
                product.button_publish()

    # 经销商从平台产品查询后批量收录
    @api.multi
    def btn_dist_multi_collect(self,cr,uid,active_ids):
        prod_check = self.env['product.template'].browse(active_ids[0])
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not (not prod_check.master_product and prod_check.platform_published):
            raise UserError(u'只能从平台的产品目录中收录')
        for product_id in active_ids:
            product = self.browse(product_id)
            if not product.collected_mark and product.product_owner != partner and product.distributor != partner:
                product.button_collect_product()

    # 业务员从经销商产品查询后批量收录到店铺
    @api.multi
    def btn_shop_multi_collect(self, cr, uid, active_ids):
        prod_check = self.env['product.template'].browse(active_ids[0])
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        print prod_check,distributor
        if not prod_check.product_owner == distributor:
            raise UserError(u'只能从经销商收录的产品中发布到店铺中')
        list = []
        for rec in active_ids:
            list.append(rec)

        # self.create_or_update_amazon_product(active_ids)

        return {
            'name': '店铺产品转化',
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'b2b.shop.collect.convert',
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'context': {'product_ids':list}
        }

    @api.multi
    def create_or_update_amazon_product(self, template_ids):
        '''创建亚马逊产品 v1.0'''
        amazon_product_obj = self.env['amazon.product.ept']
        templates = self.env['product.template'].browse(template_ids)
        for template in templates:
            # print 'template:',template
            instance = template.product_owner.parent_id.amazon_instance_id
            # print 'instance_id:', instance.id
            products = template.product_variant_ids
            # print 'products:', products
            if len(products) == 1:  # no variation
                product = products[0]
                amazon_product = amazon_product_obj.search([('product_id', '=', product.id)])
                if len(amazon_product) == 1:
                    val = {
                        'instance_id': instance.id,
                        'seller_sku': product.default_code,
                        'product_upc': product.barcode,
                        'amazon_browse_node_id': False,
                        'condition': instance.condition or 'New',
                        'tax_code_id': instance.default_amazon_tax_code_id and instance.default_amazon_tax_code_id.id or False,
                        'long_description': template.description or False,
                        'variation_data': False,
                        'standard_product_id_type': 'UPC',
                    }
                    amazon_product.write(val)
                elif len(amazon_product) > 1:
                    raise UserError(u'内部编码为%s的产品，存在多个亚马逊产品' % product.default_code)
                else:
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
                    amazon_product_obj.create(val)
            elif len(products) > 1:
                for product in products:
                    amazon_product = amazon_product_obj.search([('product_id', '=', product.id)])
                    if len(amazon_product) == 1:
                        val = {
                            'instance_id': instance.id,
                            'seller_sku': product.default_code,
                            'product_upc': product.barcode,
                            'amazon_browse_node_id': False,
                            'condition': instance.condition or 'New',
                            'tax_code_id': instance.default_amazon_tax_code_id and instance.default_amazon_tax_code_id.id or False,
                            'long_description': template.description or False,
                            'variation_data': False,
                            'standard_product_id_type': 'UPC',
                        }
                        amazon_product.write(val)
                    elif len(amazon_product) > 1:
                        raise UserError(u'内部编码为%s的产品，存在多个亚马逊产品' % product.default_code)
                    else:
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
                        amazon_product_obj.create(val)

    # 经销商产品查询后批量设置产品分类
    @api.multi
    def btn_dist_multi_assign_categ(self, cr, uid, active_ids):
        prod_check = self.env['product.template'].browse(active_ids[0])
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not prod_check.product_owner == distributor:
            raise UserError(u'只能从经销商收录的产品中指定内部分类')
        list = []
        for rec in active_ids:
            list.append(rec)
        return {
            'name': '指定产品内部分类',
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'b2b.dist.assign.categ',
            'type': 'ir.actions.act_window',
            'views': [(False, 'form')],
            'context': {'product_ids': list}
        }

    @api.one
    def btn_upload_tmpl_to_amazon(self):
        # 调用亚马逊接口，上传产品数据，将代码添加于此
        # TODO
        # 亚马逊接口上传成功后替换掉以下代码
        # if upload 成功
        finish_time = fields.Datetime.now()
        self.update({'product_status': 'done',
                     'image_update': 'done',
                     'price_update': 'done',
                     'stock_update': 'done',
                     'relation_update': 'done',
                     'product_up_time': finish_time,
                     'image_up_time': finish_time,
                     'price_up_time': finish_time,
                     'stock_up_time': finish_time,
                     'relation_up_time': finish_time,
                     })

    # 经销商从平台产品查询后批量上传亚马逊
    @api.multi
    def btn_shop_multi_tmpl_upload(self, cr, uid, active_ids):
        prod_check = self.env['product.template'].browse(active_ids[0])
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not (prod_check.product_status in ('pending', 'to_delete', 'fail')
                or prod_check.image_update in ('pending', 'to_delete', 'fail')
                or prod_check.price_update in ('pending', 'to_delete', 'fail')
                or prod_check.stock_update in ('pending', 'to_delete', 'fail')
                or prod_check.relation_update in ('pending', 'to_delete', 'fail')):
            raise UserError(u'只能从产品变更的目录中选择进行上传')
        for product_id in active_ids:
            product = self.browse(product_id)
            if (product.product_status in ('pending', 'to_delete', 'fail')
                or product.image_update in ('pending', 'to_delete', 'fail')
                or product.price_update in ('pending', 'to_delete', 'fail')
                or product.stock_update in ('pending', 'to_delete', 'fail')
                or product.relation_update in ('pending', 'to_delete', 'fail')):
                self.export_product_to_amazon(product)
                product.with_context({'collection_mark': 'collected'}).btn_upload_tmpl_to_amazon()
        # raise UserError(u'...cs...')

    @api.multi
    def export_product_to_amazon(self, template):
        print 'export_product_to_amazon',template
        amazon_product_obj = self.env['amazon.product.ept']
        products = template.product_variant_ids
        print 'products',products
        amazon_products = amazon_product_obj.search([('product_id', 'in', products.ids)])
        print 'amazon_products',amazon_products
        instance = template.product_owner.amazon_instance_id
        print 'instance:',instance
        amazon_products.export_product_amazon(instance, amazon_products)


