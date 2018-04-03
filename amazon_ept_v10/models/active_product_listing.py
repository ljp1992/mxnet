from openerp import models,fields,api,_
from openerp.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports
from openerp.exceptions import Warning
import time
import base64
import csv
from StringIO import StringIO

class active_product_listing_report_ept(models.Model):
    _name="active.product.listing.report.ept"
    _inherits={"report.request.history":'report_history_id'}
    _description = "Active Product"
    _inherit = ['mail.thread']
    _order = 'id desc'
    
    instance_id=fields.Many2one('amazon.instance.ept',string='Instance')
    report_id=fields.Char('Report ID', readonly='1')
    report_request_id=fields.Char('Report Request ID', readonly='1')
    
    name = fields.Char(size=256, string='Name')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment')
    report_history_id = fields.Many2one('report.request.history', string='Report',required=True,ondelete="cascade",index=True, auto_join=True)
    
    @api.model
    def create(self,vals):    
        try:
            sequence=self.env.ref('amazon_ept_v10.seq_active_product_list')
            if sequence:
                report_name=sequence.next_by_id()
            else:
                report_name='/'
        except:
            report_name='/'
        vals.update({'name':report_name})
        return super(active_product_listing_report_ept,self).create(vals)
    
    @api.multi
    def unlink(self):
        for report in self:
            if report.state == 'processed':
                raise Warning(_('You cannot delete processed report.'))
        return super(active_product_listing_report_ept, self).unlink()
    
    @api.model
    def default_get(self, fields):
        res = super(active_product_listing_report_ept, self).default_get(fields)
        if not fields:
            return res
        res.update({'report_type' : '_GET_MERCHANT_LISTINGS_DATA_',
                    })
        return res
    @api.multi
    def request_report(self):
        instance = self.instance_id
        seller = self.instance_id.seller_id
        report_type = self.report_type
        if not seller:
            raise Warning('Please select instance')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        
        marketplace_ids=tuple([instance.market_place_id])
        try:
            result = mws_obj.request_report(report_type, start_date=None, end_date=None, marketplaceids=marketplace_ids)
            self.update_report_history(result)
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
    def update_report_history(self,request_result):
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
            self.get_report_list()
        vals = {}
        if not self.report_request_id and request_id:
            vals.update({'report_request_id':request_id}) 
        if report_state:
            vals.update({'state':report_state})
        if report_id:
            vals.update({'report_id':report_id})
        self.write(vals)
        return True
    @api.multi
    def get_report_list(self):
        self.ensure_one()
        seller = self.instance_id.seller_id
        if not seller:
            raise Warning('Please select seller')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not self.request_id:
            return True
        try:
            result = mws_obj.get_report_list(requestids=[self.request_id])
            self.update_report_history(result)
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
                self.update_report_history(result)
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
    
    @api.multi
    def get_report_request_list(self):
        self.ensure_one()
        seller = self.instance_id.seller_id
        if not seller:
            raise Warning('Please select Seller')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not self.report_request_id:
            return True
        try:
            result = mws_obj.get_report_request_list(requestids = (self.report_request_id,))
            self.update_report_history(result)
            
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
                self.update_report_history(result)

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
    
    @api.multi
    def get_report(self):
        self.ensure_one()
        seller = self.instance_id.seller_id
        if not seller:
            raise Warning('Please select seller')
        
        proxy_data=seller.get_proxy_server()
        mws_obj = Reports(access_key=str(seller.access_key),secret_key=str(seller.secret_key),account_id=str(seller.merchant_id),region=seller.country_id.amazon_marketplace_code or seller.country_id.code,proxies=proxy_data)
        if not self.report_id:
            return True
        try:
            result = mws_obj.get_report(report_id=self.report_id)
        except Exception,e:
            if hasattr(mws_obj, 'parsed_response_error') and type(mws_obj.parsed_response_error) !=type(None):
                error = mws_obj.parsed_response_error.parsed or {}
                error_value = error.get('Message',{}).get('value')
                error_value = error_value if error_value else str(mws_obj.response.content)  
            else:
                error_value = str(e)
            raise Warning(error_value)
        result = base64.b64encode(result.parsed)
        file_name = "Active_Product_List_" + time.strftime("%Y_%m_%d_%H%M%S") + '.csv'
        
        attachment = self.env['ir.attachment'].create({
                                           'name': file_name,
                                           'datas': result,
                                           'datas_fname': file_name,
                                           'res_model': 'mail.compose.message',
                                           'type': 'binary'
                                         })
        self.message_post(body=_("<b>Active Product Report Downloaded</b>"),attachment_ids=attachment.ids)
        self.write({'attachment_id':attachment.id})
        
        return True
    @api.multi
    def download_report(self):
        self.ensure_one()
        if self.attachment_id:
            return {
                    'type' : 'ir.actions.act_url',
                    'url' : '/web/content/%s?download=true' % ( self.attachment_id.id ),
                    'target' : 'self',
                    }
        return True 
    
    def get_fulfillment_type(self,fulfillment_channel):
        if fulfillment_channel and fulfillment_channel=='DEFAULT':
            return 'MFN'
        else:
            return False

    @api.multi
    def sync_products(self):
        self.ensure_one()
        if not self.attachment_id:
            raise Warning("There is no any report are attached with this record.")
        if not self.instance_id:
            raise Warning("Instance not found ")
        amazon_encoding=self.instance_id.amazon_encodings
        imp_file = StringIO(base64.decodestring((self.attachment_id.datas).decode(amazon_encoding)))
        reader = csv.DictReader(imp_file,delimiter='\t')
        amazon_product_ept_obj = self.env['amazon.product.ept']
        product_obj = self.env['product.product']
        log_book_obj=self.env['amazon.process.log.book']
        transaction_log_obj=self.env['amazon.transaction.log']
        model_id=transaction_log_obj.get_model_id('amazon.product.ept')
        transaction_vals={}
        log_rec=False
        for row in reader:
            fulfillment_type=self.get_fulfillment_type(row.get('fulfillment-channel',''))
            if fulfillment_type:
                record=amazon_product_ept_obj.search_amazon_product(self.instance_id.id,row.get('seller-sku',''),fulfillment_by=fulfillment_type)
                if record:
                    description=unicode(row.get('item-description',''),"utf-8",errors='ignore')
                    title=unicode(row.get('item-name',''),"utf-8",errors='ignore')                
                    record.write({
                                   'title':title,
                                   'long_description':description,
                                   'seller_sku':row.get('seller-sku',''),
                                   'fulfillment_by':fulfillment_type,
                                   'product_asin':row.get('asin1'),
                                   'exported_to_amazon':True,
                                   })
                else:
                    product_record=product_obj.search([('default_code','=',row.get('seller-sku',''))])
                    not_found_msg="""Multiple product found for same sku %s in ERP """%(row.get('seller-sku',''))
                    if len(product_record.ids)>1:
                        if not log_rec:
                            log_vals={
                                  'application':'sync_products',
                                  'instance_id':self.instance_id.id,
                                  'operation_type':'import',
                                 }
                            log_rec=log_book_obj.create(log_vals)
                            
                        transaction_vals={'model_id':model_id,
                                          'log_type':'not_found',
                                          'action_type':'skip_line',
                                          'message':not_found_msg,
                                          'job_id':log_rec.id,                                         }
                        transaction_log_obj.create(transaction_vals)
                        continue
                    if product_record:
                        description=unicode(row.get('item-description',''),"utf-8",errors='ignore')
                        title=unicode(row.get('item-name',''),"utf-8",errors='ignore')                
                        amazon_product_ept_obj.create({
                                                       'product_id':product_record.id,
                                                       'instance_id':self.instance_id.id,
                                                       'title':title,
                                                       'long_description':description,
                                                       'product_asin':row.get('asin1'),
                                                       'seller_sku':row.get('seller-sku',''),
                                                       'fulfillment_by':fulfillment_type,
                                                       'exported_to_amazon':True
                                                       })
                    else:
                        not_found_msg=""" Line Skipped due to product not found seller sku %s || Instance %s """%(row.get('seller-sku',''),self.instance_id.name)
                        
                        if not log_rec:
                            log_vals={
                                  'application':'sync_products',
                                  'instance_id':self.instance_id.id,
                                  'operation_type':'import',
                                 }
                            log_rec=log_book_obj.create(log_vals)
                            
                        transaction_vals={
                                          'model_id':model_id,
                                          'log_type':'not_found',
                                          'action_type':'skip_line',
                                          'message':not_found_msg,
                                          'job_id':log_rec.id,
                                         }
                        transaction_log_obj.create(transaction_vals)
                        continue
        self.write({'state':'processed'})
        return True