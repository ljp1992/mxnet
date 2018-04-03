# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT

class B2bSaleResendWizard(models.TransientModel):
    _name = 'b2b.sale.resend.wizard'
    _description = 're-send products claimed by end customer'

    origin = fields.Many2one('sale.order', u'销售单号')
    order_line = fields.One2many('b2b.sale.resend.wizard.line', 'order_id', u'订单明细')
    amount_total = fields.Float(u'合计金额', compute='_get_total_amount')
    # procurement_ids = fields.One2many('procurement.order', 'sale_line_id', string='Procurements')
    procurement_group_id = fields.Many2one('procurement.group', 'Procurement Group', copy=False)

    @api.onchange('origin')
    def onchange_origin(self):
        freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')
        list = []
        if self.origin:
            for line in self.origin.order_line:
                if line.product_id != freight_product:
                    list.append([0,0,{'order_id': self.id,
                                      'product_id': line.product_id,
                                      'qty': line.product_uom_qty,
                                      'price_unit': line.price_unit,
                                      'sale_line': line.id,
                                    }])
            self.order_line = list

    @api.one
    def _get_total_amount(self):
        amount = 0
        for line in self.order_line:
            amount += line.qty * line.price_unit
        self.amount_total = amount

    def _prepare_procurement_group(self):
        return {'name': self.origin.name}

    @api.multi
    def btn_confirm(self):
        if not self.order_line:
            raise UserError(u'没有需要采购的产品')

        p_amount = 0
        freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')
        freight_obj = self.env['b2b.product.freight.line'].sudo()

        for p_line in self.order_line:
            p_amount += p_line.price_unit * p_line.qty

        if p_amount > self.origin.partner_id.deposit_avail_amt:
            raise UserError(u'在平台预存的余额不足，请先充值')

        # 计算运费
        if not self.origin.partner_shipping_id.country_id:
            raise UserError(u'发货地址未明确所在国家，无法核算运费')
        dest_country = self.origin.partner_shipping_id.country_id
        amount = 0
        freight_line_id = False
        for line in self.order_line:
            if line.qty <= 0:
                line.unlink()
            else:
                freight = freight_obj.search([('product_id', '=', line.product_id.product_tmpl_id.id),
                                              ('country_id', '=', dest_country.id)], limit=1)
                if not freight:
                    raise UserError(u'未找到%s产品的运费' % line.product_id.name)
                amount += freight.cny_amount * line.qty
                if line.product_id == freight_product:
                    freight_line_id = line
        if freight_line_id:
            freight_line_id.price_unit = amount
        else:
            self.order_line.create({
                'order_id': self.id,
                'price_unit': amount,
                'qty': 1,
                'product_id': freight_product.id,
                'is_delivery': True,
            })

        proc_order_line = self.order_line.search([('order_id', '=', self.id), ('is_delivery', '!=', True)])

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

        # 生成procurement order
        new_procs = self.env['procurement.order']  # Empty recordset
        for line in proc_order_line:
            if line.product_id != freight_product:
                new_proc = new_procs.search([('origin','=',self.origin.name),
                                             ('sale_line_id','=',line.sale_line),
                                             ('state','=','done')],limit=1).copy()
                new_proc.write({'state':'confirmed', 'product_qty':line.qty, 'product_uom_qty':line.qty, 'ordered_qty':line.qty})
                new_procs += new_proc
        # 如果平台有库存，则从平台自有仓库发货：判断是否需从平台发货
        purchase = False
        platform = False
        for line in proc_order_line:
            if line.qty > line.product_id.own_stock:
                purchase = True
                line.is_procure = True
            else:
                platform = True
                line.is_procure = False
        # 如果需从平台库存发货
        if platform:
            # 生成拣货单草稿
            picking = picking_obj.sudo().create({'location_id': self.env.ref('b2b_platform.stock_location_wh_own').id,
                                          'picking_type_id': picking_type.id,
                                          'location_dest_id': cust_loc_id.id,
                                          'ship_address': self.origin.partner_shipping_id.id,
                                          'state': 'draft',
                                          'move_type': 'one',
                                          # 'carrier_id': self.carrier_id.id,
                                          'origin': self.origin.name,
                                          'partner_id': self.origin.partner_id.id,
                                          'owner_id': 1,
                                          'company_id_id': 1,
                                          'min_date': datetime.today(),
                                          })
            for pl_line in proc_order_line:
                if not pl_line.is_procure:
                    move_line = self.env['stock.move'].search([('origin', '=', self.origin.name),
                                                               ('product_id', '=', pl_line.product_id.id),
                                                               ('product_qty', '=', pl_line.qty),
                                                               ('state', '!=', 'done'),
                                                               ], limit=1)
                    if move_line:
                        move_line.sudo().write({'picking_id': picking.id})
        # 如果需从经销商采购
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
                                              'ship_address': self.origin.partner_shipping_id.id,
                                              'state': 'draft',
                                              'move_type': 'one',
                                              # 'carrier_id': self.carrier_id.id,
                                              'origin': self.origin.name,
                                              'partner_id': self.origin.partner_id.id,
                                              'owner_id': supplier.id,
                                              'company_id_id': 1,
                                              'min_date': datetime.today(),
                                              })
                move_lines = self.env['stock.move'].sudo().search([('origin', '=', self.origin.name),
                                                                    ('product_id.product_owner', '=', supplier.id),
                                                                    ('state', '!=', 'done')])
                if move_lines:
                    move_lines.write({'state': 'draft'})
                    move_lines.write({'picking_id': picking.id})
                    for m_line in move_lines:
                        ord_qty = m_line.procurement_id.product_qty
                        m_line.write({'product_uom_qty': ord_qty,'ordered_qty': ord_qty})

                # 根据库存情况决定供货路线
                # 如果供应商是经销商自己，则不需要生成采购单
                if supplier != self.origin.shop_id.parent_id:
                    supp_order_line = self.order_line.search([('order_id', '=', self.id),
                                                              ('need_procure', '=', True),
                                                              ('is_procure', '=', True),
                                                              ('is_delivery', '!=', True),
                                                              ('prod_supplier', '=', supplier.id)])
                    if supp_order_line:
                        # 创建并确认采购订单
                        amount = 0
                        po_list = []
                        for line in supp_order_line:
                            if line.product_id != freight_product:
                                freight = freight_obj.search([('product_id', '=', line.product_id.product_tmpl_id.id),
                                                              ('country_id', '=', dest_country.id)], limit=1)
                                amount += freight.cny_amount * line.qty
                                po_list.append([0, 0, {'product_id': line.product_id.id,
                                                       'name': line.product_id.name,
                                                       'date_planned': datetime.today(),
                                                       'product_qty': line.qty,
                                                       'product_uom': line.product_id.product_tmpl_id.uom_id.id,
                                                       'price_unit': line.price_unit,
                                                       'taxs_id': False,
                                                       }])
                        if amount:
                            po_list.append([0, 0, {'product_id': freight_product.id,
                                                   'name': freight_product.name,
                                                   'date_planned': datetime.today(),
                                                   'product_qty': 1,
                                                   'product_uom': freight_product.id,
                                                   'price_unit': amount,
                                                   'taxs_id': False,
                                                   }])
                        purchase_id = purchase_obj.create({
                            'partner_id': supplier.id,
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'origin': self.origin.name,
                            'origin_so': self.origin.id,
                            'distributor': self.origin.partner_id.id,
                            'date_order': datetime.today(),
                            'date_planned': datetime.today(),
                            'picking_type_id': self.env['stock.picking.type'].sudo().search([('name', '=', u'直运')],
                                                                                            limit=1).id,
                            'dest_address_id': self.origin.partner_shipping_id.id,
                            'order_line': po_list
                        })
                        purchase_id.state = 'purchase'

        # 创建并确认客户发票
        cust_inv_obj = self.env['account.invoice'].sudo()
        cust_inv_line_obj = self.env['account.invoice.line'].sudo()
        cust_inv_id = cust_inv_obj.create({
            'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'sale')],
                                                                    limit=1).id or 1,
            'type': 'out_invoice',
            'partner_id': self.origin.partner_id.id,
            'reference': self.origin.name,
            'origin': self.origin.name,
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
            'name': self.origin.name,
            'commercial_partner_id': self.origin.partner_id.id,
            # 'partner_invoice_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.origin.partner_id.id,
        })
        for line in self.order_line:
            cust_inv_line_obj.create({
                'origin': self.origin.name,
                'price_unit': line.price_unit,
                'price_subtotal': line.amount_subtotal,
                'currency_id': self.env.user.company_id.currency_id.id,
                'uom_id': line.product_id.product_tmpl_id.uom_id.id,
                'partner_id': self.origin.partner_id.id,
                'company_id': 1,
                'account_id': 52,
                'price_subtotal_signed': line.amount_subtotal,
                'name': u'100% 的采购货款',
                'product_id': line.product_id.id,
                'invoice_id': cust_inv_id.id,
                'quantity': line.qty,
                })
            line.write({'invoice_status': 'invoiced'})
        cust_inv_id.action_invoice_open()

        self.origin.write({'qdoo_state': 'part-deliver', 'invoice_status': 'invoiced'})

        # return {'name': u'产品清单',
        #         'type': 'ir.actions.act_window',
        #         'res_model': 'product.product',
        #         'view_type': 'form',
        #         'view_mode': 'tree',
        #         # 'view_id': 'view_tree_b2b_distributor_product_list',
        #         # 'search_view_id': 'search_b2b_distributor_product_list',
        #         'domain': [('my_products', '=', True)],
        #         'context': {'create': False},
        #         }

