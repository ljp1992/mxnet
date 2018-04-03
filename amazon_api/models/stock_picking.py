# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products,Feeds
import datetime, time

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    delivery_submission_id = fields.Char(help=u'feed.submission.history feed id')

    amazon_delivery_state = fields.Selection([
        ('in_delivery', u'亚马逊正在处理发货请求'),
        ('done', u'请求发货成功'),
        ('failed', u'请求发货失败'),
    ], string=u'亚马逊订单发货状态')

    @api.multi
    def do_new_transfer(self):
        result = super(StockPicking, self).do_new_transfer()
        self.request_amazon_delivery()
        return result

    @api.multi
    def request_amazon_delivery(self):
        '''亚马逊发货'''
        self.ensure_one()
        amazon_sale_order_obj = self.env['amazon.sale.order.ept']
        picking = self
        if picking.state != 'done':
            return
        message_id = 1
        message_info = ''
        for move in picking.move_lines:
            if move.state != 'done':
                continue
            sale_line = move.procurement_id.sale_line_id
            sale_order = sale_line.order_id
            amazon_order_item_id = sale_line.order_item_id
            if not amazon_order_item_id:
                continue
            carrier_name = picking.courrier_id.courrier or ''
            tracking_no = picking.carrier_tracking_ref or ''
            parcel = {
                'tracking_no': tracking_no,
                'qty': int(move.product_uom_qty),
                'amazon_order_item_id': amazon_order_item_id,
                'order_ref': sale_order.origin_doc,
                'carrier_name': carrier_name,
                'shipping_level_category': sale_order.shipment_service_level_category,
            }
            date_done = datetime.datetime.strptime(picking.date_done, "%Y-%m-%d %H:%M:%S")
            fulfillment_date_concat = date_done.strftime('%Y-%m-%dT%H:%M:%S') + '-00:00'
            message_info += amazon_sale_order_obj.create_parcel_for_multi_tracking_number(parcel, message_id,
                                                                                         fulfillment_date_concat)
            message_id += 1
        seller = sale_order.shop_id.amazon_seller_id
        instance = sale_order.shop_id.amazon_instance_id
        marketplaceids = [instance.market_place_id]
        xml_data = amazon_sale_order_obj.create_data(message_info, str(seller.merchant_id))
        proxy_data = seller.get_proxy_server()
        mws_obj = Feeds(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                        account_id=str(seller.merchant_id),
                        region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                        proxies=proxy_data)
        results = mws_obj.submit_feed(xml_data, '_POST_ORDER_FULFILLMENT_DATA_', marketplaceids=marketplaceids,
                                      instance_id=instance.id, model_name='stock.picking', record_id=self.id)
        FeedSubmissionId = results.parsed.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False)
        if FeedSubmissionId:
            picking.delivery_submission_id = FeedSubmissionId
            picking.amazon_delivery_state = 'in_delivery'
        return
