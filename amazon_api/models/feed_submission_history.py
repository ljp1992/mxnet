# -*- encoding: utf-8 -*-

from openerp import models, fields, api
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports, Products, Feeds, DictWrapper
import time
from openerp.exceptions import Warning
from odoo.exceptions import UserError

class feed_submission_history(models.Model):
    _inherit = "feed.submission.history"

    model_name = fields.Char(string=u'model name')
    record_id = fields.Integer(string=u'record id')

    @api.multi
    def get_feed_result_ljp(self):
        tmpl_obj = self.env['product.template']
        feed_obj = self.env['feed.submission.history']
        # 变体
        templates = tmpl_obj.search([('product_status', '=', 'updating')])
        for template in templates:
            product_feed = feed_obj.search([('feed_result_id', '=', template.product_feed_id)])
            if product_feed and len(product_feed) == 1:
                if not product_feed.feed_result:
                    try:
                        product_feed.get_feed_submission_result()
                    except:
                        continue
                if product_feed.feed_result:
                    result = DictWrapper(product_feed.feed_result, '')
                    data = result.parsed
                    error_info = data.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}) \
                        .get('MessagesWithError', {}).get('value', '')
                    # print data,error_info
                    if error_info == '0':
                        template.with_context(collection_mark='collected').product_status = 'done'
                    else:
                        template.with_context(collection_mark='collected').product_status = 'fail'
        # 母子关系
        templates = tmpl_obj.search([('relation_update', '=', 'updating')])
        for template in templates:
            relation_feed = feed_obj.search([('feed_result_id', '=', template.relation_feed_id)])
            if relation_feed and len(relation_feed) == 1:
                if not relation_feed.feed_result:
                    try:
                        relation_feed.get_feed_submission_result()
                    except:
                        continue
                if relation_feed.feed_result:
                    feed_result = DictWrapper(relation_feed.feed_result, '')
                    error_info = feed_result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}) \
                        .get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        template.with_context(collection_mark='collected').relation_update = 'done'
                    else:
                        template.with_context(collection_mark='collected').relation_update = 'fail'
        # 价格
        templates = tmpl_obj.search([('price_update', '=', 'updating')])
        for template in templates:
            price_feed = feed_obj.search([('feed_result_id', '=', template.price_feed_id)])
            if price_feed and len(price_feed) == 1:
                if not price_feed.feed_result:
                    try:
                        price_feed.get_feed_submission_result()
                    except:
                        continue
                if price_feed.feed_result:
                    result = DictWrapper(price_feed.feed_result, '')
                    error_info = result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}) \
                        .get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        template.with_context(collection_mark='collected').price_update = 'done'
                    else:
                        template.with_context(collection_mark='collected').price_update = 'fail'
        # 图片
        templates = tmpl_obj.search([('image_update', '=', 'updating')])
        for template in templates:
            image_feed = feed_obj.search([('feed_result_id', '=', template.image_feed_id)])
            if image_feed and len(image_feed) == 1:
                if not image_feed.feed_result:
                    try:
                        image_feed.get_feed_submission_result()
                    except:
                        continue
                if image_feed.feed_result:
                    result = DictWrapper(image_feed.feed_result, '')
                    error_info = result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}) \
                        .get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        template.with_context(collection_mark='collected').image_update = 'done'
                    else:
                        template.with_context(collection_mark='collected').image_update = 'fail'
        # 库存
        templates = tmpl_obj.search([('stock_update', '=', 'updating')])
        for template in templates:
            stock_feed = feed_obj.search([('feed_result_id', '=', template.stock_feed_id)])
            if stock_feed and len(stock_feed) == 1:
                if not stock_feed.feed_result:
                    try:
                        stock_feed.get_feed_submission_result()
                    except:
                        continue
                if stock_feed.feed_result:
                    result = DictWrapper(stock_feed.feed_result, '')
                    error_info = result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}) \
                        .get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        template.with_context(collection_mark='collected').stock_update = 'done'
                    else:
                        template.with_context(collection_mark='collected').stock_update = 'fail'
        #亚马逊处理真发货请求
        pickings = self.env['stock.picking'].search([('amazon_delivery_state', '=', 'in_delivery')])
        for picking in pickings:
            delivery_feed = feed_obj.search([('feed_result_id', '=', picking.delivery_submission_id)], limit=1)
            if delivery_feed:
                if not delivery_feed.feed_result:
                    try:
                        delivery_feed.get_feed_submission_result()
                    except:
                        continue
                if delivery_feed.feed_result:
                    result = DictWrapper(delivery_feed.feed_result, '')
                    error_info = result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}).get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        picking.amazon_delivery_state = 'done'
                    else:
                        picking.amazon_delivery_state = 'failed'
        #亚马逊处理假发货请求
        sale_orders = self.env['sale.order'].search([('amazon_false_delivery_state', '=', 'in_delivery')])
        for sale_order in sale_orders:
            delivery_feed = feed_obj.search([('feed_result_id', '=', sale_order.false_delivery_feed_id)], limit=1)
            if delivery_feed:
                if not delivery_feed.feed_result:
                    try:
                        delivery_feed.get_feed_submission_result()
                    except:
                        continue
                if delivery_feed.feed_result:
                    result = DictWrapper(delivery_feed.feed_result, '')
                    error_info = result.parsed.get('Message', {}).get('ProcessingReport', {}).get(
                        'ProcessingSummary', {}).get('MessagesWithError', {}).get('value', '')
                    if error_info == '0':
                        sale_order.amazon_false_delivery_state = 'done'
                    else:
                        sale_order.amazon_false_delivery_state = 'failed'
        print 'over'
