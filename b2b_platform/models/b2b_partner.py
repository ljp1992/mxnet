# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools
from odoo.osv import osv
from openerp import SUPERUSER_ID
from odoo.exceptions import UserError
from odoo import _, exceptions
from lxml import etree
import urllib
import urllib2
import base64
import random
import string
import json
import logging


class b2b_partner(models.Model):
    _inherit = 'res.partner'

    type = fields.Selection(
        [('operator', u'业务员'),
         ('shop', u'店铺'),
         ('warehouse', u'库管'),
         ('contact', 'Contact'),
         ('invoice', 'Invoice address'),
         ('delivery', 'Shipping address'),
         ('other', 'Other address')], string='Address Type',
        default='contact',
        help="Used to select automatically the right address according to the context in sales and purchases documents.")
    qdoo_func = fields.Selection([
        ('supplier', u'供应商'),
        ('distributor', u'经销商'),
        ('platform', u'平台')
    ], u'平台角色')
    introduction = fields.Text(u'公司简介')
    qdoo_state = fields.Selection([('new', u'审核中'), ('approved', u'已审核')], u'状态', default='new')
    parent_id = fields.Many2one('res.partner', string='Related Company', index=True,
                                default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id
                                if self.user_has_groups('b2b_platform.group_qdoo_supplier_manager,'
                                                        'b2b_platform.group_qdoo_distributor_manager')
                                   and not self.env.uid == SUPERUSER_ID
                                else False)
    shop_operator = fields.Many2one('res.partner', u'店铺管理员',
                            domain="['|','&',('parent_id','=',parent_id),('type','=','operator'),('sys_user_id','=',uid)]")
    shop_markup = fields.Float(u'售价上浮率(%)', digits=(16,2))
    #remove shop_language required
    shop_language = fields.Selection([('chinese', u'中文'),('english', u'英文'),('german', u'德文'),
            ('french', u'法文'),('spanish', u'西班牙文'),('italian', u'意大利文'),('japanese', u'日文')], u'店铺语言')
    shop_currency = fields.Many2one('res.currency', u'店铺所用币种', required=True)
    amazon_instance_id = fields.Many2one('amazon.instance.ept', u'亚马逊店铺', readonly=True)
    amazon_seller_id = fields.Many2one('amazon.seller.ept', u'亚马逊主站', readonly=True)
    qq_id = fields.Char(u'QQ号码')
    deposit_amt = fields.Float(u'预付款余额', digits=(16,2), compute='_prepayment_get')
    deposit_avail_amt = fields.Float(u'预付款可用余额', digits=(16,2), compute='_prepayment_get')
    withdraw_balance = fields.Float(u'提现余额', digits=(16, 2), compute='_withdraw_balance_get')
    kanban_display = fields.Boolean(u'看板显示', compute='_displayable_on_kanban', search='_search_displayable_on_kanban')
    debit_value = fields.Float(u'可结算金额', compute='_debit_to_value')
    cust_to_shop = fields.Many2one('res.partner', u'客户所属店铺')
    own_shops = fields.Many2one('res.partner', u'自有店铺', compute='_if_own_shop', search='_search_own_shop')
    product_disclosure = fields.Selection([('close',u'不开放'), ('semi',u'部分开放'), ('open',u'完全开放')],
                                          u'产品开放级别', default='open', required=True)
    disclosure_is_visible = fields.Boolean(u'开放级别可见', compute='_if_disclosable')
    city = fields.Char(u'城市')
    supplier_manager = fields.Many2one('res.users', u'供应商管理员', compute='_get_supplier_manager', search='_is_supplier_manager')
    sys_user_id = fields.Many2one('res.users', u'系统账号', compute='_get_user_id', search='_search_user_id')

    @api.one
    def _get_user_id(self):
        user_ids = self.with_context(active_test=False).env['res.users'].sudo().search([('partner_id', '=', self.id)])
        if len(user_ids) == 1:
            self.sys_user_id = user_ids[0]

    def _search_user_id(self, operator, value):
        list = self.user_ids.search([('id', '=', value)]).partner_id
        return [('id', 'in', list.ids)]

    @api.one
    def _if_disclosable(self):
        self.disclosure_is_visible = False
        for line in self.category_id:
            if line.qdoo_func == 'supplier' and self.is_company:
                self.disclosure_is_visible = True

    @api.one
    def _get_supplier_manager(self):
        self.supplier_manager = self.env['res.users'].search([('partner_id','=',self.id)],limit=1)

    def _is_supplier_manager(self,operator,value):
        partners = self.search([('id', '=', self.env.user.partner_id.id)])
        return [('id', 'in', partners.ids)]

    @api.one
    def _if_own_shop(self):
        user_id = self.env.user
        if self.type == 'shop' and self.parent_id:
            # 如果是经销商管理员
            if self.parent_id == user_id.partner_id:
                self.own_shops = True
            # 如果是经销商业务员
            elif self.parent_id == user_id.partner_id.parent_id:
                self.own_shops = True

    def _search_own_shop(self, operator, value):
        ids = []
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        lines = self.search([('type', '=', 'shop'), ('parent_id', '=', partner.id)])
        for line in lines:
            ids.append(line.id)
        return [('id', 'in', ids)]

    @api.multi
    def write(self, vals):
        if vals.get('shop_markup'):
            old_markup = self.shop_markup
            markup = vals.get('shop_markup')
            for rec in self:
                prod_tmpl_obj = self.env['product.template'].with_context({'collection_mark': 'collected'})
                prod_prod_obj = self.env['product.product'].with_context({'collection_mark': 'collected'})
                prod_attr_price_obj = self.env['product.attribute.price'].sudo()
                # 更新店铺中收录的产品
                shop_prods = prod_tmpl_obj.search([('product_owner', '=', rec.id)])
                if shop_prods:
                    mod_time = fields.Datetime.now()
                    for s_prod in shop_prods:
                        s_prod.list_price = s_prod.list_price / (1 + old_markup / 100.0) * (1 + markup / 100.0)

                        s_attr_val = s_prod.mapped('attribute_line_ids')
                        for value in s_attr_val:
                            vlu = value[0].id
                            s_attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', s_prod.id),
                                                                       ('value_id', '=', vlu)])
                            if s_attr_price:
                                s_attr_price.write({'price_extra': s_attr_price.price_extra / (
                                    1 + old_markup / 100.0) * (1 + markup / 100.0)})
                        for prod in prod_prod_obj.search([('product_tmpl_id', '=', s_prod.id)]):
                            prod._set_product_lst_price()
                            prod.write({'price_update': 'pending', 'price_mod_time': mod_time})
        ##########################################################################
        # res.partner must only allow to set the company_id of a partner if it
        # is the same as the company of all users that inherit from this partner
        # (this is to allow the code from res_users to write to the partner!) or
        # if setting the company_id to False (this is compatible with any user
        # company)
        if vals.get('website'):
            vals['website'] = self._clean_website(vals['website'])
        if vals.get('parent_id'):
            vals['company_name'] = False
        if vals.get('company_id'):
            company = self.env['res.company'].browse(vals['company_id'])
            for partner in self:
                if partner.user_ids:
                    companies = set(user.company_id for user in partner.user_ids)
                    if len(companies) > 1 or company not in companies:
                        raise UserError(_(
                            "You can not change the company as the partner/user has multiple user linked with different companies."))
        tools.image_resize_images(vals)

        result = True
        # To write in SUPERUSER on field is_company and avoid access rights problems.
        if 'is_company' in vals and self.user_has_groups(
                'base.group_partner_manager') and not self.env.uid == SUPERUSER_ID:
            result = super(b2b_partner, self).sudo().write({'is_company': vals.get('is_company')})
            del vals['is_company']
        result = result and super(b2b_partner, self).write(vals)
        for partner in self:
            if any(u.has_group('base.group_user') for u in partner.user_ids if u != self.env.user):
                self.env['res.users'].check_access_rights('write')
            partner._fields_sync(vals)
        return result
        ##########################################################################

    @api.onchange('shop_markup')
    def onchange_shop_markup(self):
        prod_tmpl_obj = self.env['product.template']
        prod_prod_obj = self.env['product.product']
        prod_attr_price_obj = self.env['product.attribute.price'].sudo()
        # 更新店铺中收录的产品
        shop_prods = prod_tmpl_obj.search([('product_owner', '=', self.id)])
        if shop_prods:
            for s_prod in shop_prods:

                markup_lines = self.env['b2b.trader.markup'].search(
                    [('partner', '=', self.parend_id.id), ('id', '=', s_prod.trader_categ_id.id)], limit=1)
                d_markup = markup_lines.rate or 0

                s_prod.write({'list_price': s_prod.standard_price * (1 + d_markup / 100.0) * (1 + self.shop_markup / 100.0)})

                s_attr_val = s_prod.mapped('attribute_value_ids')
                for value in s_attr_val:
                    vlu = value[0].id
                    s_attr_price = prod_attr_price_obj.search([('product_tmpl_id', '=', s_prod.id),
                                                               ('value_id', '=', vlu)])
                    if s_attr_price:
                        s_attr_price.write({'price_extra': s_attr_price.price_extra * (1 + self.shop_markup / 100.0)})
                s_prod._set_product_lst_price()

    @api.one
    def _debit_to_value(self):
        self.debit_value = self.debit

    @api.one
    def _displayable_on_kanban(self):
        if self.env.user.partner_id == self or self.env.user.partner_id.parent_id == self:
            self.kanban_display = True

    def _search_displayable_on_kanban(self,operarot,value):
        if value == True:
            ids = []
            partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
            lines = self.search([('id', '=', partner.id)])
            if lines:
                for line in lines:
                    ids.append(line.id)
            return [('id', 'in', ids)]

    @api.one
    def _withdraw_balance_get(self):
        amount = 0
        withdrawn = 0
        move_line_obj = self.env['account.move.line'].sudo()
        journal_id = self.env.ref('b2b_platform.account_journal_data_supplier').id
        withdraw_account_id = self.env['account.account'].sudo().search([('name', '=', u'商户提现')], limit=1).id
        bank_account_id = self.env['account.account'].sudo().search([('name', '=', u'银行')], limit=1).id
        move_lines = move_line_obj.search([('journal_id','=',journal_id), ('partner_id','=',self.id), ('account_id','=',withdraw_account_id)])
        if move_lines:
            for line in move_lines:
                amount += line.credit
        move_lines_2 = move_line_obj.search([('journal_id', '=', journal_id), ('partner_id', '=', self.id), ('account_id', '=', bank_account_id)])
        if move_lines_2:
            for line in move_lines_2:
                withdrawn += line.credit
        self.withdraw_balance = amount - withdrawn

    @api.one
    def _prepayment_get(self):

        move_obj = self.env['account.move'].sudo()
        invoice_obj = self.env['account.invoice'].sudo()
        dist = self.env.user.partner_id.parent_id or self.env.user.partner_id

        # 累计充值金额
        deposit_amt = 0
        journal_id = self.env.ref('b2b_platform.account_journal_data_deposit')
        deposits = move_obj.search([('journal_id','=',journal_id.id),('partner_id','=',dist.id),('state','=','posted')])
        if deposits:
            for deposit in deposits:
                deposit_amt += deposit.amount

        # 累计开票金额跟未支付金额
        inv_amt = 0
        unpaid_amt = 0
        invoices = invoice_obj.search([('partner_id','=',dist.id),('type','=','out_invoice')])
        if invoices:
            for invoice in invoices:
                inv_amt += invoice.amount_total
                unpaid_amt += invoice.residual

        self.deposit_amt = deposit_amt - inv_amt + unpaid_amt
        self.deposit_avail_amt = deposit_amt - inv_amt

    # http post method
    def _url_post(self,url, data):
        req = urllib2.Request(url)
        data = urllib.urlencode(data)
        # enable cookie
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        response = opener.open(req, data)
        return response.read()

    # 用户注册审核通过
    @api.multi
    def btn_registration_pass(self):
        if (not self.category_id) or (not self.email):
            raise osv.except_osv("资料不完整，请继续完善！")

        if len(self.search([('mobile','=',self.mobile)])) > 1:
            raise UserError(u'该商户的手机号已被占用，请核查')

        user_obj = self.env['res.users'].sudo()
        group_obj = self.env['res.groups'].sudo()
        for rec in self:
            user_id = user_obj.search([('partner_id','=',rec.id)],limit=1)
            if not user_id:
                raise osv.except_osv("未找到对应的系统账号，用户已申请入驻？")
            if rec.category_id:
                # 去掉门户权限组
                if user_id.has_group('base.group_portal'):
                    portal_group_id = self.env['ir.model.data'].get_object('base', 'group_portal')
                    user_id.write({'groups_id': [(5, portal_group_id.id)]})
                for categ in rec.category_id:
                    # 如果有供应商角色
                    if categ.name == u'供应商':
                        # 添加管理员权限
                        if not user_id.sudo().has_group('b2b_platform.group_qdoo_supplier_manager'):
                            group_id = self.env['ir.model.data'].sudo().get_object('b2b_platform', 'group_qdoo_supplier_manager')
                            # res_group = group_obj.search([('id','=',group_id.id)])
                            # res_group.write({'users': [(4, user_id.id)]})
                            user_id.write({'groups_id': [(4, group_id.id)]})
                        # # 添加仓库
                        # wh_obj = self.env['stock.warehouse']
                        # warehouse = wh_obj.sudo().search([('partner_id','=',rec.id)])
                        # if not warehouse:
                        #     wh_obj.create({'name':rec.name,
                        #                     'partner_id':rec.id,
                        #                     'code': 'S' + str(rec.id),
                        #                     'reception_steps':'one_step',
                        #                     'delivery_steps':'ship_only',
                        #                     'buy_to_resupply':False,
                        #                     })
                        # 添加供应商所属库位
                        stock_location_obj = self.env['stock.location']
                        location = stock_location_obj.sudo().search([('partner_id', '=', rec.id)])
                        if not location:
                            stock_location_obj.create({'name': rec.name,
                                           'location_id': self.env.ref('b2b_platform.stock_location_wh_suppliers').id,
                                           'partner_id': rec.id,
                                           'usage': 'internal',
                                           })
                            # # 添加第三方仓库所属库位, 不自动创建，改为手工添加
                            # stock_location_obj.create({'name': rec.name,
                            #                'location_id': self.env.ref('b2b_platform.stock_location_wh_3pl').id,
                            #                'partner_id': rec.id,
                            #                'usage': 'internal',
                            #                })
                    # 如果有经销商角色
                    elif categ.name == u'经销商':
                        # 添加管理员权限
                        if not user_id.has_group('b2b_platform.group_qdoo_distributor_manager'):
                            dist_group_id = self.env['ir.model.data'].sudo().get_object('b2b_platform', 'group_qdoo_distributor_manager')
                            # dist_group = group_obj.search([('id', '=', dist_group_id.id)])
                            # dist_group.write({'users': [(4, user_id.id)]})
                            user_id.write({'groups_id': [(4, dist_group_id.id)]})
            # 审核完成
            rec.sudo().qdoo_state = 'approved'

            # 收汇系统集成
            '''
            exchange_system_url = self.env['ir.config_parameter'].get_param('exchange_system_url')

            if exchange_system_url:
                # 原始收汇密码
                origin_exchange_password = ''.join(random.sample(string.ascii_letters + string.digits, 8))
                exchange_key = 'esupplyc'
                exchange_password = base64.b64encode(origin_exchange_password + exchange_key)

                str_exchange_system_url = exchange_system_url + '/usercenter/user/gmRegist'
                data = {'login_account':user_id.login, 'password':exchange_password, 'mobile':user_id.partner_id.mobile}
                str_response = self._url_post(str_exchange_system_url, data)
                json_response = json.loads(str_response)

                if json_response['error_no']==0:
                    user_id.write({'exchange_token': exchange_password,'is_bind':True})
                else:
                    user_id.write({'exchange_system_error': json_response['error_info'], 'is_bind': False})
            '''

    def get_list(self):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id

        report_obj = self.env['b2b.trader.accounting']
        invoice_obj = self.env['account.invoice']
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']

        report_obj.search([('partner_id', '=', partner.id)]).unlink()

        # 充值明细
        journal_id = self.env.ref('b2b_platform.account_journal_data_deposit')
        deposits = move_obj.search(
            [('journal_id', '=', journal_id.id), ('partner_id', '=', partner.id), ('state', '=', 'posted')])
        for deposit in deposits:
            report_obj.create({'partner_id': partner.id,
                        'categ': u'充值',
                        'number': deposit.name,
                        'origin': deposit.ref,
                        'date_invoice': deposit.date,
                        'amount_total': deposit.amount,
                        'state': 'paid',
                        })

        # 客户发票
        invoices = invoice_obj.search([('partner_id', '=', partner.id), ('type', '=', 'out_invoice')])
        for inv in invoices:
            report_obj.create({'partner_id': partner.id,
                         'categ': u'发票',
                         'number': inv.number,
                         'origin': inv.origin,
                         'date_invoice': inv.date_invoice,
                         'amount_total': inv.amount_total * -1.0,
                         'state': inv.state,
                         })

        # 供应商待结算账单
        bills = invoice_obj.search([('partner_id', '=', partner.id), ('type', '=', 'in_invoice'), ('state', '=', 'open')])
        for bill in bills:
            report_obj.create({'partner_id': partner.id,
                         'categ': u'待结算',
                         'number': bill.number,
                         'origin': bill.origin,
                         'date_invoice': bill.date_invoice,
                         'amount_total': bill.amount_total,
                         'state': bill.state,
                         })

        # 可提现金额明细
        journal = self.env.ref('b2b_platform.account_journal_data_supplier').id
        bank_account_id = self.env['account.account'].sudo().search([('name', '=', u'银行')], limit=1).id
        payable_account_id = self.env['account.account'].sudo().search([('name', '=', u'应付账款')], limit=1).id
        sup_bills = invoice_obj.search(
            [('partner_id', '=', partner.id), ('type', '=', 'in_invoice'), ('state', '=', 'paid')])
        for line in sup_bills:
            report_obj.create({'partner_id': partner.id,
                         'categ': u'已结算',
                         'number': line.number,
                         'origin': line.origin,
                         'date_invoice': line.date_invoice,
                         'amount_total': line.amount_total,
                         'state': line.state,
                         })

        move_lines_2 = move_line_obj.search(
            [('journal_id', '=', journal), ('partner_id', '=', partner.id), ('account_id', '=', bank_account_id)])
        for line2 in move_lines_2:
            report_obj.create({'partner_id': partner.id,
                         'categ': u'已提现',
                         'number': line2.name,
                         'origin': line2.ref,
                         'date_invoice': line2.date,
                         'amount_total': line2.credit * -1.0,
                         'state': 'paid',
                         })

        return {
            'name': '商户交易明细',
            'view_type': 'tree',
            "view_mode": 'tree',
            'res_model': 'b2b.trader.accounting',
            'type': 'ir.actions.act_window',
            'views': [(False, 'tree'), (False, 'form')],
            'context': {'create': False, 'edit': False},
            'domain': [('partner_id', '=', self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)]
        }


