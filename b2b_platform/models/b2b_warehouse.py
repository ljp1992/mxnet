# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta

class B2bPicking(models.Model):
    _inherit = "stock.picking"

    origin_so = fields.Many2one('sale.order', u'销售订单', ondelete='restrict')
    ship_address = fields.Many2one('res.partner', u'送货地址')
    supp_loc = fields.Many2one('stock.location', u'供应商库存', compute='_getStockLocations')
    tpl_loc = fields.Many2one('stock.location',  u'第三方库存', compute='_getStockLocations')
    tpl_wh = fields.Many2one('stock.location',  u'第三方库存', compute='_getStockLocations')
    supp_own_pick = fields.Boolean(u'供应商的拣货单', compute='_if_is_supp_picking', search='_get_supp_picking')
    transfer_applier = fields.Many2one('res.partner', u'调拨发起方',
                           default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    owner_id = fields.Many2one('res.partner', '所有者',
                               states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
                               default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id,
                               help="Default Owner")
    courrier_id = fields.Many2one('b2b.courrier', u'物流公司')

    @api.onchange('location_id')
    def onchange_location_id(self):
        if self.location_id:
            if self.location_id.location_id != self.env.ref('b2b_platform.stock_location_wh_suppliers'):
                for line in self.move_lines:
                    if line.thirdpl_stock < line.product_uom_qty:
                        raise UserError(u'第三方仓库库存不足，确定要从第三方仓库发货？')
                if self.carrier_id == self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier'):
                    self.carrier_id = False
            else:
                if not self.carrier_id:
                    self.carrier_id = self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier')

    @api.one
    def _if_is_supp_picking(self):
        partner = self.env.user.partner_id.parent_id or self.env.user.partner_id
        if self.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_suppliers') and self.owner_id == partner:
           self.supp_own_pick = True
        elif self.location_id.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_3pl') \
                and self.user_has_groups('b2b_platform.group_b2b_3pl_operator'):
            self.supp_own_pick = True
        elif self._context.get('b2b_action') == 'transfer':
            self.supp_own_pick = True

    def _get_supp_picking(self, operator, value):
        if self.user_has_groups('b2b_platform.group_qdoo_supplier_manager'):
            partner = self.env.user.partner_id
        else:
            partner = self.env.user.partner_id.parent_id
        supp_loc = self.env.ref('b2b_platform.stock_location_wh_suppliers')
        loc_ids = self.search([('location_id.location_id', '=', supp_loc.id),('owner_id', '=', partner.id)])
        return [('id','in',loc_ids.ids)]

    @api.one
    def _getStockLocations(self):
        supplier = self.owner_id
        stock_obj = self.env['stock.location'].sudo()
        self.supp_loc = stock_obj.search([('location_id', '=', self.env.ref('b2b_platform.stock_location_wh_suppliers').id),
                                         ('partner_id', '=', supplier.id)])
        self.tpl_loc = stock_obj.search([('location_id.location_id', '=', self.env.ref('b2b_platform.stock_location_wh_3pl').id),
                                         ('partner_id', '=', supplier.id)])
        self.tpl_wh = self.env.ref('b2b_platform.stock_location_wh_3pl')

    @api.multi
    def action_confirm(self):
        if self.picking_type_id.id == 1:
            if self.location_dest_id.location_id.location_id != self.env.ref('b2b_platform.stock_location_wh_3pl'):
                raise UserError(u'请选择第三方仓库的入库库位')
            if not self.move_lines:
                raise UserError(u'请填写产品明细')
        self.filtered(lambda picking: not picking.move_lines).write({'launch_pack_operations': True})
        # TDE CLEANME: use of launch pack operation, really useful ?
        self.mapped('move_lines').filtered(lambda move: move.state == 'draft').action_confirm()
        self.filtered(
            lambda picking: picking.location_id.usage in ('supplier', 'inventory', 'production')).force_assign()
        return True

    @api.multi
    def do_new_transfer(self):
        purchase_obj = self.env['purchase.order'].sudo()
        purchase_line_obj = self.env['purchase.order.line'].sudo()
        sale_obj = self.env['sale.order'].sudo()
        invoice_obj = self.env['account.invoice'].sudo()
        invoice_line_obj = self.env['account.invoice.line'].sudo()
        payment_obj = self.env['account.payment']
        pay_method_obj = self.env['account.payment.method']

        for pick in self:
            if pick.state == 'done':
                raise UserError(u'已出货完毕')
            if (not pick.carrier_id or not pick.carrier_tracking_ref) and self.picking_type_id.id != 1:
                raise UserError(u'请完善发货信息')
            pack_operations_delete = self.env['stock.pack.operation']
            if not pick.move_lines and not pick.pack_operation_ids:
                raise UserError(u'请填写初始需求')
            # In draft or with no pack operations edited yet, ask if we can just do everything
            if (pick.state == 'draft' or all([x.qty_done == 0.0 for x in pick.pack_operation_ids])) and self.picking_type_id.id != 1:
                raise UserError(u'请填写实际发货数量')
            if (pick.state == 'draft' or all([x.qty_done == 0.0 for x in pick.pack_operation_ids])) and self.picking_type_id.id == 1:
                raise UserError(u'请填写实际收货数量')
                # # If no lots when needed, raise error
                # picking_type = pick.picking_type_id
                # if (picking_type.use_create_lots or picking_type.use_existing_lots):
                #     for pack in pick.pack_operation_ids:
                #         if pack.product_id and pack.product_id.tracking != 'none':
                #             raise UserError(
                #                 'Some products require lots/serial numbers, so you need to specify those first!')
                # view = self.env.ref('stock.view_immediate_transfer')
                # wiz = self.env['stock.immediate.transfer'].create({'pick_id': pick.id})
                # # TDE FIXME: a return in a loop, what a good idea. Really.
                # return {
                #     'name': 'Immediate Transfer?',
                #     'type': 'ir.actions.act_window',
                #     'view_type': 'form',
                #     'view_mode': 'form',
                #     'res_model': 'stock.immediate.transfer',
                #     'views': [(view.id, 'form')],
                #     'view_id': view.id,
                #     'target': 'new',
                #     'res_id': wiz.id,
                #     'context': self.env.context,
                # }

            # Check backorder should check for other barcodes
            if pick.check_backorder():
                raise UserError(u'请先补货，更新库存数量后再发货')
                # raise UserError(u'确定需要补货？')
                # view = self.env.ref('stock.view_backorder_confirmation')
                # wiz = self.env['stock.backorder.confirmation'].create({'pick_id': pick.id})
                # # TDE FIXME: same reamrk as above actually
                # return {
                #     'name': 'Create Backorder?',
                #     'type': 'ir.actions.act_window',
                #     'view_type': 'form',
                #     'view_mode': 'form',
                #     'res_model': 'stock.backorder.confirmation',
                #     'views': [(view.id, 'form')],
                #     'view_id': view.id,
                #     'target': 'new',
                #     'res_id': wiz.id,
                #     'context': self.env.context,
                # }
            for operation in pick.pack_operation_ids:
                if operation.qty_done < 0:
                    raise UserError('No negative quantities allowed')
                if operation.qty_done > 0:
                    operation.write({'product_qty': operation.qty_done})
                else:
                    pack_operations_delete |= operation
            if pack_operations_delete:
                pack_operations_delete.unlink()
        self.sudo().do_transfer()

        # 以下为追加的内容，生成供应商发票
        ##################################################

        freight_obj = self.env['b2b.product.freight.line'].sudo()
        sale_obj = self.env['sale.order'].sudo()
        sale_line_obj = self.env['sale.order.line'].sudo()
        dest_country = self.ship_address.country_id
        freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')

        # 计算发货货值跟运费额
        delivered_amt = 0
        ship_charge = 0
        extra_ship_charge = 0
        for deliver_line in self.pack_operation_product_ids:
            sale_line = sale_line_obj.search([('product_id', '=', deliver_line.product_id.id),
                                          ('order_id', '=', sale_obj.search([('name','=',self.origin)]).id)],limit=1)
            delivered_amt += deliver_line.qty_done * sale_line.price_unit
            freight = freight_obj.search([('product_id', '=', deliver_line.product_id.product_tmpl_id.id),
                                          ('country_id', '=', dest_country.id)], limit=1)
            ship_charge += deliver_line.qty_done * freight.cny_amount
            # 如果不走采购，但又从第三方仓库发货，需补交运费
            if not sale_line.need_procure and self.location_id.location_id != self.env.ref('b2b_platform.stock_location_wh_suppliers'):
                extra_ship_charge += deliver_line.qty_done * freight.cny_amount

        sale = sale_obj.search([('name', '=', self.origin)])
        if sale and sale.fba_order:
            ship_charge = sale.fba_order.freight

        # 如有采购单，创建并确认供应商发票
        purchase = purchase_obj.search([('origin', '=', self.origin),
                                        ('partner_id', '=', self.owner_id.id),
                                        ('invoice_status', '!=', 'invoiced'),
                                        ('state', '=', 'purchase')])
        if len(purchase) > 1:
            raise UserError(u'检测到对应多张采购单，请核实')
        elif len(purchase) == 1:
            # 如果是第三方仓库或者平台发货，则采购中减去该项运费
            if self.location_id.location_id and \
                    (self.location_id.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_3pl')
                     or self.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_own')):
                purchase.amount_untaxed -= ship_charge
                purchase.amount_total -= ship_charge
                purchase_freight_line = purchase_line_obj.search(
                    [('order_id', '=', purchase.id), ('product_id', '=', freight_product.id)], limit=1)
                if purchase_freight_line:
                    purchase_freight_line.price_unit -= ship_charge
            # 创建供应商账单
            supplier_inv_id = invoice_obj.create({
                'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'purchase')],
                                                                        limit=1).id or 2,
                'type': 'in_invoice',
                'partner_id': self.owner_id.id,
                'reference': self.name,
                'purchase_id': purchase.id,
                'origin': self.name,
            })
            supplier_inv_id.purchase_order_change()
            supplier_inv_id.action_invoice_open()

        # 支付客户发票
        if sale:
            pay_method = pay_method_obj.sudo().search(
                [('code', '=', 'manual'), ('payment_type', '=', 'inbound')], limit=1)
            invoice = invoice_obj.search([('origin', '=', sale.name),('state','=','open')],limit=1)
            if invoice:
                # 需重新核算经销商发票中的运费金额
                if extra_ship_charge > 0:
                    invoice.amount_total_company_signed += extra_ship_charge
                    invoice.residual += extra_ship_charge
                    invoice.amount_untaxed += extra_ship_charge
                    invoice.residual_company_signed += extra_ship_charge
                    invoice.amount_total_signed += extra_ship_charge
                    invoice.residual_signed += extra_ship_charge
                    invoice.amount_total += extra_ship_charge
                    invoice.amount_untaxed_signed += extra_ship_charge
                    invoice_freight_line = invoice_line_obj.search([('invoice_id','=',invoice.id),('product_id','=',freight_product.id)],limit=1)
                    if invoice_freight_line:
                        invoice_freight_line.price_unit += extra_ship_charge
                        invoice_freight_line.price_subtotal += extra_ship_charge
                        invoice_freight_line.price_subtotal_signed += extra_ship_charge
                # 创建付款单据
                payment = payment_obj.create({
                    'invoice_ids': [(6, 0, [invoice.id])],
                    'payment_date': fields.Date.context_today(self),
                    'communication': invoice.number,
                    'journal_id': invoice.journal_id.id,
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'payment_method_id': pay_method.id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': invoice.partner_id.id,
                    'amount': delivered_amt + ship_charge,
                    'payment_difference_handling': 'open',
                })
                payment.post()

                if self.sudo().search([('origin','=',self.origin),('state','!=','done')]):
                    sale.write({'qdoo_state': 'part-deliver', 'act_deliver_date': datetime.now()})
                else:
                    sale.write({'qdoo_state': 'delivered', 'act_deliver_date': datetime.now()})
            # 如果没有客户发票，但又有运费，则创建一个新的客户发票
            elif ship_charge > 0 and self.location_id.location_id != self.env.ref('b2b_platform.stock_location_wh_suppliers'):
                cust_inv_obj = self.env['account.invoice'].sudo()
                cust_inv_line_obj = self.env['account.invoice.line'].sudo()
                ship_inv_id = cust_inv_obj.create({
                    'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'sale')],
                                                                            limit=1).id or 1,
                    'type': 'out_invoice',
                    'partner_id': self.partner_id.id,
                    'reference': self.origin,
                    'origin': self.origin,
                    'amount_total_company_signed': ship_charge,
                    'residual': ship_charge,
                    'amount_untaxed': ship_charge,
                    'residual_company_signed': ship_charge,
                    'amount_total_signed': ship_charge,
                    'residual_signed': ship_charge,
                    'amount_total': ship_charge,
                    'amount_untaxed_signed': ship_charge,
                    'state': 'draft',
                    'account_id': 4,
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'name': self.origin,
                    'commercial_partner_id': self.partner_id.id,
                    # 'partner_invoice_id': self.partner_invoice_id.id,
                    'partner_shipping_id': self.ship_address.id,
                })
                cust_inv_line_obj.create({
                    'origin': self.origin,
                    'price_unit': ship_charge,
                    'price_subtotal': ship_charge,
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'uom_id': 1,
                    'partner_id': self.partner_id.id,
                    'company_id': 1,
                    'account_id': 52,
                    'price_subtotal_signed': ship_charge,
                    'name': u'100% 的运费款',
                    'product_id': freight_product.id,
                    'invoice_id': ship_inv_id.id,
                    'quantity': 1,
                })
                ship_inv_id.action_invoice_open()

                # 创建付款单据
                payment = payment_obj.create({
                    'invoice_ids': [(6, 0, [ship_inv_id.id])],
                    'payment_date': fields.Date.context_today(self),
                    'communication': ship_inv_id.number,
                    'journal_id': ship_inv_id.journal_id.id,
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'payment_method_id': pay_method.id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': ship_inv_id.partner_id.id,
                    'amount': ship_charge,
                    'payment_difference_handling': 'open',
                })
                payment.post()

                if self.sudo().search([('origin', '=', self.origin), ('state', '!=', 'done')]):
                    sale.write({'qdoo_state': 'part-deliver', 'act_deliver_date': datetime.now()})
                else:
                    sale.write({'qdoo_state': 'delivered', 'act_deliver_date': datetime.now()})

            if sale.order_line:
                sale.order_line.write({'invoice_status': 'invoiced'})
            sale.write({'invoice_status': 'invoiced'})

        # 如果是从第三方仓库、或者平台自有库存发货、或者FBA补货非供应商代发，则生成运费账单
        if self.location_id.location_id and \
                (self.location_id.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_3pl')
                 or self.location_id.location_id == self.env.ref('b2b_platform.stock_location_wh_own')) \
                 or (sale.fba_order and sale.fba_order.carrier_id != self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier')):
            if not self.sudo().carrier_id.partner_id:
                raise UserError(u'承运商没有对应的业务伙伴，不能生成承运商运费账单')
            else:
                carrier = self.sudo().carrier_id.partner_id
            carrier_inv_id = invoice_obj.create({
                        'journal_id': self.env['account.journal'].sudo().search([('type', '=', 'purchase')],
                                                                                limit=1).id or 2,
                        'type': 'in_invoice',
                        'partner_id': carrier.id,
                        'reference': self.name,
                        'origin': self.name,
                        'amount_total': ship_charge,
                        })
            carrier_inv_id.invoice_line_ids.create({
                        'invoice_id': carrier_inv_id.id,
                        'origin': self.origin,
                        'price_unit': ship_charge,
                        'price_subtotal': ship_charge,
                        'currency_id': self.env.user.company_id.currency_id.id,
                        'uom_id': 1,
                        'partner_id': carrier.id,
                        'company_id': self.env.user.company_id.id,
                        'account_id': self.env['account.account'].sudo().search([('name', '=', u'材料采购')],
                                                                                limit=1).id or 9,
                        'price_subtotal_signed': ship_charge,
                        'name': u'运费',
                        'product_id': freight_product.id,
                        'quantity': 1,
                    })
            carrier_inv_id.action_invoice_open()
        #######################################################

        return


class B2bStockMove(models.Model):
    _inherit = "stock.move"

    supplier_stock = fields.Float(u'经销商库存', related='product_id.supplier_stock')
    thirdpl_stock = fields.Float(u'3PL库存', related='product_id.thirdpl_stock')
    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=lambda self: ['|',('product_owner','=',self.env.user.partner_id.parent_id.id),
                             ('product_owner','=',self.env.user.partner_id.id),
                             ('master_product', '=', False),
                             ('type', 'in', ['product', 'consu'])],
        index=True, required=True,
        states={'done': [('readonly', True)]})

