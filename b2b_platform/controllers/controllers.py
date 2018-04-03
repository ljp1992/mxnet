# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale, TableCompute
from odoo.addons.website.models.website import slug
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.website_portal.controllers.main import website_account
import base64

import logging
import werkzeug

_logger = logging.getLogger(__name__)

PPG = 20  # Products Per Page
PPR = 4   # Products Per Row


class AuthSignupHomeNew(AuthSignupHome):

    @http.route('/web/signup', type='http', auth='public', website=True)
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                return super(AuthSignupHome, self).web_login(*args, **kw)
            except (SignupError, AssertionError), e:
                if request.env["res.users"].sudo().search([("login", "=", qcontext.get("login"))]):
                    qcontext["error"] = _("Another user is already registered using this email address.")
                else:
                    _logger.error(e.message)
                    # qcontext['error'] = _("Could not create a new account.")
                    qcontext['error'] = e.message

        return request.render('auth_signup.signup', qcontext)

    def get_auth_signup_qcontext(self):
        qcontext = super(AuthSignupHomeNew, self).get_auth_signup_qcontext()
        categ_obj = request.env['res.partner.category']
        if qcontext.get('categ'):
            categ_domain = [('qdoo_func', '=', qcontext.get('categ'))]
            qcontext['partner_categs'] = categ_obj.sudo().search_read(categ_domain, ['name'])

        def qdoo_check(s):
            return qcontext.get(s)

        qcontext['qdoo_check'] = qdoo_check
        return qcontext

    def do_signup(self, qcontext):
        '''写入res_partner category_id值  Modefied by 刘吉平 on 2018-01-03'''
        assert qcontext.get('password'), u"请输入密码！"
        super(AuthSignupHomeNew, self).do_signup(qcontext)
        new_user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))])
        category_ids = request.env['res.partner.category'].sudo().search([]).ids
        vals = {
            'qdoo_state': 'new',
            'qdoo_func': qcontext.get('categ', False),
            'mobile': qcontext.get('mobile', ''),
            'introduction': qcontext.get('introduction', ''),
            'category_id': [(6, False, category_ids)],
            'is_company': True,
            'supplier': True
        }
        new_user.partner_id.write(vals)

    # def do_signup(self, qcontext):
    #     assert qcontext.get('password'), u"请输入密码！"
    #     super(AuthSignupHomeNew, self).do_signup(qcontext)
    #     if qcontext.get('categ'):
    #         new_user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))])
    #         category_ids = []
    #         for key, value in qcontext.items():
    #             if key.startswith('partner_categ_') and value:
    #                 category_ids.append(int(value))
    #         vals = {
    #             'qdoo_state': 'new',
    #             'qdoo_func': qcontext.get('categ', False),
    #             'mobile': qcontext.get('mobile', ''),
    #             'introduction': qcontext.get('introduction', ''),
    #             'category_id': [(6, 0, category_ids)],
    #             'is_company': True,
    #             'supplier': True
    #         }
    #         new_user.partner_id.write(vals)
        # # if qcontext.get('categ'):
        # new_user = request.env['res.users'].sudo().search([('login', '=', qcontext.get('login'))])
        # category_ids = []
        # # for key, value in qcontext.items():
        # #     if key.startswith('partner_categ_') and value:
        # #         category_ids.append(int(value))
        # category_ids.append(1)
        # category_ids.append(2)
        # vals = {
        #     'qdoo_state': 'new',
        #     'qdoo_func': qcontext.get('categ', False),
        #     'mobile': qcontext.get('mobile', ''),
        #     'introduction': qcontext.get('introduction', ''),
        #     'category_id': [(6, 0, category_ids)],
        #     'is_company': True,
        #     'supplier': True
        # }
        # new_user.partner_id.write(vals)


class WebsiteAccountNew(website_account):
    @http.route(['/my/account'], type='http', auth='user', website=True)
    def details(self, redirect=None, **post):
        partner = request.env.user.partner_id
        values = {
            'error': {},
            'error_message': []
        }

        if post:
            filter_post = post.copy()
            category_ids = []
            for key, value in post.items():
                if key.startswith('partner_categ_'):
                    if value:
                        category_ids.append(int(value))
                    filter_post.pop(key)
            error, error_message = self.details_form_validate(filter_post)
            values.update({'error': error, 'error_message': error_message})
            values.update(post)
            if not error:
                values = {key: post[key] for key in self.MANDATORY_BILLING_FIELDS}
                values.update({key: post[key] for key in self.OPTIONAL_BILLING_FIELDS if key in post})
                values.update({'zip': values.pop('zipcode', '')})
                vals = values.copy()
                vals['category_id'] = [(6, 0, category_ids)]
                partner.sudo().write(vals)
                if redirect:
                    return request.redirect(redirect)
                return request.redirect('/my/home')

        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])

        categ_obj = request.env['res.partner.category']
        categ_domain = [('qdoo_func', '=', 'supplier')]
        partner_categs = categ_obj.sudo().search_read(categ_domain, ['name'])

        def qdoo_check(s):
            return values.get(s)

        values.update({
            'partner': partner,
            'countries': countries,
            'states': states,
            'has_check_vat': hasattr(request.env['res.partner'], 'check_vat'),
            'redirect': redirect,
            'partner_categs': partner_categs,
            'qdoo_check': qdoo_check
        })

        for categ in partner.category_id:
            values.update({'partner_categ_%s' % categ.id: 1})

        return request.render("website_portal.details", values)

    @http.route(['/my/account/image'], type='http', auth='user', website=True, csrf=False)
    def account_image(self, **kw):
        partner = request.env.user.partner_id
        partner.write({'image': base64.encodestring(kw['partner_img'].read())})
        return '1111'
