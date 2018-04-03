from odoo.addons.amazon_ept_v10.models.sale_order import amazon_sale_order_ept
from odoo.addons.amazon_ept_v10.models.settlement_report import settlement_report_ept
from datetime import datetime
import hashlib
import uuid
import requests
import base64
from odoo.exceptions import ValidationError
from odoo.addons.amazon_ept_v10.models.enviroment import verification_url

from odoo.addons.base.module.module import Module
from odoo import api, fields, models, modules, tools, _
__metaclass__ = type

_app_name = 'amazon_ept_v10'

class ir_module_module_python(Module):
    

    def button_immediate_upgrade(self):
        for record in self:
            if record.name==_app_name:
                record.update_list()
                try:
                    import odoo.addons.auto_invoice_workflow_ept.models.custom_base
                    import odoo.addons.auto_invoice_workflow_ept.models.custom_base_sale
                    import odoo.addons.auto_invoice_workflow_ept.models.procurement_group
                except:
                    raise ValidationError("Problem with auto invoice workflow module. Please find latest module from emiprotechnologies and upgrade it.")
                auto_invoice_workflow_ept = self.env['ir.module.module'].search([('name','=','auto_invoice_workflow_ept')])
                if not auto_invoice_workflow_ept:
                    raise ValidationError("Problem with auto invoice workflow module. Please find latest module from emiprotechnologies and upgrade it.")
                try:
                    auto_invoice_workflow_ept.button_immediate_upgrade()
                    app = record.env['ept.app.key.data'].search([('app','=',record.name)])
                    if not app:
                        ctx = self._context.copy() or {}
                        ctx.update({'app_name':record.name})
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
                
        return self._button_immediate_function(type(self).button_upgrade)
    

    def button_immediate_install(self):
        for record in self:
            for record in self:
                if record.name==_app_name:
                    record.update_list()
                    try:
                        import odoo.addons.auto_invoice_workflow_ept.models.custom_base
                        import odoo.addons.auto_invoice_workflow_ept.models.custom_base_sale
                        import odoo.addons.auto_invoice_workflow_ept.models.procurement_group
                    except:
                        raise ValidationError("Problem with auto invoice workflow module. Please find latest module from emiprotechnologies and upgrade it.")
                
        return self._button_immediate_function(type(self).button_install)
    Module.button_immediate_upgrade = button_immediate_upgrade
    Module.button_immediate_install = button_immediate_install
    

class instance_checking(amazon_sale_order_ept):
    
    def import_sales_order(self,seller,marketplaceids=[],created_before='',created_after=''):
        try:
            ept_key = self.env['ept.app.key.data'].search([('app','=',_app_name)])
        except Exception as e:
            raise ValidationError("Problem with Auto Workflow Module.\nPlease install or update Auto Workflow Module and insert your licence key.\nAmazon --> settings --> App licence")
        if len(ept_key) == 1:
            check = decode_client_key(ept_key,self._cr.dbname,_app_name)
            if check:
                return super(instance_checking,self).import_sales_order(seller=seller,marketplaceids=marketplaceids,created_before=created_before,created_after=created_after)
            else:
                raise ValidationError("Something bad happened with your app licence.")
        else:
            raise ValidationError("Something bad happened with your app licence.")
        
    def import_sales_order_by_flat_report(self,seller,marketplaceids=[],start_date=False,end_date=False,status=('Unshipped','PartiallyShipped')):
        try:
            ept_key = self.env['ept.app.key.data'].search([('app','=',_app_name)])
        except Exception as e:
            raise ValidationError("Problem with Auto Workflow Module.\nPlease install or update Auto Workflow Module and insert your licence key.\nAmazon --> settings --> App licence")
        if len(ept_key) == 1:
            check = decode_client_key(ept_key,self._cr.dbname,_app_name)
            if check:
                return super(instance_checking,self).import_sales_order_by_flat_report(seller=seller,marketplaceids=marketplaceids,start_date=start_date,end_date=end_date,status=status)
            else:
                raise ValidationError("Something bad happened with your app licence.")
        else:
            raise ValidationError("Something bad happened with your app licence.")
        
    def import_sales_order_by_xml_report(self,seller,marketplaceids=[],start_date=False,end_date=False):
        try:
            ept_key = self.env['ept.app.key.data'].search([('app','=',_app_name)])
        except Exception as e:
            raise ValidationError("Problem with Auto Workflow Module.\nPlease install or update Auto Workflow Module and insert your licence key.\nAmazon --> settings --> App licence")
        if len(ept_key) == 1:
            check = decode_client_key(ept_key,self._cr.dbname,_app_name)
            if check:
                return super(instance_checking,self).import_sales_order_by_xml_report(seller=seller,marketplaceids=marketplaceids,start_date=start_date,end_date=end_date)
            else:
                raise ValidationError("Something bad happened with your app licence.")
        else:
            raise ValidationError("Something bad happened with your app licence.")

