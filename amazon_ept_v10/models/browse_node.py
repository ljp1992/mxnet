from openerp import models, fields,api, _
from openerp.exceptions import Warning

class amazon_browse_node_ept(models.Model):
    _name="amazon.browse.node.ept"
    
    @api.multi
    def name_get(self):
        def get_names(cat):
            """ Return the list [cat.name, cat.parent_id.name, ...] """
            res = []
            while cat:
                res.append(cat.name)
                cat = cat.parent_id
            return res

        return [(cat.id, " / ".join(reversed(get_names(cat)))) for cat in self]

    @api.one
    def _get_full_name(self):
        for browse_node in self:
            full_name=[]
            full_name.append(browse_node.name)                      
            temp_browse_node=browse_node
            while True:
                parent_id=temp_browse_node.parent_id and temp_browse_node.parent_id.id                
                if parent_id:                
                    parent_node=temp_browse_node.search([('id','=',parent_id)])
                    full_name.append(parent_node.name)
                    temp_browse_node=parent_node                
                else:                    
                    break
                
            browse_node.full_name_ept='/'.join(reversed(full_name))                                                                  
                
    name = fields.Char(size=256, string='Name', required=True)
    ama_category_code = fields.Char(size=20, string='Amazon Category Code')
    parent_id = fields.Many2one('amazon.browse.node.ept', string='Parent')
    odoo_category_id = fields.Many2one('product.category', string='Odoo Category')
    country_id=fields.Many2one('res.country',string='Country')
    is_root_category=fields.Boolean("Ancestor Exist",default=False)
    full_name_ept=fields.Char(compute=_get_full_name,string="Full Name")
    

    """Here We have check Ancestor exist or not if exist then we update it or create it"""    
    @api.model
    def check_ancestor_exist_or_not(self,result,node):
        if not result.ancestor:
            return True        
        browse_node_ancestor=self.search([
                                    ('name','=',result.ancestor.name),
                                    ('ama_category_code','=',result.ancestor.id),
                                    ('country_id','=',node.country_id.id),
                                    ('parent_id','=',node.id)                                                               
                                    ]
                                   )        
        vals={}                
        if not browse_node_ancestor:
            vals.update({
                         'ama_category_code':result.ancestor.id,
                         'name':result.ancestor.name,
                         'country_id':node.country_id.id,
                         'parent_id':node.id,
                         'is_root_category':True
                         })
            browse_node_ancestor=self.create(vals)
        else:            
            vals.update({
                     'ama_category_code':result.ancestor.id,
                     'name':result.ancestor.name,
                     })
            browse_node_ancestor.write(vals)
        return browse_node_ancestor
    
    @api.model
    def check_children_exist_or_not(self,children,node,parent_id):
        child_node=self.search([('ama_category_code','=',children.id),
                                    ('name','=',children.name),
                                    ('country_id','=',node.country_id.id),
                                    ('parent_id','=',parent_id)
                                    ])
        vals={}
        if not child_node:                                  
            vals.update(
                        {
                         'ama_category_code':children.id,
                         'name':children.name,
                         'country_id':node.country_id.id,
                         'parent_id':parent_id
                         })
            self.create(vals)
        else:
            vals.update(
                        {
                         'ama_category_code':children.id,
                         'name':children.name,
                         })
            child_node.write(vals)
        return child_node  
    
    @api.multi
    def unlink(self):        
        record=self.search([('parent_id','in',self.ids)])        
        if not record:        
            return super(amazon_browse_node_ept,self).unlink()
        raise Warning(_("You can not delete parent category"))
    