# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError

class AmazonTransactionLog(models.Model):
    _inherit = 'amazon.transaction.log'

    @api.multi
    def create_log_line_qdodoo(self, val):
        '''添加日志信息'''
        job_id = val.get('job_id')
        if not job_id:
            raise UserError(u'job_id不能为空')
        model_id = val.get('model_id', False)
        if not model_id:
            model_id = self.env['amazon.process.log.book'].browse(job_id).res_model.id or False
        self.create({
            'model_id': model_id,
            'res_id': val.get('res_id', False),
            'job_id': job_id,
            'log_type': val.get('log_type', ''),
            'action_type': val.get('action_type', ''),
            'user_id': self.env.user.id,
            'message': val.get('message', ''),
        })

