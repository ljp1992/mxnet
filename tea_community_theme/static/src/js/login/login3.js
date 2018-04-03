/**
 * Created by rain.wen on 2017-05-26.
 */

odoo.define('login3', function (require) {
    "use strict";
    var Login = function () {
        var handleLogin = function() {
            //数据库切换
            var currentdb = $("#db_list option:selected").val()
            $("#db_list").unbind('change');
            $(document).ready(function() {
                $("#db_list").change(function() {
                    if(this.value != currentdb)
                        window.location.href= '/web?db='+this.value;
                })
            });

            function format(db) {
                if (!db.id) {
                    return db.text;
                }
                var $db = $(
                    '<span><i class="fa fa-database"></i> ' + db.text + '</span>'
                );
                return $db;
            }

            if (jQuery().select2 && $('#db_list').size() > 0) {
                $("#db_list").select2({
                    placeholder: '<i class="fa fa-database"></i>',
                    templateResult: format,
                    templateSelection: format,
                    minimumResultsForSearch: -1,
                    width: '100%',
                    escapeMarkup: function(m) {
                        return m;
                    }
                });
            }

            $('.login-form input').keypress(function (e) {
                if (e.which == 13) {
                    if ($('.login-form').validate().form()) {
                        $('.login-form').submit();
                    }
                    return false;
                }
            });
        }


        return {
            init: function () {
                handleLogin();
            }
        };
    }();

    jQuery(document).ready(function() {
        Login.init();
    });

});