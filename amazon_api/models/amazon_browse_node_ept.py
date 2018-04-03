# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys
from StringIO import StringIO
from requests import request

class BrowseNode(models.Model):
    _inherit = 'amazon.browse.node.ept'

    # marketplace_id = fields.Many2one('amazon.marketplace.ept', string=u'Marketplace')

    @api.multi
    def name_get(self):
        result = []
        for node in self:
            name = node.name
            id = node.id
            country_name = node.country_id.name
            while True:
                if node.parent_id:
                    name = node.parent_id.name + '/' + name
                    node = node.parent_id
                else:
                    break
            result.append((id, country_name + '/' + name))
        return result


