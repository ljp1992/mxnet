# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class b2b_sale_order(models.Model):
    _inherit = 'sale.order'

    qdoo_state = fields.Selection([('new',u'未处理'),('own',u'自发'),('po',u'已转采'),('part-deliver',u'部分发货'),
                       ('delivered',u'已发货'), ('cancel', u'已取消'), ('done', u'已关闭'), ('return', u'已退货'),
                       ('complaint',u'申诉'),('accepted',u'申诉完成'),('rejected',u'申诉退回')],
                       u'状态', default='new')
    origin_doc = fields.Char(u'电商订单号')
    shop_id = fields.Many2one('res.partner', u'店铺', domain="[('type','=','shop')]", required=True)
    picking_id = fields.One2many('stock.picking', 'origin_so', u'拣货单')
    po_ids = fields.One2many('purchase.order', 'origin_so', u'采购单')
    po_count = fields.Integer(string='Purchase Orders', compute='_compute_purchase_ids')
    fba_order = fields.Many2one('b2b.fba.rfq', u'FBA补货单')
    freight = fields.Float(u'运费', compute='_get_freight_charge')
    carrier_id = fields.Many2one("delivery.carrier", string="Delivery Method",
             default=lambda self: self.env['delivery.carrier'].sudo().search([('name', 'ilike', u'供应商')], limit=1).id,
             help="Fill this field if you plan to invoice the shipping based on picking.")
    own_orders = fields.Boolean(u'本商户的订单', compute='_if_own_orders', search='_get_own_orders')

    # 亚马逊订单数据
    e_order_from = fields.Selection([('amazon',u'亚马逊')], u'来源平台', default='amazon')
    e_order_amount = fields.Monetary(u'订单金额')
    e_order_freight = fields.Monetary(u'运费')
    e_order_commission = fields.Monetary(u'佣金')
    e_order_sales = fields.Monetary(u'销售收入')
    e_order_country = fields.Many2one('res.country', u'国家', related='partner_shipping_id.country_id', readonly=True)
    e_order_email = fields.Char(u'客户邮箱', related='partner_shipping_id.email', readonly=True)
    e_order_company = fields.Char(u'公司')
    e_order_address = fields.Char(u'地址', related='partner_shipping_id.street')
    e_order_city = fields.Char(u'城市', related='partner_shipping_id.city')
    e_order_state = fields.Many2one('res.country.state', u'州省', related='partner_shipping_id.state_id')
    e_order_zip = fields.Char(u'邮编', related='partner_shipping_id.zip')
    e_order_phone = fields.Char(u'电话', related='partner_shipping_id.phone')
    delivery_mode = fields.Selection([('mfn', u'自发货'), ('fba', u'FBA')], u'运输方式', default='mfn')

    # 发货信息
    act_carrier = fields.Char(u'快递/物流公司')
    act_waybill = fields.Char(u'快递/物流单号')
    act_deliver_date = fields.Datetime(u'发货日期')

    @api.one
    def _if_own_orders(self):
        dist = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.own_orders = True if self.partner_id == dist else False

    def _get_own_orders(self,operator,value):
        dist = self.env.user.partner_id.parent_id or self.env.user.partner_id
        orders = self.search([('partner_id','=',dist.id)])
        return [('id','in',orders.ids)]

    @api.one
    def _get_freight_charge(self):
        freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')
        self.freight = self.order_line.search([('product_id','=',freight_product.id)])[0].price_unit or 0

    @api.onchange('shop_id')
    def onchange_shop_id(self):
        if self.shop_id and self.shop_id.parent_id:
            self.partner_id = self.shop_id.parent_id
            self.partner_invoice_id = self.shop_id.parent_id
        else:
            self.partner_id = False
            self.partner_invoice_id = False

    @api.multi
    def _compute_purchase_ids(self):
        for order in self:
            order.po_count = len(order.po_ids)

    @api.multi
    def btn_cancel(self):
        return self.write({'qdoo_state': 'cancel'})

    @api.one
    def btn_own(self):
        for line in self.order_line:
            line.need_procure = False
        self.write({'qdoo_state':'own'})

    @api.one
    def btn_ship(self):
        if not self.act_carrier or not self.act_waybill:
            raise UserError(u'请先完善发货信息')
        # 调用接口，回写亚马逊发货信息
        #
        #########################
        self.write({'qdoo_state': 'delivered', 'act_deliver_date':datetime.now()})

    @api.one
    def btn_fake_ship(self):
        if not self.act_carrier or not self.act_waybill:
            raise UserError(u'请先完善发货信息')
        # 调用接口，回写亚马逊发货信息
        #
        #########################
        self.write({'act_deliver_date': datetime.now()})

    @api.one
    def btn_return(self):
        self.write({'qdoo_state': 'return'})

    # 每天检查销售单，发货后30天的关闭订单
    @api.multi
    def cron_close_sale_order(self):
        now = datetime.now()
        orders = self.search([('qdoo_state','=','delivered')])
        for order in orders:
            if order.act_deliver_date and (now - datetime.strptime(order.act_deliver_date, '%Y-%m-%d %H:%M:%S')).days > 30:
                order.write({'qdoo_state':'done'})

    @api.multi
    def action_view_purchase(self):

        purchases = self.env['purchase.order'].search([('origin_so','=',self.id)])
        action = self.env.ref('purchase.purchase_form_action').read()[0]
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases.ids)]
        elif len(purchases) == 1:
            action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            action['res_id'] = purchases.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    def btn_platform(self):
        p_amount = 0
        proc_order_line = self.order_line.search([('order_id','=',self.id),('need_procure','=',True),('is_delivery','!=',True)])
        self_order_line = self.order_line.search([('order_id','=',self.id),('need_procure','=',False),('is_delivery','!=',True)])
        freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')
        freight_obj = self.env['b2b.product.freight.line'].sudo()

        for p_line in proc_order_line:
            if p_line.product_id.qty_available < p_line.product_uom_qty:
                raise UserError(u'%s在系统内没有足够库存，请将走平台选项清除，系统外发货处理，或走取消订单流程' % p_line.product_id.name)
            p_amount += p_line.price_unit * p_line.product_uom_qty

        if p_amount > self.partner_id.deposit_avail_amt:
            raise UserError(u'在平台预存的余额不足，请先充值')

        # 如果不是FBA补货，则计算运费
        if not self.fba_order:
            if not self.partner_shipping_id.country_id:
                raise UserError(u'发货地址未明确所在国家，无法核算运费')
            dest_country = self.partner_shipping_id.country_id

            amount = 0
            freight_line_id = False
            for line in proc_order_line:
                freight = freight_obj.search([('product_id', '=',line.product_id.product_tmpl_id.id),
                            ('country_id','=',dest_country.id)],limit=1)
                if not freight:
                    raise UserError(u'未找到%s产品的运费' % line.product_id.name)
                amount += freight.cny_amount * line.product_uom_qty
                if line.product_id == freight_product:
                    freight_line_id = line

            if freight_line_id:
                freight_line_id.price_unit = amount
            else:
                self.order_line.create({
                            'order_id': self.id,
                            'product_uom': freight_product.uom_id.id,
                            'price_unit': amount,
                            'product_uom_qty': 1,
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'company_id': self.env.user.company_id.id,
                            'state': 'draft',
                            'order_partner_id': self.partner_id.id,
                            'product_id':freight_product.id,
                            'is_delivery': True,
                            'sequence': 1000,
                            })
        else:
            dest_country = self.fba_order.dest_country
        # 创建发货单
        purchase_obj = self.env['purchase.order'].sudo()
        picking_obj = self.env['stock.picking']
        warehouse_obj = self.env['stock.warehouse'].sudo()
        warehouse = warehouse_obj.search([('partner_id', '=', 1)], limit=1)
        if not warehouse:
            raise UserError(u'未找到平台仓库编码，请咨询平台管理人员')

        stock_loc_obj = self.env['stock.location'].sudo()
        cust_loc_id = stock_loc_obj.search([('usage', '=', 'customer')], limit=1)
        if not cust_loc_id:
            raise UserError(u'未找到客户所属库位，请咨询平台管理人员')

        picking_type_obj = self.env['stock.picking.type'].sudo()
        picking_type = picking_type_obj.search([('id', '=', self.env.ref('stock.picking_type_out').id), ('warehouse_id', '=', warehouse.id)], limit=1)
        # picking_type = picking_type_obj.search([('name', '=', u'发货'), ('warehouse_id', '=', warehouse.id)], limit=1)
        if not picking_type:
            raise UserError(u'未找到捡货类型，请咨询平台管理人员')

        self.state = 'sale'
        self.confirmation_date = fields.Datetime.now()

        # 生成采购单的procurement order
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        new_procs = self.env['procurement.order']  # Empty recordset
        for line in proc_order_line:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            if not line.order_id.procurement_group_id:
                vals = line.order_id._prepare_procurement_group()
                line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)

            vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            new_proc = self.env["procurement.order"].with_context(procurement_autorun_defer=True).create(vals)
            # new_proc.message_post_with_view('mail.message_origin_link',
            #                                 values={'self': new_proc, 'origin': line.order_id},
            #                                 subtype_id=self.env.ref('mail.mt_note').id)
            new_procs += new_proc
        # 生成自发货的procurement order
        for line in self_order_line:
            if line.state != 'sale' or not line.product_id._need_procurement():
                continue
            qty = 0.0
            for proc in line.procurement_ids:
                qty += proc.product_qty
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            if not line.order_id.procurement_group_id:
                vals = line.order_id._prepare_procurement_group()
                line.order_id.procurement_group_id = self.env["procurement.group"].create(vals)

            vals = line._prepare_order_line_procurement(group_id=line.order_id.procurement_group_id.id)
            vals['product_qty'] = line.product_uom_qty - qty
            new_proc = self.env["procurement.order"].with_context(procurement_autorun_defer=True).create(vals)
            # new_proc.message_post_with_view('mail.message_origin_link',
            #                                 values={'self': new_proc, 'origin': line.order_id},
            #                                 subtype_id=self.env.ref('mail.mt_note').id)
            new_procs += new_proc
        # 生成stock_move
        autocommit = False
        for procurement in new_procs:
            if procurement.state not in ("running", "done"):
                try:
                    if procurement._assign():
                        res = procurement._run()
                        if res:
                            procurement.write({'state': 'running'})
                        else:
                            procurement.write({'state': 'exception'})
                    else:
                        procurement.message_post(body=_('No rule matching this procurement'))
                        procurement.write({'state': 'exception'})
                    if autocommit:
                        self.env.cr.commit()
                except :
                    if autocommit:
                        self.env.cr.rollback()
                        continue
                    else:
                        raise
        # 如果平台有库存，则从平台自有仓库发货：判断是否需从平台发货
        purchase = False
        platform = False
        self_stock = False
        for line in proc_order_line:
            if line.product_uom_qty > line.product_id.own_stock:
                purchase = True
                line.is_procure = True
            else:
                platform = True
                line.is_procure = False
        # 如果有自发货
        if self_order_line:
            self_stock = True
        # 如果需从平台库存发货
        if platform:
            # 生成拣货单草稿
            picking = picking_obj.sudo().create({'location_id': self.env.ref('b2b_platform.stock_location_wh_own').id,
                                          'picking_type_id': picking_type.id,
                                          'location_dest_id': cust_loc_id.id,
                                          'ship_address': self.partner_shipping_id.id,
                                          'state': 'draft',
                                          'move_type': 'one',
                                          # 'carrier_id': self.carrier_id.id,
                                          'origin': self.name,
                                          'partner_id': self.partner_id.id,
                                          'owner_id': 1,
                                          'company_id_id': 1,
                                          'min_date': datetime.today(),
                                          })
            for pl_line in proc_order_line:
                if not pl_line.is_procure:
                    move_line = self.env['stock.move'].search([('origin', '=', self.name),
                                                                ('product_id', '=', pl_line.product_id.id),
                                                                ('product_qty', '=', pl_line.product_uom_qty),
                                                                ('state', '!=', 'done'),
                                                                ], limit=1)
                    if move_line:
                        move_line.sudo().write({'picking_id': picking.id})
        # 如果需从自有库存发货
        if self_stock:
            # 生成拣货单草稿
            supp_loc_id = stock_loc_obj.search([('location_id.name', '=', u'供应商库存'),
                                                ('partner_id', '=', self.shop_id.parent_id.id)], limit=1)
            picking = picking_obj.sudo().create(
                {'location_id': supp_loc_id.id,
                 'picking_type_id': picking_type.id,
                 'location_dest_id': cust_loc_id.id,
                 'ship_address': self.partner_shipping_id.id,
                 'state': 'draft',
                 'move_type': 'one',
                 # 'carrier_id': self.carrier_id.id,
                 'origin': self.name,
                 'partner_id': self.partner_id.id,
                 'owner_id': self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id,
                 'company_id_id': 1,
                 'min_date': datetime.today(),
                 })
            for pl_line in self_order_line:
                if not pl_line.is_procure:
                    move_line = self.env['stock.move'].search([('origin', '=', self.name),
                                                               ('product_id', '=',
                                                                pl_line.product_id.id),
                                                               ('product_qty', '=',
                                                                pl_line.product_uom_qty),
                                                               ('state', '!=', 'done'),
                                                               ], limit=1)
                    if move_line:
                        move_line.sudo().write({'picking_id': picking.id})
        # 如果需从供应商采购
        if purchase:
            # 拆分采购单
            supp_list = proc_order_line.mapped('prod_supplier')
            for supplier in supp_list:
                supp_loc_id = stock_loc_obj.search([('location_id.name', '=', u'供应商库存'),
                                                    ('partner_id', '=', supplier.id)], limit=1)
                if not supp_loc_id:
                    raise UserError(u'未找到供应商所属库位，请咨询平台管理人员')

                # 生成拣货单草稿
                picking = picking_obj.sudo().create({'location_id': supp_loc_id.id,
                                          'picking_type_id': picking_type.id,
                                          'location_dest_id': cust_loc_id.id,
                                          'ship_address': self.partner_shipping_id.id,
                                          'state': 'draft',
                                          'move_type': 'one',
                                          # 'carrier_id': self.carrier_id.id,
                                          'origin': self.name,
                                          'partner_id': self.partner_id.id,
                                          'owner_id': supplier.id,
                                          'company_id_id': 1,
                                          'min_date': datetime.today(),
                                          })
                move_lines = self.env['stock.move'].search([('origin', '=', self.name),
                                                            ('product_id.product_owner', '=', supplier.id),
                                                            ('state', '!=', 'done')])
                if move_lines:
                    move_lines.sudo().write({'picking_id':picking.id})

                # 根据库存情况决定供货路线
                # 如果供应商是经销商自己，则不需要生成采购单
                if supplier != self.shop_id.parent_id:
                    supp_order_line = proc_order_line.search([('order_id','=',self.id),
                                                              ('need_procure','=',True),
                                                              ('is_procure','=',True),
                                                              ('prod_supplier','=',supplier.id)])
                    # purchase = False
                    # # 平台自有库存若能满足订单数量，则不生成采购单
                    # for line in supp_order_line:
                    #     if line.product_uom_qty > line.product_id.own_stock:
                    #         purchase = True
                    #         break
                    # if purchase:
                    if supp_order_line:
                        # 创建并确认采购订单
                        amount = 0
                        po_list = []
                        for line in supp_order_line:
                            if line.product_id != freight_product:
                                freight = freight_obj.search([('product_id', '=', line.product_id.product_tmpl_id.id),
                                                              ('country_id', '=', dest_country.id)], limit=1)
                                amount += freight.cny_amount * line.product_uom_qty
                                po_list.append([0, 0, {'product_id': line.product_id.id,
                                                       'name': line.product_id.name,
                                                       'date_planned': datetime.today(),
                                                       'product_qty': line.product_uom_qty,
                                                       'product_uom': line.product_uom.id,
                                                       'price_unit': line.price_unit,
                                                       'taxes_id': False,
                                                       }])
                        if amount:
                            if self.fba_order:
                                amount = self.fba_order.freight
                                if self.fba_order.carrier_id == self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier'):
                                    po_list.append([0, 0, {'product_id': freight_product.id,
                                                           'name': freight_product.name,
                                                           'date_planned': datetime.today(),
                                                           'product_qty': 1,
                                                           'product_uom': freight_product.uom_id.id,
                                                           'price_unit': amount,
                                                           'taxes_id': False,
                                                           }])
                            else:
                                po_list.append([0, 0, {'product_id': freight_product.id,
                                                       'name': freight_product.name,
                                                       'date_planned': datetime.today(),
                                                       'product_qty': 1,
                                                       'product_uom': freight_product.uom_id.id,
                                                       'price_unit': amount,
                                                       'taxes_id': False,
                                                       }])
                        purchase_id = purchase_obj.create({
                            'partner_id': supplier.id,
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'origin': self.name,
                            'origin_so': self.id,
                            'distributor': self.partner_id.id,
                            'date_order': datetime.today(),
                            'date_planned': datetime.today(),
                            'picking_type_id': self.env['stock.picking.type'].sudo().search([('name', '=', u'直运')],limit=1).id,
                            'dest_address_id': self.partner_shipping_id.id,
                            'order_line': po_list
                        })
                        purchase_id.state = 'purchase'

        # 创建并确认客户发票
        if proc_order_line:
            cust_inv_obj = self.env['account.invoice'].sudo()
            cust_inv_line_obj = self.env['account.invoice.line'].sudo()
            cust_inv_id = cust_inv_obj.create({
                'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'sale')],
                                                                        limit=1).id or 1,
                'type': 'out_invoice',
                'partner_id': self.partner_id.id,
                'reference': self.name,
                'origin': self.name,
                'amount_total_company_signed': self.amount_total,
                'residual': self.amount_total,
                'amount_untaxed': self.amount_total,
                'residual_company_signed': self.amount_total,
                'amount_total_signed': self.amount_total,
                'residual_signed': self.amount_total,
                'amount_total': self.amount_total,
                'amount_untaxed_signed': self.amount_total,
                'state': 'draft',
                'account_id': 4,
                'currency_id': 8,
                'name': self.name,
                'commercial_partner_id': self.partner_id.id,
                # 'partner_invoice_id': self.partner_invoice_id.id,
                'partner_shipping_id': self.partner_id.id,
            })
            for line in self.order_line:
                cust_inv_line_obj.create({
                    'origin': self.name,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                    'currency_id': line.currency_id.id,
                    'uom_id': line.product_uom.id,
                    'partner_id': self.partner_id.id,
                    'company_id': 1,
                    'account_id': 52,
                    'price_subtotal_signed': line.price_subtotal,
                    'name': u'100% 的采购货款',
                    'product_id': line.product_id.id,
                    'invoice_id': cust_inv_id.id,
                    'quantity': line.product_uom_qty,
                    })
                line.write({'invoice_status': 'invoiced'})
            cust_inv_id.action_invoice_open()
        if self.order_line.search([('order_id', '=', self.id), ('need_procure', '=', False)]):
            self.write({'qdoo_state': 'own', 'invoice_status': 'invoiced'})
        else:
            self.write({'qdoo_state': 'po', 'invoice_status': 'invoiced'})


    @api.one
    def btn_complaint(self):
        self.write({'qdoo_state': 'complaint'})

    @api.multi
    #def post_order_shipping(self):
    #    for record in self:
    #        api_sdk = record.channel_mapping_ids[0].channel_id.get_mws_api_sdk()
    #        self.env['mws.feed'].post_order_shipping(record,record.channel_mapping_ids[0].channel_id,api_sdk)

    def btn_resend_submit(self):
        # self.write({'qdoo_state': 'resend'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'b2b.sale.resend.wizard',
            'name': '补发货',
            'views': [(False, 'form')],
            'view_mode': 'form',
            'view_type': 'form',
            # 'view_id': 'import_inventory_wizard_form',
            'target': 'new',
            'context': {'default_origin': self.id},
            # 'domain': [('product_in_own_shops', '=', True)]
        }

