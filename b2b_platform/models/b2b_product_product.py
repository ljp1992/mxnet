# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
import odoo.addons.decimal_precision as dp
from odoo.osv import osv
from odoo.exceptions import UserError, AccessError
import uuid
import itertools
import psycopg2
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    master_product = fields.Many2one('product.product', u'平台主产品', index=True)
    owner = fields.Many2one('res.partner', u'店铺', related='product_tmpl_id.product_owner', readonly=True)

    modify_state = fields.Selection(u'价格变更', related='product_tmpl_id.modify_state')
    prod_mod_state = fields.Selection(u'产品变更', related='product_tmpl_id.prod_mod_state')
    image_mod_state = fields.Selection(u'图片变更', related='product_tmpl_id.image_mod_state')
    stock_mod_state = fields.Selection(u'库存变更', related='product_tmpl_id.stock_mod_state')
    variant_mod_state = fields.Selection(u'关系变更', related='product_tmpl_id.variant_mod_state')
    shop_mod_list = fields.Boolean(u'店铺更新', compute='_set_shop_mod_list', search='_get_shop_mod_list')

    overall_avail_qty = fields.Float(u'总库存', related='master_product.qty_available')
    own_stock = fields.Float('平台可用库存', compute='_get_b2b_own_stock',
                                            digits=dp.get_precision('Product Unit of Measure'))
    supplier_stock = fields.Float('供应商可用库存', compute='_get_b2b_stock',
                             digits=dp.get_precision('Product Unit of Measure'))
    thirdpl_stock = fields.Float('3PL可用库存', compute='_get_b2b_stock',
                             digits=dp.get_precision('Product Unit of Measure'))
    adjust_qty = fields.Integer(u'实际盘点数量')
    my_products = fields.Boolean(u'我的产品', compute="_get_my_products", search='_get_my_products')
    # mws_product_type_id = fields.Many2one(related='product_tmpl_id.mws_product_type_id')
    b2b_price = fields.Monetary(u'产品模板平台成本价')
    variant_adj_price = fields.Monetary(u'变体价格调整')
    shop_adj_price = fields.Float(u'店铺价格调整', digits=(16,2))
    shop_retail_price = fields.Float(u'店铺售价', digits=(16,2))
    system_avail_qty = fields.Float(u'变体库存', compute='_get_system_qty')
    stock_level = fields.Char(u'有无库存', compute='_get_system_qty')

    shop_currency = fields.Many2one('res.currency', compute='get_shop_currency', store=False, string=u'币种')
    shop_currency2 = fields.Many2one('res.currency', compute='get_shop_currency', store=False, string=u'币种')

    ################################ ljp added ################################################################

    seller_product_id = fields.Many2one('product.product', string=u'经销商产品')

    cost_price = fields.Monetary(compute='_get_cost_price', store=True, string=u'成本价')
    platform_price = fields.Monetary(string=u'平台价格')
    seller_price = fields.Monetary(string=u'经销商价格')
    shop_price_cny = fields.Monetary(string=u'店铺价格')
    shop_price = fields.Float(compute='_get_shop_price', store=False, string=u'店铺售价', digits=(16, 2))

    @api.multi
    def _get_shop_price(self):
        for product in self:
            rate = product.shop_currency.rate or 1
            product.shop_price = product.shop_price_cny * rate

    @api.depends('product_tmpl_id.cost_price')
    def _get_cost_price(self):
        for product in self:
            product.cost_price = product.product_tmpl_id.cost_price

    @api.multi
    def get_shop_currency(self):
        for product in self:
            currency = product.product_owner and product.product_owner.shop_currency
            if currency:
                product.shop_currency = product.shop_currency2 = currency.id

    @api.one
    def _get_system_qty(self):
        system_avail_qty = 0
        if self.master_product:
            system_avail_qty = self.master_product.qty_available
        else:
            system_avail_qty = self.qty_available
        self.system_avail_qty = system_avail_qty
        if system_avail_qty:
            self.stock_level = u'有'
        else:
            self.stock_level = u'无'


    @api.multi
    def name_get(self):
        # TDE: this could be cleaned a bit I think

        def _name_get(d):
            name = d.get('name', '')
            name = name[0:50] + '...' if len(name) > 50 else name
            # code = self._context.get('display_default_code', True) and d.get('default_code', False) or False
            # if code:
            #     name = '[%s] %s' % (code, name)
            return (d['id'], name)

        partner_id = self._context.get('partner_id')
        if partner_id:
            partner_ids = [partner_id, self.env['res.partner'].browse(partner_id).commercial_partner_id.id]
        else:
            partner_ids = []

        # all user don't have access to seller and partner
        # check access and use superuser
        self.check_access_rights("read")
        self.check_access_rule("read")

        result = []
        for product in self.sudo():
            # display only the attributes with multiple possible values on the template
            variable_attributes = product.attribute_line_ids.filtered(lambda l: len(l.value_ids) > 1).mapped(
                'attribute_id')
            variant = product.attribute_value_ids._variant_name(variable_attributes)

            name = variant and "%s (%s)" % (product.name, variant) or product.name
            sellers = []
            if partner_ids:
                sellers = [x for x in product.seller_ids if (x.name.id in partner_ids) and (x.product_id == product)]
                if not sellers:
                    sellers = [x for x in product.seller_ids if (x.name.id in partner_ids) and not x.product_id]
            if sellers:
                for s in sellers:
                    seller_variant = s.product_name and (
                        variant and "%s (%s)" % (s.product_name, variant) or s.product_name
                    ) or False
                    mydict = {
                        'id': product.id,
                        'name': seller_variant or name,
                        'default_code': s.product_code or product.default_code,
                    }
                    temp = _name_get(mydict)
                    if temp not in result:
                        result.append(temp)
            else:
                mydict = {
                    'id': product.id,
                    'name': name,
                    'default_code': product.default_code,
                }
                result.append(_name_get(mydict))
        return result

    @api.depends('list_price', 'price_extra','b2b_price','variant_adj_price','shop_adj_price')
    def _compute_product_lst_price(self):
        prod_temp = self[0].product_tmpl_id
        if prod_temp.categ_id and prod_temp.categ_id.commission_rate:
            rate = prod_temp.categ_id.commission_rate
        else:
            categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
            rate = categ.commission_rate if categ else 0

        to_uom = None
        if 'uom' in self._context:
            to_uom = self.env['product.uom'].browse([self._context['uom']])

        for product in self:
            # 供应商产品
            if not product.master_product:
                if to_uom:
                    dist_price = product.uom_id._compute_price(product.dist_price, to_uom)
                else:
                    dist_price = product.dist_price
                product.lst_price = (dist_price + product.price_extra + product.variant_adj_price) * (1 + rate / 100)
            # 经销商产品
            else:
                # 获取经销商分类的加价率
                if product.product_tmpl_id.trader_categ_id:
                    dist_markup = product.product_tmpl_id.trader_categ_id.rate
                else:
                    dist_markup = 0
                # 获取店铺的加价率
                if product.product_tmpl_id.product_owner and product.product_tmpl_id.product_owner.type == 'shop':
                    markup = product.product_tmpl_id.product_owner.shop_markup
                    if product.product_tmpl_id.product_owner.shop_currency:
                        currency_id = product.product_tmpl_id.product_owner.shop_currency
                    else:
                        currency_id = self.env.user.company_id.currency_id
                else:
                    markup = 0
                    currency_id = self.env.user.company_id.currency_id
                product.shop_currency = currency_id
                product.lst_price = product.standard_price * (1 + dist_markup / 100) * (1 + markup / 100) + product.variant_adj_price

    @api.onchange('variant_adj_price','shop_adj_price')
    def _onchange_price_adjustment(self):
        # 获取平台分类的加价率
        if self._origin.product_tmpl_id.categ_id and self._origin.product_tmpl_id.categ_id.commission_rate:
            rate = self._origin.product_tmpl_id.categ_id.commission_rate
        else:
            categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
            rate = categ.commission_rate if categ else 0
        # 获取经销商分类的加价率
        if self._origin.product_tmpl_id.trader_categ_id:
            dist_markup = self._origin.product_tmpl_id.trader_categ_id.rate
        else:
            dist_markup = 0
        # 获取店铺的加价率
        if self._origin.product_tmpl_id.product_owner and self._origin.product_tmpl_id.product_owner.type == 'shop':
            markup = self._origin.product_tmpl_id.product_owner.shop_markup
            if self._origin.product_tmpl_id.product_owner.shop_currency:
                currency_id = self._origin.product_tmpl_id.product_owner.shop_currency
            else:
                currency_id = self.env.user.company_id.currency_id
        else:
            markup = 0
            currency_id = self.env.user.company_id.currency_id
        self.shop_currency = currency_id
        # 是否需计量单位转换
        to_uom = None
        if 'uom' in self._context:
            to_uom = self.env['product.uom'].browse([self._context['uom']])
        # 更新价格
        # 如果是供应商产品
        if not self._origin.product_tmpl_id.master_product:
            if to_uom:
                dist_price = self._origin.uom_id._compute_price(self._origin.product_tmpl_id.dist_price, to_uom)
            else:
                dist_price = self._origin.product_tmpl_id.dist_price
            cost_price = dist_price + self.variant_adj_price
            self.standard_price = cost_price
            self.lst_price = cost_price * (1 + rate/100)
        # 如果是经销商产品
        else:
            shop_cny_price = self.standard_price * (1 + dist_markup/100) * (1 + markup/100) + self.variant_adj_price
            shop_foreign_price = self.env.user.company_id.currency_id.compute(shop_cny_price, currency_id) + self.shop_adj_price
            self.lst_price = shop_cny_price
            self.shop_retail_price = shop_foreign_price

    def _get_my_products(self, operator, value):
        if self.user_has_groups('b2b_platform.group_qdoo_supplier_warehouse,b2b_platform.group_qdoo_supplier_manager'):
            products = self.search([('owner', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id),('master_product','=',False)])
        elif self.user_has_groups('b2b_platform.group_b2b_3pl_operator'):
            products = self.search([('master_product', '=', False),('product_tmpl_id.type','!=','service')])
        else:
            products = False
        return [('id', 'in', products.ids)]

    def _set_shop_mod_list(self):
        oper = self.env.user.partner_id
        for product in self:
            if product.product_owner.shop_operator == oper and (product.product_status == 'pending' or product.image_update == 'pending' or product.price_update == 'pending' or product.stock_update == 'pending' or product.relation_update == 'pending'):
                product.shop_mod_list = True

    def _get_shop_mod_list(self, operator, value):
        list = []
        oper = self.env.user.partner_id
        products = self.env['product.product'].search([('product_owner.shop_operator', '=', oper.id)])
        for product in products:
            if product.product_status in ('pending','to_delete','fail') \
                    or product.image_update in ('pending','to_delete','fail') \
                    or product.price_update in ('pending','to_delete','fail') \
                    or product.stock_update in ('pending','to_delete','fail') \
                    or product.relation_update in ('pending','to_delete','fail'):
                list.append(product.id)
        return [('id', 'in', list)]

    @api.depends('stock_quant_ids', 'stock_move_ids')
    def _get_b2b_stock(self):
        supp_stock_id = self.env.ref('b2b_platform.stock_location_wh_suppliers')
        thirdpl_stock_id = self.env.ref('b2b_platform.stock_location_wh_3pl')
        for product in self:
            supp_qty = 0
            tpl_qty = 0
            supp_stocks = self.env['stock.quant'].sudo().search(
                [('product_id', '=', product.id),('location_id.location_id', '=', supp_stock_id.id)])
            for rec in supp_stocks:
                supp_qty += rec.qty
            tpl_stocks = self.env['stock.quant'].sudo().search(
                [('product_id', '=', product.id), ('location_id.location_id.location_id', '=', thirdpl_stock_id.id)])
            for res in tpl_stocks:
                tpl_qty += res.qty
            product.supplier_stock = supp_qty
            product.thirdpl_stock = tpl_qty

    @api.depends('stock_quant_ids', 'stock_move_ids')
    def _get_b2b_own_stock(self):
        own_stock_id = self.env.ref('b2b_platform.stock_location_wh_own')
        for product in self:
            qty = 0
            stocks = self.env['stock.quant'].sudo().search([('location_id','=',own_stock_id.id),('product_id','=',product.id)])
            for rec in stocks:
                qty += rec.qty
            product.own_stock = qty
        # # 合并计算供应商、平台及第三方仓库的产品可用库存数量
        # res_own = self._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'),
        #                                     self._context.get('package_id'), self._context.get('from_date'),
        #                                     self._context.get('to_date'))
        # res_supp = self._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'),
        #                                         self._context.get('package_id'), self._context.get('from_date'),
        #                                         self._context.get('to_date'))
        # res_3pl = self._compute_quantities_dict(self._context.get('lot_id'), self._context.get('owner_id'),
        #                                         self._context.get('package_id'), self._context.get('from_date'),
        #                                         self._context.get('to_date'))
        # for product in self:
        #     product.own_stock = res_own[product.id]['qty_available']
            # product.supplier_stock = res_supp[product.id]['qty_available']
            # product.thirdpl_stock = res_3pl[product.id]['qty_available']


    # TODO 需修改
    def _search_b2b_qty_available(self, operator, value):
        # TDE FIXME: should probably clean the search methods
        if value == 0.0 and operator in ('=', '>=', '<='):
            return self._search_product_quantity(operator, value, 'qty_available')
        product_ids = self._search_qty_available_new(operator, value, self._context.get('lot_id'), self._context.get('owner_id'), self._context.get('package_id'))
        if (value > 0 and operator in ('<=', '<')) or (value < 0 and operator in ('>=', '>')):
            # include also unavailable products
            domain = self._search_product_quantity(operator, value, 'qty_available')
            product_ids += domain[0][2]
        return [('id', 'in', product_ids)]

    @api.multi
    def unlink(self):
        # for ids in self:
        #     if ids.product_tmpl_id.master_product and not ids.master_product:  # 新复制出来的临时产品不在查验范围之内
        #         break
        #     products = self.sudo().search([('master_product','=',ids.id)])
        #     if products:
        #         raise osv.except_osv("该产品已被经销商收录，不能删除，但允许从平台下架。")
        #     dist_products = self.sudo().search([('master_product', '=', ids.master_product.id),
        #                         ('product_tmpl_id.product_owner.parent_id','=', ids.product_tmpl_id.product_owner.id)])
        #     if dist_products:
        #         raise osv.except_osv("该产品已被店铺收录，不能删除。")
        #######################################################
        # 以下为源码
        unlink_products = self.env['product.product']
        unlink_templates = self.env['product.template']
        for product in self:
            # Check if product still exists, in case it has been unlinked by unlinking its template
            if not product.exists():
                continue
            # Check if the product is last product of this template
            other_products = self.search(
                [('product_tmpl_id', '=', product.product_tmpl_id.id), ('id', '!=', product.id)])
            if not other_products:
                unlink_templates |= product.product_tmpl_id
            unlink_products |= product
        res = super(ProductProduct, unlink_products).unlink()
        # delete templates after calling super, as deleting template could lead to deleting
        # products due to ondelete='cascade'
        unlink_templates.unlink()
        return res
        #######################################################

    @api.multi
    def write(self, values):
        ##### 以下为新加功能
        mod_time = fields.Datetime.now()
        image_processing = False
        for product in self:
            if not product.master_product:        # 如果是供应商的产品
                ###---产品更改有效状态时的处理
                if values.get('active') == False or values.get('active') == True:
                    if product.product_tmpl_id.product_variant_ids:
                        for prod in product.product_tmpl_id.product_variant_ids:
                            collected_prods = self.with_context(active_test=False).search([('master_product', '=', product.id)])
                            if collected_prods:
                                status = 'to_delete' if values.get('active') == False else 'pending'
                                collected_prods.write({'active': values.get('active'), 'shop_active': values.get('active'),
                                                       'product_status': status, 'product_mod_time': fields.Datetime.now()})
                ###---产品更改图片时的处理
                if values.get('images') != None:
                    image_processing = True
                ###---产品更改变体价格时的处理
                if values.get('variant_adj_price') != None:
                    product.standard_price = product.b2b_price + values.get('variant_adj_price')
                # if values.get('shop_adj_price') != None:
                #     shop_adj = values.get('shop_adj_price') - product.shop_adj_price
                #     values['shop_adj_price'] = product.lst_price + shop_adj
                # if values.get('standard_price') != None:
                #     std_price = values.get('standard_price')
                #     # 获取平台分类的加价率
                #     if self.product_tmpl_id.categ_id and self.product_tmpl_id.categ_id.commission_rate:
                #         rate = self.product_tmpl_id.categ_id.commission_rate
                #     else:
                #         categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                #         rate = categ.commission_rate if categ else 0
                #     # 是否需计量单位转换
                #     to_uom = None
                #     if 'uom' in self._context:
                #         to_uom = self.env['product.uom'].browse([self._context['uom']])
                #     if to_uom:
                #         dist_price = self.uom_id._compute_price(std_price, to_uom)
                #     else:
                #         dist_price = std_price
                #     cost_price = dist_price + self.variant_adj_price
                #     values['lst_price'] = cost_price * (1 + rate / 100)

                # if values.get('b2b_price') != None:
                #     b2b_price = values.get('b2b_price')
                #     var_adj = values.get('variant_adj_price') if values.get('variant_adj_price') != None else product.variant_adj_price
                #     # 获取平台分类的加价率
                #     if product.product_tmpl_id.categ_id and product.product_tmpl_id.categ_id.commission_rate:
                #         rate = product.product_tmpl_id.categ_id.commission_rate
                #     else:
                #         categ = product.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                #         rate = categ.commission_rate if categ else 0
                #     std_price = b2b_price + var_adj
                #     # product.lst_price = std_price * (1 + rate / 100)
                #     # product.standard_price = std_price

            elif product.product_tmpl_id.product_owner.parent_id:      # 如果是店铺中的产品
                ###---产品更改变体价格时的处理
                if values.get('variant_adj_price') != None:
                    var_adj = values.get('variant_adj_price') - product.variant_adj_price
                    product.lst_price = product.lst_price + var_adj
                if values.get('shop_adj_price') != None:
                    shop_adj = values.get('shop_adj_price') - product.shop_adj_price
                    product.shop_retail_price = product.shop_retail_price + shop_adj
                ###---产品更改有效状态时的处理
                if values.get('active') == False:
                    values['product_status'] = 'to_delete'
                if values.get('active') == True:
                    values['product_status'] = 'pending'
                ###---产品更改图片时的处理
                if values.get('images') != None:
                    values['image_update'] = 'pending'
                    values['image_mod_time'] = fields.Datetime.now()
                ###---产品更改价格时的处理
                if values.get('shop_retail_price') != None:
                    values['price_update'] = 'pending'
                    values['price_mod_time'] = fields.Datetime.now()
                ###---产品更改变体时的处理
                if values.get('attribute_value_ids') != None:
                    values['relation_update'] = 'pending'
                    values['relation_mod_time'] = fields.Datetime.now()
            else:                                                   # 如果是经销商收录的产品
                True                                                # 不做处理
        ###### 以下为ODOO原功能
        res = super(ProductProduct, self).write(values)
        if 'active' in values and not values['active'] and self.mapped('orderpoint_ids').filtered(lambda r: r.active):
            raise UserError(
                _('You still have some active reordering rules on this product. Please archive or delete them first.'))
        ######################

        ###---供应商更改产品图片时的处理
        if image_processing:
            for product in self:
                collected_prods = self.search([('master_product', '=', product.id)])
                if collected_prods:
                    for shop_prod in collected_prods:
                        for prod_image in product.images:
                            if prod_image not in shop_prod.images:
                                self._cr.execute(
                                    'insert into product_product_image_rel (image_id,product_id) values(%s,%s)',
                                    (prod_image.id, shop_prod.id))
                                shop_prod.write({'image_update': 'pending', 'image_mod_time': mod_time})
                        for shop_image in shop_prod.images:
                            if shop_image not in product.images:
                                self._cr.execute(
                                    'delete from product_product_image_rel where image_id = %s and product_id = %s;'
                                    % (shop_image.id, shop_prod.id))
                                shop_prod.write({'image_update': 'pending', 'image_mod_time': mod_time})
        return res

    def _set_product_lst_price(self):
        for product in self:

            prod_temp = product.product_tmpl_id
            if prod_temp.categ_id and prod_temp.categ_id.commission_rate:
                rate = prod_temp.categ_id.commission_rate
            else:
                categ = self.env['product.category'].sudo().search([('parent_id', '=', False)], limit=1)
                rate = categ.commission_rate if categ else 0

            if self._context.get('uom'):
                value = self.env['product.uom'].browse(self._context['uom'])._compute_price(product.lst_price,
                                                                                            product.uom_id)
            else:
                value = product.lst_price
            value -= product.price_extra * (1 + rate / 100)
            product.write({'list_price': value})

    @api.one
    def btn_upload_to_amazon(self):
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
    def btn_shop_multi_upload(self, cr, uid, active_ids):
        prod_check = self.env['product.product'].browse(active_ids[0])
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not (prod_check.product_status in ('pending','to_delete','fail') or prod_check.image_update in ('pending','to_delete','fail')
                or prod_check.price_update in ('pending','to_delete','fail') or prod_check.stock_update in ('pending','to_delete','fail')
                or prod_check.relation_update in ('pending','to_delete','fail')):
            raise UserError(u'只能从产品变更的目录中选择进行上传')
        for product_id in active_ids:
            product = self.browse(product_id)
            if (product.product_status in ('pending','to_delete','fail') or product.image_update in ('pending','to_delete','fail')
                or product.price_update in ('pending','to_delete','fail') or product.stock_update in ('pending','to_delete','fail')
                or product.relation_update in ('pending','to_delete','fail')):
                product.btn_upload_to_amazon()

    # 定时检查库存，对0或负库存的产品触发变更通知
    @api.multi
    def cron_check_stock_balance(self):
        products = self.env['product.product'].sudo().search([('product_owner.type','=','shop'),('master_product.qty_available','<=',0)])
        mod_time = fields.Datetime.now()
        for product in products:
            product.product_tmpl_id.with_context({'collection_mark': 'collected'}).write({'stock_update':'pending', 'stock_mod_time':mod_time})
        return True

    # 获取UPC码
    def get_upc_code(self, distributor_id, shop_id, product_id):
        avail_code = self.env['b2b.upc.list'].search([('owner','=',distributor_id.id),
                                                      ('state','=','vacant')],limit=1)
        if not avail_code:
            return False
        return avail_code
