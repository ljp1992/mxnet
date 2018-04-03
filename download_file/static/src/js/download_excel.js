odoo.define('download_file.import_ljp', function (require) {
    "use strict";

    var core = require('web.core');
    var Model = require('web.Model');

    var download_file_js = function (element, action) {
        console.log(action.context);
        var model = action.context.model;
        var id = action.context.order_id;
        var url = '/web/binary/download_document/?model='+model+'&id='+id;
        console.log(url);
        window.location.href = url;
    };

    core.action_registry.add('download_file', download_file_js);
});