class b2b_sale_order_line(models.Model):
    _inherit = 'sale.order.line'

    shop_product = fields.Many2one('product.product', string=u'商品', domain=[('sale_ok', '=', True)],
                                 change_default=True, ondelete='restrict')
    shop_currency = fields.Many2one('res.currency', u'币种')
    shop_unit_price = fields.Float(u'单价')
    prod_supplier = fields.Many2one('res.partner', u'供应商', related='product_id.product_owner', readonly=True)
    need_procure = fields.Boolean(u'走平台', default=True)
    is_procure = fields.Boolean(u'走供应商')
    own_product = fields.Boolean(u'自有', compute="_if_own_product")

    @api.onchange('shop_product')
    def _onchange_shop_product(self):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if self.shop_product and self.shop_product.master_product:
            self.product_id = self.shop_product.master_product
            self.price_unit = self.shop_product.master_product.lst_price
            self.currency_id = self.env.user.company_id.currency_id
            if self.product_id.product_owner == partner:
                self.need_procure = False
        else:
            self.product_id = False

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.order_id.pricelist_id and self.order_id.partner_id:
            product = self.product_id.with_context(
                lang=self.order_id.partner_id.lang,
                partner=self.order_id.partner_id.id,
                quantity=self.product_uom_qty,
                date=self.order_id.date_order,
                pricelist=self.order_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.shop_product.master_product.lst_price

    @api.one
    def _if_own_product(self):
        # 如果是自有产品，则不需经平台采购流程
        if self.product_id and self.order_id.shop_id and self.product_id.product_owner == self.order_id.shop_id.parent_id:
            self.own_product = True