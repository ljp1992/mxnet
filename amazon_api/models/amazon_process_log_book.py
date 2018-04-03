# -*- encoding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
class AmazonProcessLogBook(models.Model):
    _inherit = 'amazon.process.log.book'

    #同步产品时，可以根据这两个字段找到对应的日志
    res_model = fields.Many2one('ir.model', help=u'哪个模型产生的日志')
    res_id = fields.Integer(help=u'对应res_model中哪条记录')
    over_time = fields.Datetime(string=u'结束时间')

    @api.multi
    def create_log_qdodoo(self, val):
        '''创建日志'''
        res_model = False
        if val.get('model_name'):
            model = self.env['ir.model'].search([('model', '=', val.get('model_name'))])
            if not model:
                raise UserError(u'模型%不存在' % val.get('model_name'))
            else:
                res_model = model.id
        log = self.create({
            'res_model': res_model,
            'res_id': val.get('res_id', False),
            'application': val.get('application', ''),
            'instance_id': val.get('instance_id', False),
            'operation_type': val.get('operation_type', ''),
            'message': val.get('message', ''),
        })
        return log
