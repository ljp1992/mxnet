odoo.define('add_button_inventory_import.add_tree_view_button', function (require) {
    "use strict";

    var show_button_model = ['product.product'];//哪些模型显示导入按钮
    var ListView = require('web.ListView');

    ListView.include({
        render_buttons: function () {
            var self = this;
            this._super.apply(this, arguments);
            var tree_model = this.dataset.model;
            for(var i=0; i<show_button_model.length; i++) {
                if (tree_model == show_button_model[i]){
                    var button2 = $("<button type='button' class='btn btn-sm btn-default abc'>导入库存</button>")
                        .click(this.proxy('popup_import_inventory_wizard'));
                    this.$buttons.append(button2);
                }
            }
        },
        popup_import_inventory_wizard: function () {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'import.inventory.wizard',
                views: [[false, 'form']],
                view_mode: "form",
                view_type: 'form',
                view_id: 'import_inventory_wizard_form',
                target: 'new',
            });
        },
    });

});
