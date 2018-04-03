from openerp import fields,models,api

class account_fiscal_position(models.Model):
    _inherit = 'account.fiscal.position'
    
    origin_country_ept=fields.Many2one('res.country',string='Origin Country')
    
    @api.model
    def _get_fpos_by_region(self, country_id=False, state_id=False, zipcode=False, vat_required=False):
        if not country_id:
            return False
        base_domain = [('auto_apply', '=', True), ('vat_required', '=', vat_required)]
        if self.env.context.get('force_company'):
            base_domain.append(('company_id', '=', self.env.context.get('force_company')))
        null_state_dom = state_domain = [('state_ids', '=', False)]
        null_zip_dom = zip_domain = [('zip_from', '=', 0), ('zip_to', '=', 0)]

        if zipcode and zipcode.isdigit():
            zipcode = int(zipcode)
            zip_domain = [('zip_from', '<=', zipcode), ('zip_to', '>=', zipcode)]
        else:
            zipcode = 0

        if state_id:
            state_domain = [('state_ids', '=', state_id)]

        domain_country = base_domain + [('country_id', '=', country_id)]

        # Build domain to search records with exact matching criteria
        fpos = self.search(domain_country + state_domain + zip_domain, limit=1)
        # return records that fit the most the criteria, and fallback on less specific fiscal positions if any can be found
        if not fpos and state_id:
            fpos = self.search(domain_country + null_state_dom + zip_domain, limit=1)
        if not fpos and zipcode:
            fpos = self.search(domain_country + state_domain + null_zip_dom, limit=1)
        if not fpos and state_id and zipcode:
            fpos = self.search(domain_country + null_state_dom + null_zip_dom, limit=1)

        origin_country_ept = self._context.get('origin_country_ept',False)
        if not origin_country_ept:
            return fpos
        domain =[
            ('auto_apply', '=', True),
            '|',('origin_country_ept','=',origin_country_ept),('origin_country_ept','=',False),
            '|', ('vat_required', '=', False), ('vat_required', '=',True)]    
        if self.env.context.get('force_company'):
            domain.append(('company_id','=',self.env.context.get('force_company')))
        else:
            domain.append(('company_id','=',False))
        fiscal_position = self.search(domain + [('country_id', '=',country_id)], limit=1)
        if fiscal_position:
            return fiscal_position
        fiscal_position = self.search( domain + [('country_group_id.country_ids', '=',country_id)],limit=1)
        if fiscal_position:
            return fiscal_position
        fiscal_position = self.search(domain + [('country_id', '=', None), ('country_group_id', '=', None)],limit=1)
        if fiscal_position:
            return fiscal_position
        return fpos or False
