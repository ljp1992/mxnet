from odoo.addons.base.module.module import Module
import odoo
from odoo import api, fields, models, modules, tools, _
import requests
import base64
import uuid
from odoo.exceptions import ValidationError
from odoo.addons.auto_invoice_workflow_ept.models.environment import uninstall_url
from odoo.addons.auto_invoice_workflow_ept.models.app_list import ept_apps
__metaclass__ = type

def get_mac():
        mac_num = hex(uuid.getnode()).replace('0x', '').upper()
        mac = '-'.join(mac_num[i : i + 2] for i in range(0, 11, 2))
        return mac
    
class ir_module_module_python(Module):

    def module_uninstall(self):
        for record in self:
            if record.name in ept_apps:
                db_name = self._cr.dbname
                mac = get_mac()
                app_name = record.name
                from odoo.addons.auto_invoice_workflow_ept.models.environment import uninstall_url
                from odoo.addons.auto_invoice_workflow_ept.models.environment import erp_uninstall_url
                app = False
                try:
                    app = record.env['ept.app.key.data'].search([('app','=',record.name)])
                except:
                    pass
                headers = {'User-Agent': 'ept/1.0'}
                session = requests.Session()
                if app:
                    app_key = app.key
                    try:
                        post_url = "%s%s/%s/%s/%s"%(erp_uninstall_url,app_key,mac,db_name,app_name)
                        response = session.post("%s?rdte=%s"%(uninstall_url,post_url),headers=headers,data={'rdte':post_url})
                        app.unlink()
                    except:
                        try:
                            post_url = "%s%s/%s/%s/%s"%(erp_uninstall_url,app_key,mac,db_name,app_name)
                            response = session.post(post_url,headers=headers,data={})
                            app.unlink()
                        except:
                            app.unlink()
                            pass
                else:
                    try:
                        post_url = "%s/undefined/%s/%s/%s"%(erp_uninstall_url,mac,db_name,app_name)
                        response = session.post("%s?rdte=%s"%(uninstall_url,post_url),headers=headers,data={'rdte':post_url})
                        if response.status_code != 200:
                            raise ValidationError("Something bad happened.\n You can not uninstall this app.") 
                    except:
                        try:
                            post_url = "%s/undefined/%s/%s/%s"%(erp_uninstall_url,mac,db_name,app_name)
                            response = session.post(post_url,headers=headers,data={})
                            if response.status_code != 200:
                                raise ValidationError("Something bad happened.\n You can not uninstall this app.") 
                        except:
                            pass
        modules_to_remove = self.mapped('name')
        self.env['ir.model.data']._module_data_uninstall(modules_to_remove)
        self.write({'state': 'uninstalled', 'latest_version': False})
        return True
        
    def _button_immediate_function(self, function):
        if self.name in ept_apps:
            ctx = self._context.copy() or {}
            ctx.update({'app_name':self.name})
            ctx.update({'install':True})
            auto_invoice_workflow_ept = self.env['ir.module.module'].search([('name','=','auto_invoice_workflow_ept')])
            if not auto_invoice_workflow_ept:
                raise ValidationError("Auto invoice workflow module is missing. You can not install this module without auto invoice workflow.") 
            try:
                if auto_invoice_workflow_ept.state not in ['installed','to install','to upgrade']:
                    auto_invoice_workflow_ept.button_immediate_install()
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
                else:
                    auto_invoice_workflow_ept.button_immediate_upgrade()
                app = self.env['ept.app.key.data'].search([('app','=',self.name)])
                if not app:
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
            except:
                raise ValidationError("Problem with auto invoice workflow module. Please find latest module from emiprotechnologies and upgrade it.") 
                    
        function(self)

        self._cr.commit()
        api.Environment.reset()
        modules.registry.Registry.new(self._cr.dbname, update_module=True)

        self._cr.commit()
        env = api.Environment(self._cr, self._uid, self._context)
        config = env['res.config'].next() or {}
        if config.get('type') not in ('ir.actions.act_window_close',):
            if self.name in ept_apps:
                return config,True
            else:
                return config

        # reload the client; open the first available root menu
        menu = env['ir.ui.menu'].search([('parent_id', '=', False)])[:1]
        if self.name not in ept_apps:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                'params': {'menu_id': menu.id},
            },False
       
    #Module.button_install = button_install
    Module._button_immediate_function = _button_immediate_function
    Module.module_uninstall = module_uninstall
        