class B2bStockQuant(models.Model):
    _inherit = "stock.quant"

    my_locations = fields.Boolean(u'我的库位', compute="_get_my_locations", search='_get_my_locations')

    def _get_my_locations(self,operator,value):
        if self.user_has_groups('b2b_platform.group_qdoo_supplier_warehouse,b2b_platform.group_qdoo_supplier_manager'):
            locs = self.env['stock.location'].search([('location_id','=',self.env.ref('b2b_platform.stock_location_wh_suppliers').id),
                                      ('partner_id','=',self.env.user.partner_id.parent_id.id or self.env.user.partner_id.id)])
        elif self.user_has_groups('b2b_platform.group_b2b_3pl_operator'):
            locs = self.env['stock.location'].search([('location_id.location_id','=',self.env.ref('b2b_platform.stock_location_wh_3pl').id)])
        else:
            locs = False
        return [('location_id','child_of', locs.ids)]

class B2bDeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    partner_id = fields.Many2one('res.partner', u'承运商', required=True)

    @api.multi
    def write(self, vals):
        res = super(B2bDeliveryCarrier, self).write(vals)
        self.create_price_rules()
        # 以下为新加内容
        ###################################################
        self.product_id.product_tmpl_id.write({'type':'service'})
        ###################################################
        return res

    @api.model
    def create(self, vals):
        res = super(B2bDeliveryCarrier, self).create(vals)
        res.create_price_rules()
        # 以下为新加内容
        ###################################################
        res.product_id.product_tmpl_id.write({'type': 'service'})
        ###################################################
        return res

class B2bCourrierCompany(models.Model):
    _name = "b2b.courrier"
    _rec_name = 'courrier'

    courrier = fields.Char(u'物流公司', required=True)
    code = fields.Char(u'编码', readonly=True)
    partner = fields.Many2one(u'res.partner', u'归属',
                      default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)

    @api.model
    def create(self, vals):
        res = super(B2bCourrierCompany, self).create(vals)
        res.write({'code':self.env['ir.sequence'].next_by_code('b2b.courrier.code')})
        if self.user_has_groups('b2b_platform.group_qdoo_platform_operator'):
            res.write({'partner': False})
        return res

