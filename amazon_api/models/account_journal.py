# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.multi
    def name_get(self):
        result = super(AccountJournal, self).name_get()
        if self._context.get('customize_name'):
            result = []
            for account in self:
                result.append((account.id, account.bank_acc_number))
        return result