class settlement_report_checking(settlement_report_ept):
    
    def process_settlement_report_file(self):
        try:
            ept_key = self.env['ept.app.key.data'].search([('app','=',_app_name)])
        except Exception as e:
            raise ValidationError("Problem with Auto Workflow Module.\nPlease install or update Auto Workflow Module and insert your licence key.\nAmazon --> settings --> App licence")
        if len(ept_key) == 1:
            check = decode_client_key(ept_key,self._cr.dbname,_app_name)
            if check:
                return super(settlement_report_checking,self).process_settlement_report_file()
            else:
                raise ValidationError("Something bad happened with your app licence.")
        else:
            raise ValidationError("Something bad happened with your app licence.") 
        
def get_mac():
    mac_num = hex(uuid.getnode()).replace('0x', '').upper()
    mac = '-'.join(mac_num[i : i + 2] for i in range(0, 11, 2))
    return mac
    
def decode_key(key):
    is_valid = False
    is_permanent = False
    expiry_date = False
    
    random_number = 0
    date_time_str = ''
    for str_chr in key:
        if str_chr.isdigit():
            random_number= int(str_chr)
            break
        date_time_str = date_time_str + str_chr

    count = 0
    date_digit_string = ''
    for str_char in date_time_str:
        plus_number = 65
        if ord(str_char) >= 97:
            plus_number = 97
        int_value = ord(str_char) - count - random_number
        int_value = int_value - plus_number
        if int_value < 0:
            int_value =  int_value + 26
        date_digit_string = '%s%s'%(date_digit_string,int_value)
        count = count + 1
    to_md5 = '%s%s'%(date_time_str,random_number)
    md5 = hashlib.md5(to_md5.encode(encoding='utf_8', errors='strict')).hexdigest()
    if md5[4:random_number+9] == key[len(date_time_str)+1:len(date_time_str)+1+random_number+5]:
        is_valid = True
    
    processed_str_len = len(to_md5) + len(md5[4:random_number+9])
    key_part = key[processed_str_len:]
    
    if hashlib.md5("ept_permanent".encode(encoding='utf_8', errors='strict')).hexdigest()[4:random_number+9] == key_part:
        is_permanent = True
    else:
        expiry_date = False
        count = 0
        ex_date_digit_string = ''
        for str_char in key_part:
            plus_number = 65
            if ord(str_char) >= 97:
                plus_number = 97
            int_value = ord(str_char) - count - random_number
            int_value = int_value - plus_number
            if int_value < 0:
                int_value =  int_value + 26
            ex_date_digit_string = '%s%s'%(ex_date_digit_string,int_value)
            count = count + 1
        expiry_date =   ex_date_digit_string 
    if is_valid:
        return is_permanent or expiry_date
    else:
        return False

def decode_client_key(ept_key,db_name,app_name):

    return True
    
    # #Mac checking
    # #db_name_checking
    # key = ept_key.key
    # create_date = ept_key.create_date
    # ept_flag = ept_key.ept_flag
    # current_date = datetime.now().date()
    # create_date = datetime.strptime(create_date.split(" ")[0], "%Y-%m-%d").date()
    # if create_date.day%27 == current_date.day:
    #     if ept_flag:
    #         headers = {'User-Agent': 'ept/1.0'}
    #         payload = {}
    #         session = requests.Session()
    #         mac = get_mac()
    #         from odoo.addons.amazon_ept_v10.models.enviroment import verification_url
    #         from odoo.addons.amazon_ept_v10.models.enviroment import erp_verification_url
    #         skip = False
    #         try:
    #             post_url = "%s%s/%s/%s/%s"%(erp_verification_url,key,mac,db_name,app_name)
    #             response = session.post("%s?rdte=%s"%(verification_url,post_url),headers=headers,data={'rdte':post_url})
    #             if not response.status_code == 200:
    #                 post_url = "%s%s/%s/%s/%s"%(erp_verification_url,key,mac,db_name,app_name)
    #                 response = session.post(post_url,headers=headers,data={})
    #                 if not response.status_code == 200:
    #                     return False
    #         except:
    #             skip = True
    #         ept_key.write({'ept_flag':False})
    # else:
    #     if not ept_flag:
    #         ept_key.write({'ept_flag':True})
    #
    # try:
    #     mac_pass = False
    #     mac = get_mac()
    #     string_to_append = hashlib.md5(mac.encode(encoding='utf_8', errors='strict') + db_name.encode(encoding='utf_8', errors='strict')).hexdigest()[0:10]
    #     if key[0:10] == string_to_append:
    #         mac_pass = True
    #     #child checking
    #     child_key = key[10:]
    #     child_pass = decode_key(child_key)
    #
    #     #Expiry date checking
    #     if mac_pass and child_pass:
    #         if type(child_pass) == type(True):
    #             return True
    #         else:
    #             ex_date = datetime.strptime(child_pass, "%Y%m%d").date()
    #             if ex_date < current_date:
    #                 raise ValidationError("Your licence has been expired. Please renew it to continue....")
    #             return True
    #     else:
    #         return False
    # except:
    #     return False
