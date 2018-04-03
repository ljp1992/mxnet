from openerp import models,fields,api
from ..amazon_emipro_api.utils import xml2dict

class amazon_process_log_book(models.Model):
    _name="amazon.process.log.book"
    _order='id desc'

    name = fields.Char("Name")
    filename = fields.Char("File Name")
    create_date = fields.Datetime("Create Date")
    instance_id=fields.Many2one('amazon.instance.ept',string="Instance")
    transaction_log_ids = fields.One2many("amazon.transaction.log","job_id",string="Log")
    skip_process = fields.Boolean("Skip Process")
    application = fields.Selection([('sales','Sales')
                                    ,('purchase','Purchase')
                                    ,('sales_return','Sales Return')
                                    ,('update_tracking_number','Update Tracking Number')
                                    ,('stock_report','Stock Report')
                                    ,('sync_products','Sync Products')
                                    ,('stock_adjust','Stock Adjustment')
                                    ,('removal_order','Removal Order')
                                    ,('product','Product')
                                    ,('price','Price')
                                    ,('image','Image')
                                    ,('refund','Refund')
                                    ,('update_inbound_shipment','Update Inbound Shipment')
                                    ,('other','Other')],string="Application")
    operation_type = fields.Selection([('import','Import'),('export','Export')]  ,string="Operation")    
    message=fields.Text("Message")
    request_feed_id=fields.Many2one("feed.submission.history",string="Request Feed",copy=False)
    is_feed_updated=fields.Boolean("Is feed updated",default=False)
    
    @api.multi
    def get_feed_result(self):
        self.process_feed_submisstion_job([],self.ids)
        return True
    @api.multi
    def check_exported_products_feed(self,instance_ids,job_ids):
        domain=[('application','=','product'),('operation_type','=','export')
                ,('request_feed_id','!=',False),('is_feed_updated','=',False)]        
        instance_ids and domain.append(('instance_id','in',instance_ids))
        job_ids and domain.append(('id','in',job_ids))
        jobs=self.search(domain)
        return jobs,'export_product'
    @api.multi
    def check_exported_images_feed(self,instance_ids,job_ids):
        domain=[('application','=','image'),('operation_type','=','export')
                ,('request_feed_id','!=',False),('is_feed_updated','=',False)]        
        instance_ids and domain.append(('instance_id','in',instance_ids))
        job_ids and domain.append(('id','in',job_ids))
        jobs=self.search(domain)
        return jobs,'export_image'

    @api.multi
    def check_exported_price_feed(self,instance_ids,job_ids):
        domain=[('application','=','price'),('operation_type','=','export')
                ,('request_feed_id','!=',False),('is_feed_updated','=',False)]        
        instance_ids and domain.append(('instance_id','in',instance_ids))
        job_ids and domain.append(('id','in',job_ids))
        jobs=self.search(domain)
        return jobs,'export_price'
    
    @api.multi
    def create_log_based_on_operation(self,jobs,operation):
        amazon_product_obj=self.env['amazon.product.ept']
        amazon_transaction_log_obj=self.env['amazon.transaction.log']
        model_id=amazon_transaction_log_obj.get_model_id('amazon.product.ept')
        xml_to_dict_obj=xml2dict()

        for job in jobs:
            job.request_feed_id.get_feed_submission_result()
            if job.request_feed_id.feed_result:
                result=xml_to_dict_obj.fromstring(job.request_feed_id.feed_result)
                lines=result.get('AmazonEnvelope',{}).get('Message',{}).get('ProcessingReport',{}).get('Result',{})
                if not isinstance(lines,list):
                    lines=[lines]
                for line in lines:
                    sku=line.get('AdditionalInfo',{}).get('SKU',{}).get('value')
                    result_code=line.get('ResultCode',{}).get('value')
                    product=amazon_product_obj.search([('seller_sku','=',sku),('instance_id','=',job.instance_id.id)])
                    log_type=False
                    if result_code=='Warning':
                        log_type='warning'
                    if result_code=='Error':
                        if operation=='export_product':
                            product and product.write({'error_in_export_product':True})
                        if operation=='export_price':
                            product and product.write({'error_in_export_price':True})
                        if operation=='export_image':
                            product and product.write({'error_in_export_image':True})

                        log_type='error'
                    description=line.get('ResultDescription',{}).get('value')    
                    amazon_transaction_log_obj.create({
                                                       'model_id':model_id,
                                                       'message':description,
                                                       'res_id':product and product.id or False,
                                                       'log_type':log_type,
                                                       'job_id':job.id,                                                       
                                                       })
                summary=result.get('AmazonEnvelope',{}).get('Message',{}).get('ProcessingReport',{}).get('ProcessingSummary',{})
                description="MessagesProcessed %s"%(summary.get('MessagesProcessed',{}).get('value'))
                description="%s || MessagesSuccessful %s"%(description,summary.get('MessagesSuccessful',{}).get('value'))
                description="%s || MessagesWithError %s"%(description,summary.get('MessagesWithError',{}).get('value'))
                description="%s || MessagesWithWarning %s"%(description,summary.get('MessagesWithWarning',{}).get('value'))
                job.write({'message':description,'is_feed_updated':True})
        return True        
    @api.model
    def process_feed_submisstion_job(self,instance_ids=[],job_ids=[]):
        jobs,operation=self.check_exported_products_feed(instance_ids,job_ids)
        self.create_log_based_on_operation(jobs, operation)
        jobs,operation=self.check_exported_price_feed(instance_ids, job_ids)
        self.create_log_based_on_operation(jobs, operation)
        jobs,operation=self.check_exported_images_feed(instance_ids, job_ids)
        self.create_log_based_on_operation(jobs, operation)
        return True
    @api.model
    def create(self,vals):
        try:
            sequence=self.env.ref("amazon_ept_v10.seq_amazon_file_process_job")
        except:
            sequence=False
        name=sequence and sequence.next_by_id() or '/'
        if type(vals)==dict:
            vals.update({'name':name})
        return super(amazon_process_log_book, self).create(vals)

