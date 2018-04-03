from openerp import models, fields, api
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports
from openerp.exceptions import Warning
import time
from datetime import datetime, timedelta

class report_request_history(models.Model):
    _name="report.request.history"
    _rec_name = 'report_request_id'
    
    @api.multi
    @api.depends('seller_id')
    def get_company(self):
        for record in self:
            company_id=record.seller_id and record.seller_id.company_id.id or False
            if not company_id:
                company_id=self.env.user.company_id.id
            record.company_id=company_id
                        
    report_request_id = fields.Char(size=256, string='Report Request ID')
    report_id = fields.Char(size=256, string='Report ID')
    report_type = fields.Char(size=256, string='Report Type')
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    requested_date = fields.Datetime('Requested Date',default=time.strftime("%Y-%m-%d %H:%M:%S"))
    state = fields.Selection([('draft','Draft'),('_SUBMITTED_','SUBMITTED'),('_IN_PROGRESS_','IN_PROGRESS'),
                                     ('_CANCELLED_','CANCELLED'),('_DONE_','DONE'),
                                     ('_DONE_NO_DATA_','DONE_NO_DATA'),('processed','PROCESSED'),('imported','Imported'),
                                     ('partially_processed','Partially Processed'),('closed','Closed')
                                     ],
                                    string='Report Status', default='draft')    
    seller_id = fields.Many2one('amazon.seller.ept', string='Seller', copy=False) 
    user_id = fields.Many2one('res.users',string="Requested User")
    company_id=fields.Many2one('res.company',string="Company",copy=False,compute=get_company,store=True)

    @api.multi
    def _check_duration(self):
        if self.end_date < self.start_date:
            return False
        return True
    
    _constraints = [
        (_check_duration, 'Error!\nThe start date must be precede its end date.', ['start_date','end_date'])
    ]    

    @api.model
    def request_report(self,report_rec,seller,report_type,start_date,end_date):
        if not seller:
            raise Warning('Please select instance')
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
                        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        instances = self.env['amazon.instance.ept'].search([('seller_id','=',seller.id)])
        marketplaceids = tuple(map(lambda x: x.market_place_id,instances))
        try:
            result = mws_obj.request_report(report_type, start_date=start_date, end_date=end_date, marketplaceids=marketplaceids)
            self.update_report_history(report_rec,result)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
        return True    
    
    @api.model
    def update_report_history(self,report_rec,request_result):
        result = request_result.parsed
        report_info = result.get('ReportInfo',{})
        report_request_info = result.get('ReportRequestInfo',{})
        request_id = report_state = report_id = False
        if report_request_info:
            request_id = str(report_request_info.get('ReportRequestId',{}).get('value',''))
            report_state = report_request_info.get('ReportProcessingStatus',{}).get('value','_SUBMITTED_')
            report_id = report_request_info.get('GeneratedReportId',{}).get('value',False)
        elif report_info:
            report_id = report_info.get('ReportId',{}).get('value',False)
            request_id = report_info.get('ReportRequestId',{}).get('value',False)
        if report_state =='_DONE_' and not report_id:
            self.get_report_list(report_rec)
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id':request_id}) 
        if report_state:
            vals.update({'state':report_state})
        if report_id:
            vals.update({'report_id':report_id})
        report_rec.write(vals)
        
        return True

    @api.model
    def get_report_request_list(self,report_rec):
        seller = report_rec.seller_id
        if not seller:
            raise Warning('Please select Seller')
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not report_rec.report_request_id:
            return True
        try:
            result = mws_obj.get_report_request_list(requestids = (report_rec.report_request_id,))
            self.update_report_history(report_rec,result)
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
        has_next = result.parsed.get('HasNext',{}).get('value','false')
        while has_next =='true':
            next_token = result.parsed.get('NextToken',{}).get('value')
            try:
                result=mws_obj.get_report_request_list_by_next_token(next_token)
                self.update_report_history(report_rec,result)
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
        return True
    
    @api.model
    def get_report_list(self,report_rec):
        seller = report_rec.seller_id
        if not seller:
            raise Warning('Please select seller')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not report_rec.request_id:
            return True
        try:
            result = mws_obj.get_report_list(requestids=[report_rec.request_id])
            self.update_report_history(report_rec,result)
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
                self.update_report_history(report_rec,result)
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
        return True
        
