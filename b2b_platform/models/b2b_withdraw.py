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

class b2b_supplier_withdraw(models.Model):
    _name = 'b2b.supplier.withdraw'
    _description = "supplier withdraw money from platform"
    _order = 'id desc'


    state = fields.Selection([('draft',u'新建'),('confirm',u'平台确认'),('accept',u'到账确认'),
                              ('done',u'完成'), ('cancel',u'已取消')], string=u'状态', default='draft')
    name = fields.Char(u'提现单号')
    supplier = fields.Many2one('res.partner',u'供应商',required=True,default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    bank = fields.Many2one('b2b.supplier.bank', u'银行')
    account = fields.Char(u'银行账号', related='bank.account', readyonly=True)
    benificiary = fields.Char(u'账号户头', related='bank.benificiary', readyonly=True)
    withdrawable = fields.Float(u'可提现金额', digits=(16,2), related='supplier.withdraw_balance', readonly=True)
    amount = fields.Float(u'提现金额', digits=(16,2))
    date = fields.Date(u'转账日期')
    proof = fields.Binary(u'付款凭证')
    file_name = fields.Char(u'文件名')
    note = fields.Text(u'备注')
    supp_orders = fields.Boolean(u'本供应商的订单', compute='_if_supp_orders')

    @api.one
    def _if_supp_orders(self):
        supp = self.env.user.partner_id.parent_id or self.env.user.partner_id
        self.supp_orders = True if self.supplier == supp else False

    @api.one
    def btn_notice(self):
        if self.state != 'draft':
            raise UserError(u'单据已提交，请刷新页面更新流转状态。')
        if self.amount <= 0:
            raise UserError(u'提现金额无效')
        if self.amount > self.withdrawable:
            raise UserError(u'提现金额超可提现金额，请修改')
        name = self.env['ir.sequence'].next_by_code('qdoo.supplier.withdraw')
        return self.write({'name':name, 'state':'confirm'})

    def btn_confirm(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        if not self.date or not self.proof:
            raise UserError(u'请填入转账日期和打款凭证')
        return self.write({'state':'accept'})

    def btn_reject(self):
        if self.state != 'confirm':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state':'draft'})

    @api.one
    def btn_accept(self):
        if self.state != 'accept':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')

        account_obj = self.env['account.account'].sudo()
        account_id = account_obj.search([('name', '=', u'商户提现')], limit=1).id
        bank_account_id = account_obj.search([('name', '=', u'银行')], limit=1).id
        move_obj = self.env['account.move'].sudo()
        journal_id = self.env.ref('b2b_platform.account_journal_data_supplier').id
        currency_id = self.env.user.company_id.currency_id.id

        # 转供应商提现账户
        move = move_obj.create({'ref': self.name,
                                'compamy_id': self.env.user.company_id.id,
                                'amount': self.amount,
                                'journal_id': journal_id,
                                'currency_id': currency_id,
                                'state': 'draft',
                                'date': self.date,
                                'partner_id': self.supplier.id
                                })
        # 借预付账款
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
              % (journal_id, currency_id, self.date, self.supplier.id, 3,
                 0, self.amount, self.name, account_id, self.amount,
                 self.date, move.id, currency_id, self.name, 0,
                 self.amount, self.amount, 0, datetime.today(),
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
              % (journal_id, currency_id, self.date, self.supplier.id, 1,
                 self.amount, 0, self.name, bank_account_id, 0,
                 self.date, move.id, currency_id, self.name, self.amount,
                 self.amount * -1.0, self.amount * -1.0, self.amount * -1.0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        move.post()
        move.write({'amount': self.amount, 'partner_id': self.supplier.id})

        return self.write({'state':'done'})


    # 只能删除新建或删除的订单
    @api.multi
    def unlink(self):
        for ids in self:
            if ids.state in ('confirm','accept','done'):
                raise osv.except_osv("已提交申请的凭证不能删除！")
        return super(b2b_supplier_withdraw, self).unlink()


class b2b_supplier_bank(models.Model):
    _name = 'b2b.supplier.bank'
    _description = "supplier bank accounts"

    supplier = fields.Many2one('res.partner', u'供应商', required=True,
               default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id, readonly=True)
    name = fields.Char(u'开户行')
    benificiary = fields.Char(u'账号户头')
    account = fields.Char(u'银行账号')






