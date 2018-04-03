odoo.define('tea_community_theme.Sidebar', function (require) {
    "use strict";

    var core = require('web.core');
    var session = require('web.session');
    var Widget = require('web.Widget');

    $(function(){
        (function ($) {
            $.delDebug = function (url) {
                var str = url.match(/web(\S*)#/);
                url = url.replace("str/g","");
                return url;
            }
            $.addDebug = function (url) {
                url = url.replace(/(.{4})/,"$1?debug");
                return url;
            }
            $.addDebugWithAssets = function (url) {
                url = url.replace(/(.{4})/,"$1?debug=assets");
                return url;
            }
        })(jQuery);

        $("#sidebar a").each(function(){
            var url = $(this).attr('href');
            if (session.debug ==false)
                $(this).attr('href',$.delDebug(url));
            if (session.debug ==1)
                $(this).attr('href',$.addDebug(url));
            if (session.debug =='assets')
                $(this).attr('href',$.addDebugWithAssets(url));
        });

    });


    // var Sidebar = function () {
    //
    //     var handleLogin = function() {
    //
    //     }
    //
    //     var getUrlParam = function (name) {
    //         var reg = new RegExp("(^|&)" + name + "=([^&]*)(&|$)");
    //         var r = window.location.hash.substr(1).match(reg);
    //         if (r != null) return unescape(r[2]); return null;
    //     }
    //
    //     var getMenu = function () {
    //         return getUrlParam('menu_id');
    //     }
    //
    //     var setActive = function () {
    //         $("#sidebar>li").each(function () {
    //             if($(this).attr("data-menu") == getMenu())
    //                 $(this).addClass('active');
    //             else
    //                 $(this).removeClass('active');
    //         })
    //     }
    //
    //     return {
    //         init: function () {
    //             setActive();
    //         }
    //     };
    // }();
    //
    // jQuery(document).ready(function() {
    //     Sidebar.init();
    // });
});


