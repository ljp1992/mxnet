from openerp import models,fields,api
import time
from datetime import datetime,timedelta
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports
from openerp.exceptions import Warning

class amazon_report_wizard(models.TransientModel):
    _name="amazon.report.wizard"
    
    seller_id = fields.Many2one("amazon.seller.ept","Seller")
    report_type = fields.Char(size=256, string='Report Type',default='_GET_V2_SETTLEMENT_REPORT_DATA_XML_')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    
    @api.model
    def default_get(self,fields):
        res = super(amazon_report_wizard,self).default_get(fields)
        if self._context.has_key('default_instance_id'):
            instance_id = self._context.get('default_instance_id')
            if instance_id:
                instance = self.env['amazon.instance.ept'].browse(instance_id)
                res.update({'seller_id':instance.seller_id.id})
        return res

    @api.multi
    def on_change_seller_id(self, seller_id,start_date,end_date):
        value = {}
        if seller_id:
            seller = self.env['amazon.seller.ept'].browse(seller_id)
            value.update({'start_date':seller.settlement_report_last_sync_on,'end_date':datetime.now()})
        return {'value': value }
    
    @api.multi
    def _check_duration(self):
        if self.end_date < self.start_date:
            return False
        return True

    _constraints = [
        (_check_duration, 'Error!\nThe start date must be precede its end date.', ['start_date','end_date'])
    ]

    @api.multi
    def get_reports(self):
        self.ensure_one()
        seller = self.seller_id
        if not seller:
            raise Warning('Please select seller')
        start_date = self.start_date
        end_date = self.end_date
        if start_date:
            db_import_time = time.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            start_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            start_date = str(start_date)+'Z'
        else:
            today = datetime.now()
            earlier = today - timedelta(days=30)
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            start_date = earlier_str+'Z'
        if end_date:
            db_import_time = time.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            end_date = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            end_date = str(end_date)+'Z'
        else:
            today = datetime.now()
            earlier_str = today.strftime("%Y-%m-%dT%H:%M:%S")
            end_date = earlier_str+'Z'
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code)
        try:
            result = mws_obj.get_report_list(types=(self.report_type,),fromdate=start_date,todate=end_date)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
        list_of_wrapper=[]
        list_of_wrapper.append(result)
        has_next = result.parsed.get('HasNext',{}).get('value',False)
        while has_next =='true':
            next_token=result.parsed.get('NextToken',{}).get('value')
            try:
                result = mws_obj.get_report_list_by_next_token(next_token)
            except Exception,e:
                if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                    error = mws_obj.parsed_response_error.parsed or {}
                    error_value = error.get('Message',{}).get('value')
                    error_value = error_value if error_value else str(mws_obj.response.content)  
                else:
                    error_value = str(e)
                raise Warning(error_value)
            has_next = result.parsed.get('HasNext',{}).get('value','')
            list_of_wrapper.append(result)
        settlement_obj = self.env['settlement.report.ept']
        odoo_report_ids = []
        for result in list_of_wrapper:
            reports=[]
            if not isinstance(result.parsed.get('ReportInfo',[]),list):
                reports.append(result.parsed.get('ReportInfo',[])) 
            else:
                reports=result.parsed.get('ReportInfo',[])               
            for report in reports:
                request_id = report.get('ReportRequestId',{}).get('value','')
                report_id = report.get('ReportId',{}).get('value','')
                report_type = report.get('ReportType',{}).get('value','')
                report_exist = settlement_obj.search(['|',('report_request_id','=',request_id),('report_id','=',report_id),('report_type','=',report_type)])
                if report_exist:
                    report_exist= report_exist[0]
                    odoo_report_ids.append(report_exist.id) 
                    continue
                try:
                    sequence=self.env.ref('amazon_ept_v10.seq_import_settlement_report_job')
                    if sequence:
                        report_name=sequence.next_by_id()
                    else:
                        report_name='/'
                except:
                    report_name='/'

                vals = {
                        'name':report_name,
                        'report_type':report_type,
                        'report_request_id':request_id,
                        'report_id':report_id,
                        'start_date':start_date,
                        'end_date':end_date,
                        'state':'_DONE_',
                        'seller_id':seller.id,
                        'user_id':self._uid,
                        }
                report_rec = settlement_obj.create(vals)
                odoo_report_ids.append(report_rec.id)
        return odoo_report_ids                
    
    @api.multi
    def get_report_list(self):
        odoo_report_ids = self.get_reports()
        if odoo_report_ids:
            action = self.env.ref('amazon_ept_v10.action_amazon_settlement_report_ept', False)
            result = action and action.read()[0] or {}
            
            if len(odoo_report_ids)>1:
                result['domain'] = "[('id','in',["+','.join(map(str, odoo_report_ids))+"])]"
            else:
                res = self.env.ref('amazon_ept_v10.amazon_settlement_report_form_view_ept', False)
                result['views'] = [(res and res.id or False, 'form')]
                result['res_id'] = odoo_report_ids and odoo_report_ids[0] or False            
            return result
                
        return True
        