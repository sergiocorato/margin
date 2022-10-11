# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) Tech Plus srl (<http://www.techplus.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import openerp.addons.decimal_precision as dp

import openerp.exceptions

from openerp.osv import fields
from openerp.osv.orm import TransientModel

from openerp.tools.translate import _


class change_margin_scheme_invoce_line_wizard(TransientModel):
    _name = "change.margin.scheme.invoice.line.wizard"

    _columns = {
        'margin_line_id': fields.many2one('margin.scheme.invoice.line', string='Margin Invoice Line', required=True,
            readonly=True),
        'lot_id': fields.related('margin_line_id', 'lot_id', type='many2one', relation='stock.production.lot',
            string='Lot', readonly=True),
        'purchase_amount': fields.float('Purchase Amount', digits_compute=dp.get_precision('Account'), readonly=True),
        'amount': fields.float('Sale Amount', digits_compute=dp.get_precision('Account')),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        if context is None:
            context = {}
        active_id = context.get('active_id')
        margin_line = self.pool.get('margin.scheme.invoice.line').browse(cr, uid, active_id, context)
        return {
            'margin_line_id': active_id,
            'lot_id': margin_line.lot_id.id,
            'purchase_amount': margin_line.register_line_id.price_in,
            'amount': margin_line.amount,
        }

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        wizard.margin_line_id.update_amount(wizard.amount)
        wizard.margin_line_id.invoice_id.button_reset_taxes()
        return {
            'type': 'ir.actions.act_window_close',
        }


class add_margin_scheme_invoce_line_wizard(TransientModel):
    _name = "add.margin.scheme.invoice.line.wizard"

    _columns = {
        'invoice_id': fields.many2one('account.invoice', string='Invoice'),
        'register_line_id': fields.many2one('goods.loading.register.line', string='Register Entry', required=True),
        'purchase_amount': fields.related('register_line_id', 'price_in', type='float', string='Purchase Amount',
            readonly=True),
        'amount': fields.float('Sale Amount', digits_compute=dp.get_precision('Account')),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        if context is None:
            context = {}
        active_id = context.get('active_id')
        if not active_id:
            raise openerp.exceptions.Warning(
                _("Active id not found in context!"))
        return {
            'invoice_id': active_id,
        }

    def on_change_invoice_id(self, cr, uid, ids, invoice_id, context=None):
        invoice_obj = self.pool.get('account.invoice')
        domain = {'register_line_id': []}
        if invoice_id:
            invoice = invoice_obj.browse(cr, uid, invoice_id, context)
            if invoice.type == 'out_invoice':
                domain['register_line_id'] = [('state', '=', 'loaded'), ('return_line_id', '=', False)]
            elif invoice.type == 'out_refund':
                domain['register_line_id'] = [('state', '=', 'unloaded'), ('return_line_id', '=', False)]
        return {'domain': domain}

    def on_change_register_line_id(self, cr, uid, ids, line_id, context=None):
        if line_id:
            line = self.pool.get('goods.loading.register.line').browse(cr, uid,
                line_id, context)
            return {'value': {
                'purchase_amount': line.price_in,
                'amount': line.price_out or 0.0,
            }}
        return {'value': {
            'purchase_amount': 0.0,
            'amount': 0.0,
        }}

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        self.pool.get('account.invoice')._create_margin_invoice_lines(cr, uid, wizard.invoice_id,
            wizard.register_line_id, wizard.amount, [], False, context)
        return {
            'type': 'ir.actions.act_window_close',
        }
