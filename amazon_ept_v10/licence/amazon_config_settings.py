from odoo import models,fields,api,_
from odoo.exceptions import ValidationError

class amazon_config_settings(models.TransientModel):
    _inherit="res.config.settings"
    
    @api.multi
    def renew_app_licence(self):
        try:
            temp = self.env['ept.key.secrate']
        except:
            raise ValidationError("Problem with Auto Workflow Module.\nPlease install or update Auto Workflow Module and insert your licence key.\nAmazon --> settings --> App licence")
        ctx = self._context.copy() or {}
        ctx.update({'app_name':'amazon_ept_v10'})
        return {
                'name': 'App Activation Key',
                'view_type': 'form',
                'view_mode': 'form',
                'context':ctx,
                'res_model': 'ept.key.secrate',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                }