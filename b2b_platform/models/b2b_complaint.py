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

class b2b_customer_complaint(models.Model):
    _name = 'b2b.customer.complaint'
    _description = "complaint and reverse payment"
    _order = 'id desc'

    state = fields.Selection([('draft', u'新建'), ('confirm', u'供应商确认'), ('accept', u'平台返款'),
                              ('done', u'完成'), ('reject', u'拒绝')], string=u'状态', default='draft')
    name = fields.Char(u'申诉单号')
    date = fields.Date(u'申诉日期',required=True, default=lambda self:fields.date.today())
    applicant = fields.Many2one('res.partner', u'经销商', required=True,
                               default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    supplier = fields.Many2one('res.partner', u'供应商', required=True)
    sale_order = fields.Many2one('sale.order', u'销售单')
    purchase_order = fields.Many2one('purchase.order', u'采购单')
    picking_order = fields.Many2one('stock.picking', u'发货单')
    request_amt = fields.Float(u'申请退款金额', digits=(16,2))
    confirm_amt = fields.Float(u'同意退款金额', digits=(16,2))
    complaint = fields.Html(u'申诉内容')
    feedback = fields.Html(u'答复')
    note = fields.Html(u'平台备注')
    supp_orders = fields.Boolean(u'本供应商的订单', compute='_if_supp_orders')

    @api.one
    def _if_supp_orders(self):
        supp = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.supp_orders = True if self.supplier == supp else False

    @api.onchange('sale_order')
    def _onchange_sale_order(self):
        po_picking = False
        po = self.env['purchase.order'].search([('origin','=',self.sale_order.name)],limit=1)
        if po:
            self.purchase_order = po
        so_picking = self.env['stock.picking'].search([('origin','=',self.sale_order.name)],limit=1)
        if not so_picking and po:
            po_picking = self.env['stock.picking'].search([('origin','=',po.name)],limit=1)
        self.picking_order = po_picking or so_picking or False

    # 只能删除新建或删除的订单
    @api.multi
    def unlink(self):
        for ids in self:
            if ids.state in ('confirm', 'accept', 'done'):
                raise osv.except_osv("已提交申请的凭证不能删除！")
        return super(b2b_customer_complaint, self).unlink()

    @api.one
    def btn_notice(self):
        if self.state != 'draft':
            raise UserError(u'单据已提交，请刷新页面更新流转状态。')
        if self.request_amt <= 0:
            raise UserError(u'申请退款金额无效')
        if self.sale_order:
            self.sale_order.write({'qdoo_state':'complaint'})
        name = self.env['ir.sequence'].next_by_code('b2b.customer.complaint')
        return self.write({'name':name, 'state':'confirm'})

    def btn_confirm(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        if self.confirm_amt <= 0:
            raise UserError(u'请输入同意退款的金额')
        return self.write({'state':'accept'})

    def btn_confirm_2_draft(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state':'draft'})

    def btn_reject(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        if self.sale_order:
            self.sale_order.write({'qdoo_state':'rejected'})
        return self.write({'state':'reject'})

    def btn_accept_2_confirm(self):
        if self.state != 'accept':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state':'confirm'})

    @api.one
    def btn_accept(self):
        if self.state != 'accept':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')

        account_obj = self.env['account.account'].sudo()
        move_obj = self.env['account.move'].sudo()
        move_line_obj = self.env['account.move.line'].sudo()
        journal_id = self.env.ref('b2b_platform.account_journal_data_deposit').id
        journal_id2 = self.env.ref('b2b_platform.account_journal_data_supplier').id
        currency_id = self.env.user.company_id.currency_id.id
        account_id = account_obj.search([('name', '=', u'供应商账户')], limit=1).id
        bank_account_id = account_obj.search([('name', '=', u'银行')], limit=1).id

        ## 经销商退款，贷应收
        move = move_obj.create({'ref': self.name,
                                'compamy_id': self.env.user.company_id.id,
                                'amount': self.confirm_amt,
                                'journal_id': journal_id,
                                'currency_id': currency_id,
                                'state': 'draft',
                                'date': self.date,
                                'partner_id': self.applicant.id
                                })
        sql = "INSERT INTO account_move_line " \
              "(journal_id, currency_id, date_maturity, partner_id, user_type_id, " \
              "credit_cash_basis, debit, ref, account_id, debit_cash_basis, " \
              "date, move_id, company_currency_id, name, credit, " \
              "balance_cash_basis, balance, amount_residual, create_date, " \
              "blocked, create_uid, company_id, tax_exigible, amount_currency) " \
              "VALUES (%s, %s, '%s', %s, %s, " \
              "%s, %s, '%s', %s, %s, " \
              "'%s', %s, %s, '%s', %s, " \
              "%s, %s, %s, '%s', " \
              "%s, %s, %s, %s, %s);" \
              % (journal_id, currency_id, self.date, self.applicant.id, 3,
                 0, self.confirm_amt, self.name, account_obj.search([('code', '=', '1122')], limit=1).id, self.confirm_amt,
                 self.date, move.id, currency_id, self.name, 0,
                 self.confirm_amt, self.confirm_amt, 0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        sql = "INSERT INTO account_move_line " \
              "(journal_id, currency_id, date_maturity, partner_id, user_type_id, " \
              "credit_cash_basis, debit, ref, account_id, debit_cash_basis, " \
              "date, move_id, company_currency_id, name, credit, " \
              "balance_cash_basis, balance, amount_residual, create_date, " \
              "blocked, create_uid, company_id, tax_exigible, amount_currency) " \
              "VALUES (%s, %s, '%s', %s, %s, " \
              "%s, %s, '%s', %s, %s, " \
              "'%s', %s, %s, '%s', %s, " \
              "%s, %s, %s, '%s', " \
              "%s, %s, %s, %s, %s);" \
              % (journal_id, currency_id, self.date, self.applicant.id, 1,
                 self.confirm_amt, 0, self.name, account_obj.search([('code', '=', '5001')], limit=1).id, 0,
                 self.date, move.id, currency_id, self.name, self.confirm_amt,
                 self.confirm_amt * -1.0, self.confirm_amt * -1.0, self.confirm_amt * -1.0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        move.post()
        move.write({'amount': self.confirm_amt, 'partner_id': self.applicant.id})


        # 供应商应付款
        move = move_obj.create({'ref': self.name,
                                'compamy_id': self.env.user.company_id.id,
                                'amount': self.confirm_amt,
                                'journal_id': journal_id2,
                                'currency_id': currency_id,
                                'state': 'draft',
                                'date': self.date,
                                'partner_id': self.supplier.id
                                })
        sql = "INSERT INTO account_move_line " \
              "(journal_id, currency_id, date_maturity, partner_id, user_type_id, " \
              "credit_cash_basis, debit, ref, account_id, debit_cash_basis, " \
              "date, move_id, company_currency_id, name, credit, " \
              "balance_cash_basis, balance, amount_residual, create_date, " \
              "blocked, create_uid, company_id, tax_exigible, amount_currency) " \
              "VALUES (%s, %s, '%s', %s, %s, " \
              "%s, %s, '%s', %s, %s, " \
              "'%s', %s, %s, '%s', %s, " \
              "%s, %s, %s, '%s', " \
              "%s, %s, %s, %s, %s);" \
              % (journal_id2, currency_id, self.date, self.supplier.id, 3,
                 0, self.confirm_amt, self.name, self.env.ref('b2b_platform.account_journal_data_supplier').id, self.confirm_amt,
                 self.date, move.id, currency_id, self.name, 0,
                 self.confirm_amt, self.confirm_amt, 0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        sql = "INSERT INTO account_move_line " \
              "(journal_id, currency_id, date_maturity, partner_id, user_type_id, " \
              "credit_cash_basis, debit, ref, account_id, debit_cash_basis, " \
              "date, move_id, company_currency_id, name, credit, " \
              "balance_cash_basis, balance, amount_residual, create_date, " \
              "blocked, create_uid, company_id, tax_exigible, amount_currency) " \
              "VALUES (%s, %s, '%s', %s, %s, " \
              "%s, %s, '%s', %s, %s, " \
              "'%s', %s, %s, '%s', %s, " \
              "%s, %s, %s, '%s', " \
              "%s, %s, %s, %s, %s);" \
              % (journal_id2, currency_id, self.date, self.supplier.id, 1,
                 self.confirm_amt, 0, self.name, account_obj.search([('name', '=', u'银行')], limit=1).id, 0,
                 self.date, move.id, currency_id, self.name, self.confirm_amt,
                 self.confirm_amt * -1.0, self.confirm_amt * -1.0, self.confirm_amt * -1.0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        move.post()
        move.write({'amount': self.confirm_amt, 'partner_id':self.supplier.id})

        if self.sale_order:
            self.sale_order.write({'qdoo_state':'accepted'})

        return self.write({'state': 'done'})