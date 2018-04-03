from odoo import models,fields,api


class verify_key(models.Model):
    
    _name = 'ept.app.key.data'
    
    key = fields.Char('Key',required=True)
    app = fields.Char('App Name',required=True)
    ept_flag = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('code_app_uniq', 'unique (key,app)', 'App with this key is already installed!!!')
    ]