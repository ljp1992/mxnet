# -*- encoding: utf-8 -*-

from odoo import models, fields, api, registry
from odoo.exceptions import UserError
import threading, time

class SyncProductWizard(models.TransientModel):
    _name = 'sync.product.wizard'

    @api.multi
    def get_product_data(self):
        '''获取产品数据'''
        self.ensure_one()
        record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
        if record.instance_id.down_sync_product_get_data:
            raise UserError(u'后台已执行，请耐心等待！')
        record.instance_id.down_sync_product_get_data = True
        t = threading.Thread(target=self.get_product_data_thread)
        t.start()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def get_product_data_thread(self):
        '''获取产品数据'''
        try:
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.get_product_data_start()
                self._cr.commit()
                self._cr.close()
        except Exception,e:
            self._cr.commit()
            self._cr.close()
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.write({'order_line': [(0, 0, {'message': str(e), 'type': 'get_data'})]})
                self._cr.commit()
                self._cr.close()
        finally:
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.instance_id.down_sync_product_get_data = False
                self._cr.commit()
                self._cr.close()

    @api.multi
    def create_update_product(self):
        '''创建／更新产品'''
        self.ensure_one()
        record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
        if record.instance_id.down_sync_product_create_update:
            raise UserError(u'后台已执行，请耐心等待！')
        record.instance_id.down_sync_product_create_update = True
        t = threading.Thread(target=self.create_update_product_thread)
        t.start()
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def create_update_product_thread(self):
        '''创建／更新产品'''
        try:
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.create_update_product_start()
                self._cr.commit()
                self._cr.close()
        except Exception, e:
            self._cr.commit()
            self._cr.close()
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.write({'order_line': [(0, 0, {'message': str(e), 'type': 'create_update'})]})
                self._cr.commit()
                self._cr.close()
        finally:
            with api.Environment.manage():
                new_cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=new_cr))
                record = self.env[self._context.get('active_model')].browse(self._context.get('active_id'))
                record.instance_id.down_sync_product_create_update = False
                self._cr.commit()
                self._cr.close()

