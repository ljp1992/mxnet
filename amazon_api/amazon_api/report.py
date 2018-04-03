# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys, copy
from StringIO import StringIO

class MyReports(Reports):

    def get_xml_browse_tree_data(self, start_date=None, end_date=None, RootNodesOnly=False, BrowseNodeId=False,
                                 marketplaceids=()):
        # if RootNodesOnly:
        #     RootNodesOnly = 'true'
        data = {
            'Action': 'RequestReport',
            'ReportType': '_GET_XML_BROWSE_TREE_DATA_',
            'StartDate': start_date,
            'EndDate': end_date,
            'RootNodesOnly': RootNodesOnly,
            'BrowseNodeId': BrowseNodeId,
        }
        data.update(self.enumerate_param('MarketplaceIdList.Id.', marketplaceids))
        result = self.make_request(data)
        return result