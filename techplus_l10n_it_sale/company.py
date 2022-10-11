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

import openerp.exceptions

from openerp.osv import fields
from openerp.osv.orm import Model

from openerp.tools.translate import _


class res_company(Model):
    _inherit = "res.company"

    _columns = {
        'out_invoice_auto_keep_sold_product_to_return': fields.boolean(
            string="Auto keep sold product to return out invoices",
            help='A new kept product to return will be created any time a product to return lot will be found on a ' \
                 'confirmed out invoice line.'),
        'margin_account_tax_for_purchase_receipts_id': fields.many2one(
            'account.tax', string='Margin Tax For Purchase Receipts'),
        'out_invoice_margin_scheme_default_fiscal_position': fields.many2one('account.fiscal.position', string='Default Out Invoice Margin Scheme Fiscal Position', domain="[('is_margin_scheme', '!=', False)]"),
    }

    _defaults = {
        'out_invoice_auto_keep_sold_product_to_return': True,
    }