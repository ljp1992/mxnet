# -*- encoding: utf-8 -*-

from openerp import models, fields, api, _

class ProductBrand(models.Model):
    _inherit = "product.brand"

    # _sql_constraints = [
    #     ('name_uniq', 'unique(name)', _(u'品牌名称不能重复！')),
    # ]