from odoo import models,fields,api
class res_partner(models.Model):
    _inherit="res.partner"
    
    @api.model
    def _commercial_fields(self):
        result=super(res_partner,self)._commercial_fields()
        if 'last_time_entries_checked' in result:
            result.remove('last_time_entries_checked')
        return result