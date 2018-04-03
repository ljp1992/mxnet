# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products,Feeds
import datetime, time


skus = [u'18012826DAAG-002']

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_currency = fields.Char(related='currency_id_amazon.symbol', store=False)
    freight_currency = fields.Char(related='currency_id_amazon.symbol', store=False)
    commission_currency = fields.Char(related='currency_id_amazon.symbol', store=False)
    false_delivery_feed_id = fields.Char(help=u'feed.submission.history feed id')

    e_order_amount = fields.Float(string=u'订单金额')
    e_order_freight = fields.Float(compute='get_e_order_freight', store=False, string=u'运费')
    e_order_commission = fields.Float(compute='get_e_order_commission', store=False, string=u'佣金')

    currency_id_amazon = fields.Many2one('res.currency', string=u'订单币种')

    delivery_mode = fields.Selection([('MFN', u'自发货'), ('FBA', u'FBA')], u'运输方式', default='MFN')
    # shipping_speed_categ = fields.Selection([
    #     ('Standard', u'标准配送方式'),
    #     ('Expedited', u'加急配送方式'),
    #     ('Priority', u'优先配送方式'),
    #     ('ScheduledDelivery', u'预约配送方式'),
    #     ('Expedited', u'加急配送方式'),
    #     ('Expedited', u'加急配送方式'),
    #     ('Expedited', u'加急配送方式'),
    #     ('Expedited', u'加急配送方式'),
    # ], string=u'配送方式', default='MFN')
    shipment_service_level_category=fields.Selection([
        ('Expedited','Expedited'),
        ('NextDay','NextDay'),
        ('SecondDay','SecondDay'),
        ('Standard','Standard'),
        ('FreeEconomy','FreeEconomy')], string=u"Shipment Service Level Category", default='Standard')
    amazon_state = fields.Selection([
        ('PendingAvailability', u'PendingAvailability'),
        ('Pending', u'Pending'),
        ('Unshipped', u'Unshipped'),
        ('PartiallyShipped', u'PartiallyShipped'),
        ('Shipped', u'Shipped'),
        ('InvoiceUnconfirmed', u'InvoiceUnconfirmed'),
        ('Canceled', u'Canceled'),
        ('Unfulfillable', u'Unfulfillable'),
    ], string=u'亚马逊订单状态')
    amazon_false_delivery_state = fields.Selection([
        ('in_delivery', u'亚马逊正在处理发货请求'),
        ('done', u'请求发货成功'),
        ('failed', u'请求发货失败'),
    ], string=u'亚马逊订单发货状态')

    @api.multi
    def get_e_order_freight(self):
        '''计算运费'''
        for record in self:
            e_order_freight = 0
            for line in record.order_line:
                e_order_freight += (line.amazon_shipping_price - line.amazon_shipping_discount -
                                    line.amazon_shipping_tax)
            record.e_order_freight = e_order_freight

    @api.multi
    def get_e_order_commission(self):
        '''计算佣金'''
        for record in self:
            record.e_order_commission = record.e_order_amount * 0.15

    @api.multi
    def create_courier_and_order(self):
        for order in self:
            order.act_carrier = u'Guo Mao'
            order.act_waybill = str(datetime.datetime.now())

    @api.multi
    def btn_ship(self):
        '''假发货'''
        self.ensure_one()
        self.create_courier_and_order()
        result = super(SaleOrder, self).btn_ship()
        amazon_sale_order_obj = self.env['amazon.sale.order.ept']
        message_id = 1
        message_info = ''
        carrier_name = self.act_carrier or ''
        tracking_no = self.act_waybill or ''
        fulfillment_date_concat = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '-00:00'
        for sale_line in self.order_line:
            amazon_order_item_id = sale_line.order_item_id
            if not amazon_order_item_id:
                continue
            parcel = {
                'tracking_no': tracking_no,
                'qty': int(sale_line.product_uom_qty),
                'amazon_order_item_id': amazon_order_item_id,
                'order_ref': self.origin_doc,
                'carrier_name': carrier_name,
                'shipping_level_category': self.shipment_service_level_category,
            }
            message_info += amazon_sale_order_obj.create_parcel_for_multi_tracking_number(parcel, message_id,                                                             fulfillment_date_concat)
            message_id += 1
        seller = self.shop_id.amazon_seller_id
        instance = self.shop_id.amazon_instance_id
        marketplaceids = [instance.market_place_id]
        xml_data = amazon_sale_order_obj.create_data(message_info, str(seller.merchant_id))
        proxy_data = seller.get_proxy_server()
        mws_obj = Feeds(access_key=str(seller.access_key), secret_key=str(seller.secret_key),
                        account_id=str(seller.merchant_id),
                        region=seller.country_id.amazon_marketplace_code or seller.country_id.code,
                        proxies=proxy_data)
        results = mws_obj.submit_feed(xml_data, '_POST_ORDER_FULFILLMENT_DATA_', marketplaceids=marketplaceids,
                                      instance_id=instance.id, model_name='sale.order', record_id=self.id)
        FeedSubmissionId = results.parsed.get('FeedSubmissionInfo', {}).get('FeedSubmissionId', {}).get('value', False)
        if FeedSubmissionId:
            self.false_delivery_feed_id = FeedSubmissionId
            self.amazon_false_delivery_state = 'in_delivery'
        return result
