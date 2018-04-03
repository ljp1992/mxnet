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

class b2b_purchase_settlement(models.Model):
    _name = 'b2b.purchase.settlement'
    _description = "settle payment with suppliers"
    _order = 'id desc'


    state = fields.Selection([('draft',u'新建'),('confirm',u'供应商确认'),('transfer',u'支付账单'),
                              ('done',u'完成'), ('cancel',u'已取消')], string=u'状态', default='draft')
    name = fields.Char(u'结算单号')
    supplier = fields.Many2one('res.partner',u'供应商',required=True)
    amount = fields.Float(u'总金额', digits=(16,2), compute='_get_total_amount')
    date = fields.Date(u'账单截止日',required=True)
    note = fields.Text(u'备注')
    order_line = fields.One2many('b2b.purchase.settlement.line', 'order_id', u'明细')
    supp_orders = fields.Boolean(u'本供应商的订单', compute='_if_supp_orders')

    @api.one
    def _if_supp_orders(self):
        supp = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.supp_orders = True if self.supplier == supp else False

    @api.onchange('supplier')
    def _onchange_supplier(self):
        self.order_line = ''
        bill_obj = self.env['account.invoice'].sudo()
        order_line = []
        if self.supplier:
            bills = bill_obj.search([('partner_id','=',self.supplier.id),('residual','>',0),('state','=','open'),('type','=','in_invoice')])
            if bills:
                for bill in bills:
                    order_line.append((0,0,{'bill':bill.id}))
            self.order_line = order_line

    @api.onchange('date')
    def _onchange_date(self):
        if self.date:
            bill_obj = self.env['account.invoice'].sudo()
            self.order_line = ''
            order_line = []
            end_date = (datetime.strptime(self.date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

            bills = bill_obj.search(
                [('partner_id', '=', self.supplier.id), ('residual', '>', 0), ('state', '=', 'open'),
                 ('type', '=', 'in_invoice'), ('date_invoice', '<', end_date)])
            if bills:
                for bill in bills:
                    order_line.append((0, 0, {'bill': bill.id}))
            self.order_line = order_line

    @api.one
    def _get_total_amount(self):
        amount = 0
        for line in self.order_line:
            amount += line.amount_total_signed
        self.amount = amount

    @api.one
    def btn_notice(self):
        if self.state != 'draft':
            raise UserError(u'单据已提交，请刷新页面更新流转状态。')
        name = self.env['ir.sequence'].next_by_code('qdoo.purchase.settle')
        return self.write({'name':name, 'state':'confirm'})

    def btn_accept(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state':'transfer'})

    def btn_reject(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state':'draft'})

    @api.one
    def btn_transfer(self):
        if self.state != 'transfer':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        payment_obj = self.env['account.payment']
        pay_method_obj = self.env['account.payment.method'].sudo()
        pay_method = pay_method_obj.search([('code', '=', 'manual'), ('payment_type', '=', 'outbound')], limit=1) or 2

        journal_id = self.env.ref('b2b_platform.account_journal_data_supplier').id
        currency_id = self.env.user.company_id.currency_id.id

        if self.order_line:
            for line in self.order_line:
                payment = payment_obj.create({
                    'invoice_ids': [(6, 0, [line.bill.id])],
                    'payment_date': fields.Date.context_today(self),
                    'communication': self.name,
                    'journal_id': journal_id,
                    'currency_id': currency_id,
                    'payment_method_id': pay_method.id,
                    'payment_type': 'outbound',
                    'partner_type': 'supplier',
                    'partner_id': self.supplier.id,
                    'amount': line.residual_signed,
                    'payment_difference_handling': 'open',
                })
                payment.post()

        return self.write({'state':'done'})


    # 只能删除新建或删除的订单
    @api.multi
    def unlink(self):
        for ids in self:
            if ids.state in ('confirm','transfer','done'):
                raise osv.except_osv("已提交申请的凭证不能删除！")
        return super(b2b_purchase_settlement, self).unlink()


class b2b_purchase_settlement_line(models.Model):
    _name = 'b2b.purchase.settlement.line'

    order_id = fields.Many2one('b2b.purchase.settlement', u'结算单')
    bill = fields.Many2one('account.invoice', u'凭证号')
    bill_date = fields.Date(related='bill.date_invoice', readonly=True)
    reference = fields.Char(related='bill.reference', readonly=True)
    origin = fields.Char(related='bill.origin', readonly=True)
    amount_total_signed = fields.Monetary(related='bill.amount_total_signed', readonly=True)
    currency_id = fields.Many2one('res.currency', u'币种')
    residual_signed = fields.Monetary(related='bill.residual_signed', readonly=True)
    state = fields.Selection(related='bill.state', readonly=True)





