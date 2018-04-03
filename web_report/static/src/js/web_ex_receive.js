odoo.define('web_ex_receive', function (require) {
"use strict";

var core = require('web.core');
var Widget = require('web.Widget');
var Model = require('web.Model');
var session = require('web.session');
var PlannerCommon = require('web.planner.common');
var framework = require('web.framework');
var webclient = require('web.web_client');
var PlannerDialog = PlannerCommon.PlannerDialog;

var QWeb = core.qweb;
var _t = core._t;

var exDashboard = Widget.extend({
    template: 'WebExReceive',

    init: function(parent, data){
        this._super.apply(this, arguments);
        this.user_model = new Model('res.users');
    },

    start: function(){
        this._super.apply(this, arguments);
        var self = this;
        this.user_model.query(['login', 'exchange_token'])
            .filter([['id', '=', session.uid]])
            .limit(1)
            .all().then(function (users) {
                var urlstr="http://tmh.mxnet.cn/#!/commonBox/login?login_account="
                urlstr = urlstr+users[0].login+"&password="+users[0].exchange_token
                console.log(urlstr);
                $("iframe").attr("src",urlstr);
        });
    },

});

core.action_registry.add('web_ex_receive.main', exDashboard);

return {
    Dashboard: exDashboard,
};

});
