odoo.define('web_b2b_dashborad', function (require) {
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

var mainDashboard = Widget.extend({
    template: 'WebB2Bdashborad',

    init: function(parent, data){
        return this._super.apply(this, arguments);
    },

    start: function(){
        return true;
    },
});



core.action_registry.add('web_b2b_dashboard.main', mainDashboard);

return {
    Dashboard: mainDashboard,
};

});
