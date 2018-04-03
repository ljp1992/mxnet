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
from datetime import datetime
from odoo.exceptions import ValidationError, UserError

class b2b_payment_deposit(models.Model):
    _name = 'b2b.payment.deposit'
    _description = "deposit from distributors"
    _order = 'id desc'


    state = fields.Selection([('draft',u'新建'),('notice',u'通知'),('done',u'已确认'),('cancel',u'已取消')], string=u'状态', default='draft')
    name = fields.Char(u'充值单号')

    applicant = fields.Many2one('res.partner',u'经销商',required=True,default=lambda self: self.env.user.partner_id.parent_id or self.env.user.partner_id)
    bank = fields.Many2one('res.bank',u'银行',required=True)
    account_journal_id = fields.Many2one('account.journal', string=u'银行账号')
    # account_journal_id = fields.Many2one('account.journal', domain=[('bank_id', '=', bank.id)], string=u'银行账号')

    amount = fields.Float(u'打款金额', digits=(16,2),required=True)
    deposit_avail_amt = fields.Float(u'预付款可用余额', related='applicant.deposit_avail_amt')
    date = fields.Date(u'打款日期',required=True)
    proof = fields.Binary(u'付款凭证',required=True)
    file_name = fields.Char(u'文件名')
    note = fields.Text(u'备注')

    @api.one
    def btn_notice(self):
        if self.state != 'draft':
            raise UserError(u'单据已提交，请刷新页面更新流转状态。')
        if self.amount <= 0:
            raise UserError(u'提现金额无效')
        name = self.env['ir.sequence'].next_by_code('qdoo.payment.deposit')
        return self.write({'name':name, 'state':'notice'})

    @api.one
    def btn_done(self):
        if self.state != 'notice':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        # 创建会计凭证
        account_obj = self.env['account.account'].sudo()
        move_obj = self.env['account.move'].sudo()
        move_line_obj = self.env['account.move.line'].sudo()
        journal_id = self.env.ref('b2b_platform.account_journal_data_deposit').id
        currency_id = self.env.user.company_id.currency_id.id
        user_type_id = self.env.ref('account.data_account_type_revenue'),
        move = move_obj.create({'ref':self.name,
                                'compamy_id':self.env.user.company_id.id,
                                'amount':self.amount,
                                'journal_id':journal_id,
                                'currency_id':currency_id,
                                'state':'draft',
                                'date':self.date,
                                'partner_id':self.applicant.id
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
              % (journal_id, currency_id, self.date, self.applicant.id, 3,
                 0, self.amount, self.name, account_obj.search([('code','=','10021')],limit=1).id, self.amount,
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
              % (journal_id, currency_id, self.date, self.applicant.id, 1,
                 self.amount, 0, self.name, account_obj.search([('code', '=', '1122')], limit=1).id, 0,
                 self.date, move.id, currency_id, self.name, self.amount,
                 self.amount * -1.0, self.amount * -1.0, self.amount * -1.0, datetime.today(),
                 False, self.env.uid, 1, True, 0)
        self._cr.execute(sql)
        move.post()
        move.write({'amount':self.amount, 'partner_id':self.applicant.id})
        return self.write({'state':'done'})

    @api.one
    def btn_cancel(self):
        if self.state != 'notice':
            raise UserError(u'单据已处理，请刷新页面更新流转状态。')
        return self.write({'state': 'cancel'})

    # 只能删除未完成的订单
    @api.multi
    def unlink(self):
        for ids in self:
            if ids.state in ('notice','done'):
                raise osv.except_osv("已提交申请的凭证不能删除！")
        return super(b2b_payment_deposit, self).unlink()





