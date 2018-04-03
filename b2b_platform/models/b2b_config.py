# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.osv import osv
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError


class b2b_config_settings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.multi
    def execute(self):
        self.ensure_one()
        if not self.env.user.has_group('b2b_platform.group_qdoo_distributor_manager'):
            raise UserError("只有管理员才允许修改配置参数")

        self = self.with_context(active_test=False)
        classified = self._get_classified_fields()

        # default values fields
        IrValues = self.env['ir.values'].sudo()
        for name, model, field in classified['default']:
            if isinstance(self[name], models.BaseModel):
                if self._fields[name].type == 'many2one':
                    value = self[name].id
                else:
                    value = self[name].ids
            else:
                value = self[name]
            IrValues.set_default(model, field, value)

        # group fields: modify group / implied groups
        for name, groups, implied_group in classified['group']:
            if self[name]:
                groups.write({'implied_ids': [(4, implied_group.id)]})
            else:
                groups.write({'implied_ids': [(3, implied_group.id)]})
                implied_group.write({'users': [(3, user.id) for user in groups.mapped('users')]})

        # other fields: execute all methods that start with 'set_'
        for method in dir(self):
            if method.startswith('set_'):
                getattr(self, method)()

        # module fields: install/uninstall the selected modules
        to_install = []
        to_uninstall_modules = self.env['ir.module.module']
        lm = len('module_')
        for name, module in classified['module']:
            if self[name]:
                to_install.append((name[lm:], module))
            else:
                if module and module.state in ('installed', 'to upgrade'):
                    to_uninstall_modules += module

        if to_uninstall_modules:
            to_uninstall_modules.button_immediate_uninstall()

        action = self._install_modules(to_install)
        if action:
            return action

        if to_install or to_uninstall_modules:
            # After the uninstall/install calls, the registry and environments
            # are no longer valid. So we reset the environment.
            self.env.reset()
            self = self.env()[self._name]
        config = self.env['res.config'].next() or {}
        if config.get('type') not in ('ir.actions.act_window_close',):
            return config

        # force client-side reload (update user menu and current view)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }