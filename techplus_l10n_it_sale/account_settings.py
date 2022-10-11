# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus Account Deposit
#    Copyright (C) Ermanno Gnan (<ermannognan@gmail.com>).
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

import openerp.exceptions

from openerp.osv import fields
from openerp.osv.orm import Model, TransientModel

from openerp.tools.translate import _


class account_config_settings(TransientModel):
    _inherit = 'account.config.settings'
    _columns = {
        'margin_account_tax_for_purchase_receipts_id': fields.related('company_id', 'margin_account_tax_for_purchase_receipts_id', type='many2one', relation='account.tax',
            string='Margin Tax For Purchase Receipts'),
        'out_invoice_margin_scheme_default_fiscal_position': fields.related('company_id', 'out_invoice_margin_scheme_default_fiscal_position', type='many2one', relation='account.fiscal.position',
            string='Default Out Invoice Margin Scheme Fiscal Position', domain="[('is_margin_scheme', '!=', False)]"),
    }

    def onchange_company_id(self, cr, uid, ids, company_id, context=None):
        res = super(account_config_settings, self).onchange_company_id(
            cr, uid, ids, company_id, context=context)
        if company_id:
            company = self.pool.get('res.company').browse(
                cr, uid, company_id, context=context)
            res['value'].update({
                'margin_account_tax_for_purchase_receipts_id': company.margin_account_tax_for_purchase_receipts_id.id \
                    if company.margin_account_tax_for_purchase_receipts_id else None,
                'out_invoice_margin_scheme_default_fiscal_position': company.out_invoice_margin_scheme_default_fiscal_position.id \
                    if company.out_invoice_margin_scheme_default_fiscal_position else None,
            })
        else:
            res['value'].update({
                'margin_account_tax_for_purchase_receipts_id': None,
                'out_invoice_margin_scheme_default_fiscal_position': None,
            })
        res.setdefault('domain', {}).update({
                'margin_account_tax_for_purchase_receipts_id': [('company_id', '=', company_id)],
                'out_invoice_margin_scheme_default_fiscal_position': [('company_id', '=', company_id)],
            })
        return res