class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    child_id = fields.One2many('res.partner.category', 'parent_id', u'子类别')
    qdoo_func = fields.Selection([
        ('distributor', u'经销商'),
        ('supplier', u'供应商'),
    ], u'商户类型')


class b2b_res_users(models.Model):
    _inherit = 'res.users'

    qdoo_func = fields.Selection(u'平台角色', related = 'partner_id.qdoo_func')
    type = fields.Selection(u'业务角色', related = 'partner_id.type')
    # shop_operator = fields.Many2one('res.partner', u'店铺管理员', domain="[('type','=','operator')]",
    #                                 related='partner_id.shop_operator')
    ownership = fields.Many2one('res.partner', u'所属商户',related='partner_id.parent_id')
    owner_manager = fields.Many2one('res.users', u'商户管理员',compute='_get_owner_manager', search='_search_own_manager')

    # 收汇系统集成
    # 随机生成token
    exchange_token=fields.Char('token')
    # 是否绑定
    is_bind=fields.Boolean('is_bind')
    # 收汇系统集成error
    exchange_system_error=fields.Char('exchange_system_error')


    @api.one
    def _get_owner_manager(self):
        self.owner_manager = self.search([('partner_id.parent_id','=',self.env.user.partner_id.id)])

    def _search_own_manager(self,operator,uid):
        users = self.search([('partner_id.parent_id', '=', self.env.user.partner_id.id)])
        return [('id', 'in', users.ids)]

    @api.multi
    def write(self, vals):
        #############################################
        # 商户创建的账号要关联商户
        for user in self:
            if user.type in ('shop', 'operator', 'warehouse') and (not user.partner_id.parent_id):
                distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
                if not distributor:
                    raise UserError(u'未找到您所属的经销商，请联系平台管理员')
                user.partner_id.parent_id = distributor
        #############################################
        write_res = super(b2b_res_users, self).write(vals)
        if vals.get('groups_id'):
            # form: {'group_ids': [(3, 10), (3, 3), (4, 10), (4, 3)]} or {'group_ids': [(6, 0, [ids]}
            user_group_ids = [command[1] for command in vals['groups_id'] if command[0] == 4]
            user_group_ids += [id for command in vals['groups_id'] if command[0] == 6 for id in command[2]]
            self.env['mail.channel'].search([('group_ids', 'in', user_group_ids)])._subscribe_users()
        return write_res

    @api.model
    def create(self, values):
        if not values.get('login', False):
            action = self.env.ref('base.action_res_users')
            msg = _("You cannot create a new user from here.\n To create new user please go to configuration panel.")
            raise exceptions.RedirectWarning(msg, action.id, _('Go to the configuration panel'))

        user = super(b2b_res_users, self).create(values)

        #############################################
        # 商户创建的账号要关联商户
        distributor = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if not distributor:
            raise UserError(u'未找到您所属的经销商，请联系平台管理员')
        # if values.get('type', False) in ('shop', 'operator', 'warehouse'):
        if user.type in ('shop', 'operator', 'warehouse'):
            user.partner_id.parent_id = distributor
        #############################################

        # create a welcome message
        user._create_welcome_message()

        return user

class B2bTraderAccounting(models.TransientModel):
    _name = 'b2b.trader.accounting'
    _order = 'date_invoice'

    partner_id = fields.Many2one('res.partner', u'商户')
    categ = fields.Char(u'类别')
    number = fields.Char(u'凭证')
    origin = fields.Char(u'源单据')
    date_invoice = fields.Date(u'日期')
    amount_total = fields.Float(u'金额', digits=(16,2))
    state = fields.Selection([('open', u'打开'), ('paid', '已付')], u'状态')