class amazon_transaction_log(models.Model):
    _name = 'amazon.transaction.log'
    _rec_name='file_name'
    _order='id desc'    
    
    @api.multi
    def get_difference_qty(self):
        for record in self:
            if record.log_type == 'mismatch':
                record.difference_qty=record.required_qty-record.processed_qty

    @api.model
    def get_model_id(self, model_name):
        model = self.env['ir.model'].search([('model','=',model_name)])
        if model:
            return model.id
        return False
    
    message = fields.Text("Message")
    model_id = fields.Many2one("ir.model",string="Model")
    res_id = fields.Integer("Record ID")
    job_id = fields.Many2one("amazon.process.log.book",string="File Process Job")
    
    log_type = fields.Selection([
                                ('not_found','NOT FOUND'),
                                ('mismatch','MISMATCH'),
                                ('error','Error'),
                                ('warning','Warning')
                                ],'Log Type')
    action_type = fields.Selection([
                                    ('create','Created New'),
                                    ('skip_line','Line Skipped'),
                                    ('terminate_process_with_log','Terminate Process With Log')
                                    ], 'Action')
    operation_type = fields.Selection([('import','Import'),('export','Export')]
                                      ,string="Operation",related="job_id.operation_type",store=False,readonly=True)
    required_qty = fields.Float('Required Qty')
    processed_qty = fields.Float('Processed Qty')
    difference_qty = fields.Float("Difference Qty",compute="get_difference_qty")
    
    not_found_value = fields.Char('Not Founded Value')
    manually_processed=fields.Boolean("Manually Processed",help="If This field is True then it will be hidden from mismatch details",default=False)
    create_date = fields.Datetime("Created Date")    
    file_name = fields.Char(string="File Name",related="job_id.filename",store=False,readonly=True)
    user_id = fields.Many2one("res.users",string="Responsible")
    skip_record = fields.Boolean("Skip Line")
    amazon_order_reference=fields.Char("Amazon Order Ref")