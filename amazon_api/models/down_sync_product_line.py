# -*- coding: utf-8 -*-

from odoo import models, fields, api


class DownSyncProductLine(models.Model):
    _name = 'down.sync.product.line'

    message = fields.Text()

    order_id = fields.Many2one('active.product.listing.report.ept')

    type = fields.Selection([
        ('get_data', u'获取数据'),
        ('create_update', u'创建/更新产品')], string=u'类型')


