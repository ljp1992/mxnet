# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    def unlink(self):
        for record in self:
            print record.amazon_instance_id
            if record.amazon_instance_id:
                record.amazon_instance_id.unlink()
        return super(ResPartner, self).unlink()