# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n it Sale
#    Copyright (C) Tech Plus Project (<http://www.techplus.it>).
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

import datetime
import openerp.exceptions

from openerp.tools.translate import _

from openerp.osv import orm, fields

class l10n_it_sale_settings(orm.TransientModel):
    _name = 'l10n.it.sale.settings'
    _inherit = 'res.config.settings'

    _columns = {
        'group_margin_scheme': fields.boolean(
            "Allow setting the margin scheme type on invoices and receipts",
            implied_group='techplus_l10n_it_sale.group_margin_scheme',
            help="Allows to set the margin scheme type on invoices and "
            "receipts."),
        'def_stock_move_transportation_reason_required': fields.boolean(
            'Require transportation reason on stock moves'),
    }

    def get_default_def_stock_move_transportation_reason_required(self, cr,
        uid, fields, context=None):
        obj = self.pool.get('ir.config_parameter').get_param(cr, uid,
            'techplus_l10n_it_sale.def_stock_move_transportation_reason_required')
        obj = obj == 'True'
        return {'def_stock_move_transportation_reason_required': obj}

    def set_def_stock_move_transportation_reason_required(self, cr, uid, ids,
        context=None):
        config = self.browse(cr, uid, ids[0], context=context)
        self.pool.get('ir.config_parameter').set_param(cr, uid,
            'techplus_l10n_it_sale.def_stock_move_transportation_reason_required',
            'True' if config.def_stock_move_transportation_reason_required else 'False')


class account_config_settings(orm.TransientModel):
    _inherit = 'account.config.settings'

    _columns = {
        'out_invoice_auto_keep_sold_product_to_return': fields.related('company_id',
            'out_invoice_auto_keep_sold_product_to_return', type='boolean',
            string="Auto keep sold product to return out invoices",
            help='A new kept product to return will be created any time a product to return lot will be found on a ' \
                 'confirmed out invoice line.'),
    }

    def onchange_company_id(self, cr, uid, ids, company_id, context=None):
        res = super(account_config_settings, self).onchange_company_id(cr, uid, ids, company_id, context=context)
        if company_id:
            company = self.pool.get('res.company').browse(
                cr, uid, company_id, context=context)
            res['value'].update({
                'out_invoice_auto_keep_sold_product_to_return': company.out_invoice_auto_keep_sold_product_to_return,
            })
        else:
            res['value'].update({
                'out_invoice_auto_keep_sold_product_to_return': False,
            })
        return res