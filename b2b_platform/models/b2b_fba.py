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

class b2b_fba_procure(models.Model):
    _name = 'b2b.fba.rfq'
    _description = "FRQ for FBA purchases"
    _order = 'id desc'

    state = fields.Selection([('draft', u'新建'), ('supplier', u'供应商确认'), ('freight', u'平台运费'), ('accept', u'经销商确认'),
                                   ('done', u'完成'), ('cancel', u'取消')],
                                  u'状态', default='draft')
    name = fields.Char(u'FBA补货单号')
    distributor = fields.Many2one('res.partner', u'经销商', required=True,
                                default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    supplier = fields.Many2one('res.partner', u'供应商', required=True)
    carrier_id = fields.Many2one('delivery.carrier', u'承运方', required=True)
    shop_id = fields.Many2one('res.partner', u'店铺', domain="[('type','=','shop')]", required=True)
    method = fields.Selection([('sea', u'海运'), ('air', u'空运'), ('currier', u'特快'), ('post', u'平邮')],u'运输方式', required=True)
    dest_country = fields.Many2one('res.country', u'发往国家', required=True)
    freight = fields.Float(u'运费(元)',digits=(16,2))
    note = fields.Text(u'备注')
    order_line = fields.One2many('b2b.fba.rfq.line','order_id',u'订单明细')
    so_id = fields.Many2one('sale.order',u'订单')
    demand_qty_ttl = fields.Float(u'需求数量', compute='_get_totals')
    supply_qty_ttl = fields.Float(u'补货数量', compute='_get_totals')
    dist_orders = fields.Boolean(u'本经销商的订单', compute='_if_dist_orders', search='_get_dist_orders')
    supp_orders = fields.Boolean(u'本供应商的订单', compute='_if_supp_orders', search='_get_supp_orders')

    @api.one
    def _if_dist_orders(self):
        dist = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.dist_orders = True if self.distributor == dist else False

    def _get_dist_orders(self, operator, value):
        dist = self.env.user.partner_id.parent_id or self.env.user.partner_id
        orders = self.search([('distributor', '=', dist.id)])
        return [('id', 'in', orders.ids)]

    @api.one
    def _if_supp_orders(self):
        supp = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.supp_orders = True if self.supplier == supp else False

    def _get_supp_orders(self, operator, value):
        supp = self.env.user.partner_id.parent_id or self.env.user.partner_id
        orders = self.search([('supplier', '=', supp.id)])
        return [('id', 'in', orders.ids)]

    @api.one
    def _get_totals(self):
        demand = 0
        supply = 0
        for line in self.order_line:
            demand += line.demand_qty
            supply += line.qty
        self.demand_qty_ttl = demand
        self.supply_qty_ttl = supply

    @api.one
    def btn_notice(self):
        if self.state != 'draft':
            raise UserError(u'单据已提交，请刷新页面更新流转状态。')
        if self.demand_qty_ttl <=0:
            raise UserError(u'请填写有效需求数量。')
        if not self.name:
            name = self.env['ir.sequence'].next_by_code('b2b.fba.rfq')
        else:
            name = self.name
        return self.write({'name': name, 'state': 'supplier'})

    def btn_confirm(self):
        if self.state != 'supplier':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        if self.supply_qty_ttl <=0:
            raise UserError(u'请填写有效补货数量。')

        # sup_carrier_id = self.env['delivery.carrier'].sudo().search([('name', 'ilike', u'供应商')], limit=1).id
        sup_carrier_id = self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier').id
        if not sup_carrier_id:
            raise UserError(u'未找到供应商代发货的运输方式')
        if self.carrier_id.id != sup_carrier_id:
            return self.write({'state': 'freight'})
        else:
            return self.write({'state': 'accept'})

    def btn_reject(self):
        if self.state != 'supplier':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state': 'draft'})

    @api.one
    def btn_freight(self):
        if self.state != 'freight':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state': 'accept'})

    def btn_freight_reject(self):
        if self.state != 'freight':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state': 'supplier'})

    @api.one
    def btn_accept(self):
        if self.state != 'accept':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')

        so_obj = self.env['sale.order']
        list = []
        for line in self.order_line:
            # dr_ship = self.env['stock.location.route'].sudo().search([('name', '=', u'直运')])
            # if not dr_ship:
            #     raise UserError(u'未找到直运的补货路线，请咨询平台管理人员')
            list.append([0,0,{
                             'product_uom': line.master_product.uom_id.id,
                             'price_unit':line.dist_price_unit,
                             'product_uom_qty':line.qty,
                             'currency_id': self.env.user.company_id.currency_id.id,
                             'company_id': self.env.user.company_id.id,
                             'state':'draft',
                             'order_partner_id': self.distributor.id,
                             'product_id': line.master_product.id,
                             'shop_product': line.shop_product.id,
                             # 'route_id':dr_ship.id,
                             'is_delivery': False,
                             }])
        if self.freight:
            freight_product = self.env.ref('b2b_platform.default_b2b_delivery_carrier')
            list.append([0, 0, {
                            'product_uom': freight_product.uom_id.id,
                            'price_unit': self.freight,
                            'product_uom_qty': 1,
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'company_id': self.env.user.company_id.id,
                            'state': 'draft',
                            'order_partner_id': self.distributor.id,
                            'product_id':freight_product.id,
                            'is_delivery': True,
                        }])
        so_id = so_obj.create({'date_order':fields.Datetime.now(),
                                'partner_id':self.distributor.id,
                                'partner_invoice_id':self.distributor.id,
                                'partner_shipping_id':self.shop_id.id,
                                'company_id':self.env.user.company_id.id,
                                'state':'draft',
                                'payment_term_id':1,
                                'picking_policy':'one',
                                'warehouse_id':1,
                                'carrier_id':self.carrier_id.id,
                                'delivery_price':self.freight,
                                # 'supplier':self.supplier.id,
                                'shop_id':self.shop_id.id,
                                'advance_payment_method':'percentage',
                                'fba_order':self.id,
                                'order_line':list,
                                })
        so_id.btn_platform()
        return self.write({'state': 'done', 'so_id':so_id.id})

    def btn_accept_reject(self):
        if self.state != 'accept':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')

        # sup_carrier_id = self.env['delivery.carrier'].sudo().search([('name', 'ilike', u'供应商')], limit=1).id
        sup_carrier_id = self.env.ref('b2b_platform.b2b_supplier_as_delivery_carrier').id
        if not sup_carrier_id:
            raise UserError(u'未找到供应商代发货的运输方式')
        if self.carrier_id.id != sup_carrier_id:
            return self.write({'state': 'freight'})
        else:
            return self.write({'state': 'supplier'})

    # 只能删除新建或删除的订单
    @api.multi
    def unlink(self):
        for ids in self:
            if ids.state != 'draft':
                raise osv.except_osv("已提交申请的凭证不能删除！")
        return super(b2b_fba_procure, self).unlink()


class b2b_fba_procure_line(models.Model):
    _name = 'b2b.fba.rfq.line'

    order_id = fields.Many2one(u'b2b.fba.rfq', u'订单号', ondelete='cascade')
    shop_product = fields.Many2one('product.product', string=u'商品', domain=[('sale_ok', '=', True)],
                                   change_default=True, ondelete='restrict', required=True)
    master_product = fields.Many2one('product.product', related='shop_product.master_product',readonly=True)
    demand_qty = fields.Float(u'需求数量',digits=(16,3))
    qty = fields.Float(u'补货数量',digits=(16,3))
    uom = fields.Many2one('product.uom', u'单位', related='master_product.uom_id', readonly=True)
    dist_price_unit = fields.Float(u'采购单价(元)', related='shop_product.standard_price', readonly=True)
    supp_price_unit = fields.Float(u'供货单价(元)',related='master_product.dist_price',readonly=True)
    dist_amt = fields.Float(u'金额(元)', digits=(16, 2), compute='_get_total_amt')
    supp_amt = fields.Float(u'金额(元)',digits=(16,2),compute='_get_total_amt')
    state = fields.Selection(related='order_id.state',default='draft')

    @api.multi
    def _get_total_amt(self):
        for line in self:
            if line.order_id.state == 'draft':
                line.supp_amt = line.demand_qty * line.supp_price_unit
                line.dist_amt = line.demand_qty * line.dist_price_unit
            else:
                line.supp_amt = line.qty * line.supp_price_unit
                line.dist_amt = line.qty * line.dist_price_unit






