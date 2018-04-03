from odoo import models,fields,api
import requests
import base64
import uuid
from odoo.exceptions import ValidationError
from odoo.addons.auto_invoice_workflow_ept.models.environment import uninstall_url
from odoo.addons.auto_invoice_workflow_ept.models.environment import registration_url
from odoo.addons.auto_invoice_workflow_ept.models.environment import success_url

class verify_key(models.TransientModel):
    
    _name = "ept.key.secrate"
    
    ept_key = fields.Char('Key')
   
    @api.model  
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):

        app_name = self._context.get('app_name')
        current_key = self.env['ept.app.key.data'].search([('app','=',app_name)],limit=1).key
        arch = '<form string="App Activation">\n                <group>\n                    <field name="ept_key" string="Key" required="1" modifiers="{&quot;required&quot;: true}"/>\n                    </group>\n                    <footer>\n                        <button name="verify_key" string="Submit" type="object" class="oe_highlight"/>\n                        or\n                        <button special="cancel" string="Cancel" class="oe_link"/>\n                    </footer>\n                </form>'
        
        if current_key:
        	current_key = current_key[10:]
        	arch = '<form string="App Activation">\n                <group>\n   <pre><p><b>Current Key   :      %s</b></p></pre></group><group>                  <field name="ept_key" string="Key" required="1" modifiers="{&quot;required&quot;: true}"/>\n                    </group>\n                    <footer>\n                        <button name="verify_key" string="Submit" type="object" class="oe_highlight"/>\n                        or\n                        <button special="cancel" string="Cancel" class="oe_link"/>\n                    </footer>\n                </form>'%current_key
        
        return {
                     'name': 'test.dynamic',
                     'arch': arch,
                     'fields': {
                      'ept_key': {
                       'change_default': False,
                       'string': 'Key',
                       'searchable': True,
                       'views': {},
                       'required': False,
                       'manual': False,
                       'readonly': False,
                       'depends': (),
                       'company_dependent': False,
                       'sortable': True,
                       'translate': False,
                       'type': 'char',
                       'store': True
                      },
                     },
                     'model': 'ept.key.secrate',
                     'type': 'form',
                     'field_parent': False
        }
    
    def get_mac(self):
        mac_num = hex(uuid.getnode()).replace('0x', '').upper()
        mac = '-'.join(mac_num[i : i + 2] for i in range(0, 11, 2))
        return mac

    @api.multi
    def verify_key(self):
        from odoo.addons.auto_invoice_workflow_ept.models.environment import uninstall_url
        from odoo.addons.auto_invoice_workflow_ept.models.environment import registration_url
        from odoo.addons.auto_invoice_workflow_ept.models.environment import success_url
        from odoo.addons.auto_invoice_workflow_ept.models.environment import erp_success_url
        from odoo.addons.auto_invoice_workflow_ept.models.environment import erp_registration_url
        from odoo.addons.auto_invoice_workflow_ept.models.environment import erp_uninstall_url
        url = registration_url
        headers = {'User-Agent': 'ept/1.0'}
        payload = {}
        session = requests.Session()
      
        key = self.ept_key
        db_name = self._cr.dbname
        mac = self.get_mac()
        app_name = self._context.get('app_name')
        url = erp_registration_url + key + "/" + mac + "/" + db_name + "/" + app_name
        response = False
        try:
            response = session.post("%s?rdte=%s"%(registration_url,url),headers={},data={'rdte':url})
        except:
            try:
                response = session.post(url,headers={},data={}) 
            except:
                raise ValidationError("Connection Problem. Please try again after some time.")
        if response and response.status_code == 200:
            ept_key_data = self.env['ept.app.key.data'].search([('app','=',app_name)])
            if not ept_key_data:
                self.env['ept.app.key.data'].create({'key':response.text,'app':app_name})
            else:
                try:
                    post_url = "%s/%s/%s/%s/%s"%(erp_uninstall_url,key,mac,db_name,app_name)
                    session.post("%s?rdte=%s"%(uninstall_url,post_url),headers=headers,data={'rdte':post_url})
                except:
                    try:
                        session.post(post_url,headers=headers,data={}) 
                    except:
                        pass
                ept_key_data.write({'key':response.text,'app':app_name})
            app_to_install = self.env['ir.module.module'].search([('name','=',app_name)])
            if app_to_install:
                skip = False
                if app_to_install.state not in ['installed']:
                    tmp,skip = app_to_install.button_immediate_install()
#                post_url="%s%s"%(erp_success_url,key)
#                payload = {'rdte':post_url}
#                 try:
#                     response = session.post("%s?rdte=%s"%(success_url,post_url),headers=headers,data=payload)
#                 except:
#                     try:
#                         response = session.post(post_url,headers=headers,data={})
#                     except:
#                         pass 
#                if response.status_code == 200:
                if not self._context.get('install',False):
                    return
                env = api.Environment(self._cr, self._uid, self._context)
                config = tmp if skip else env['res.config'].next() or {}
                if config.get('type') not in ('ir.actions.act_window_close',):
                    return config
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
#                 else:
#                     app_to_install.module_uninstall()
#                     raise ValidationError("Something bad happened")
            else:
                raise ValidationError("Something bad happened")
        else:
            raise ValidationError(response.text if response!=False and response.text else "Something bad happened")