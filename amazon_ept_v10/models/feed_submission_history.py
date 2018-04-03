from openerp import models, fields,api
from ..amazon_emipro_api.mws import Feeds
import time
from openerp.exceptions import Warning

class feed_submission_history(models.Model):
    _name="feed.submission.history"
    _rec_name = 'feed_result_id'
    _order = 'feed_submit_date desc'
    
    feed_result_id = fields.Char(size=256, string='Feed Result ID')
    feed_result = fields.Text('Feed Result')
    message = fields.Text('Message')
    feed_submit_date = fields.Datetime('Feed Submit Date')
    feed_result_date = fields.Datetime('Feed Result Date')
    instance_id = fields.Many2one('amazon.instance.ept', string='Instance', copy=False) 
    user_id = fields.Many2one('res.users',string="Requested User")
     
    @api.multi
    def get_feed_submission_result(self):
        amazon_process_log_obj=self.env['amazon.process.log.book']
        instance = self.instance_id
        feed_submission_id = self.feed_result_id
        if not instance or not feed_submission_id:
            raise Warning('You must need to first set Instance and feed submission ID.') 
        
        proxy_data=instance.seller_id.get_proxy_server()
        mws_obj=Feeds(access_key=str(instance.access_key),secret_key=str(instance.secret_key),account_id=str(instance.merchant_id),region=instance.country_id.amazon_marketplace_code or instance.country_id.code,proxies=proxy_data)        
        try:
            mws_obj.get_feed_submission_result(feed_submission_id)
            if hasattr(mws_obj, 'response') and type(mws_obj.response) !=type(None):
                result = str(mws_obj.response.content)
                self.write({'feed_result':result,'feed_result_date':time.strftime("%Y-%m-%d %H:%M:%S")})
        except Exception,e:
            job=amazon_process_log_obj.search([('request_feed_id','=',feed_submission_id)],order="id desc",limit=1)
            if job:
                job.write({'message':str(e)})
            else:
                raise Warning(str(e))
        return True