class B2bSaleResendWizardLine(models.TransientModel):
    _name = 'b2b.sale.resend.wizard.line'

    order_id = fields.Many2one('b2b.sale.resend.wizard', u'订单号')
    product_id = fields.Many2one('product.product', u'产品')
    qty = fields.Float(u'数量')
    price_unit = fields.Float(u'单价')
    amount_subtotal = fields.Float(u'金额', compute='_get_subtotal')
    need_procure = fields.Boolean(u'走平台', default=True)
    is_procure = fields.Boolean(u'走供应商')
    own_product = fields.Boolean(u'自有', compute="_if_own_product")
    prod_supplier = fields.Many2one('res.partner', u'供应商', related='product_id.product_owner', readonly=True)
    sale_line = fields.Integer(u'订单行ID')
    is_delivery = fields.Boolean(u'运费')


    @api.one
    def _get_subtotal(self):
        self.amount_subtotal = self.qty * self.price_unit

    @api.multi
    def _prepare_order_line_procurement(self, group_id=False):
        self.ensure_one()
        return {
            'name': self.product_id.name,
            'origin': self.order_id.origin.name,
            'date_planned': datetime.strptime(self.order_id.origin.date_order, DEFAULT_SERVER_DATETIME_FORMAT),
            'product_id': self.product_id.id,
            'product_qty': self.qty,
            'product_uom': self.product_id.product_tmpl_id.uom_id.id,
            'company_id': self.order_id.origin.company_id.id,
            'group_id': group_id,
            'sale_line_id': self.sale_line,
        }