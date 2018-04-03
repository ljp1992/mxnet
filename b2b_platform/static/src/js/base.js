odoo.define('b2b_platform.my_account', function (require) {
    "use strict";

    var base = require('web_editor.base');

    if(!$('#partner_img_container').length) {
        return $.Deferred().reject("DOM doesn't contain '#partner_img_container'");
    }

    var $img = $('#partner_img_container img.partner_img');
    var img_src = $img.attr('src').split('?')[0];
    $('#partner_img_input').fileupload(
        {
            url: '/my/account/image',
            dataType: "json",
            multipart:true,
            done:function(e,data){
                $img.attr('src', img_src+'?unique='+Math.random());
            }
        }
    );
    var $btn = $('#partner_img_container .select_file_button');
    $btn.click(function(e) {
        $('#partner_img_input').click();
    });
});

odoo.define('b2b_platform.suppliers', function (require) {
    "use strict";

    var base = require('web_editor.base');

    if (!$('#suppliers_container').length) {
        return $.Deferred().reject("DOM doesn't contain '#suppliers_container'");
    }

    $('#supplier_search_form button').click(function(e){
        var action = $('#supplier_search_form').attr('action');
        var search = $('#supplier_search_form input').val();
        e.preventDefault();
        var new_href = '';
        if (action.indexOf('?')>-1) {
            new_href = action + '&search=' + search + '#suppliers_container';
        } else {
            new_href = action + '?search=' + search + '#suppliers_container';
        }
        window.location.href = new_href;
    });
});
