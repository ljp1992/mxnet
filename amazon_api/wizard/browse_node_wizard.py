# -*- encoding: utf-8 -*-

from odoo import api, fields, models, registry, _
from odoo.addons.amazon_ept_v10.amazon_emipro_api.mws import Reports,Products
from odoo.exceptions import UserError
import time, datetime, base64, csv, threading, sys
from StringIO import StringIO
from requests import request


class BrowseNodeWizard(models.TransientModel):
    _name = 'browse.node.wizard'





