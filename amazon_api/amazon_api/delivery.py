# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import MWS
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO

class Delivery(MWS):

    URI = '/FulfillmentOutboundShipment/2011-10-01'
    VERSION = '2011-10-01'
    NS = '{http://mws.amazonservices.com/schema/FulfillmentOutboundShipment/2011-10-01}'

    def create_fulfillment_order(self, order):
        data = {
            'Action': 'CreateFulfillmentOrder',
            'SellerFulfillmentOrderId': order.name,
            'DisplayableOrderId': order.name,
            'DisplayableOrderDateTime': datetime.datetime.now().strftime("%Y-%m-%d"),
            'DisplayableOrderComment': 'DisplayableOrderComment ljp',
            'ShippingSpeedCategory': 'Standard',
            'DestinationAddress.name': order.partner_id.partner_shipping_id.name,
            'DestinationAddress.Line1': order.e_order_address.name,
            'Items': '',
        }
        # data.update(self.enumerate_param('IdList.Id.', ids))
        print 'data:', data
        return
        result = self.make_request(data)
        # print result

