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

from stock import MARGIN_SCHEME_MODES


class account_tax(Model):
    _inherit = "account.tax"

    _columns = {
        'purchase_print_name': fields.char('Purchase Print Name', size=128,
            translate=True),
    }

account_tax()


class account_fiscal_position(Model):
    _inherit = 'account.fiscal.position'

    _columns = {
        'is_margin_scheme': fields.boolean('Margin Scheme'),
        'sale_margin_scheme_tax_on_margin': fields.many2one('account.tax',
            string='Sale Margin Scheme Tax Used On Margin'),
        'sale_margin_scheme_tax_on_untaxed': fields.many2one('account.tax',
            string='Sale Margin Scheme Tax Used On Untaxed'),
        'purchase_margin_scheme_tax': fields.many2one('account.tax',
            string='Purchase Margin Scheme Tax'),
        'default_sale_journal_id': fields.many2one('account.journal',
            string='Default Sale Journal'),
        'default_purchase_journal_id': fields.many2one('account.journal',
            string='Default Purchase Journal'),
        'default_sale_refund_journal_id': fields.many2one('account.journal',
            string='Default Sale Refund Journal'),
        'default_purchase_refund_journal_id': fields.many2one('account.journal',
            string='Default Purchase Refund Journal'),
        'custom_export_notification_required': fields.boolean('Custom Export Notification Required',
            help='This field lets you search for invoices that require custom\'s export notification.'),
        'commodity_code_required': fields.boolean('Commodity Code Required'),
        'shipping_invoice': fields.boolean('Shipping Invoice'),
        'include_ivoice_copy_extra_ue': fields.boolean('Include Invoce Copy Extra UE'),
        'identity_document_required': fields.boolean('Identity Document Required',
            help='A valid identiy Document will be required on invoices linked to this fiscal position.'),
        'print_lot_ref_on_invoices': fields.boolean('Print lot reference on invoice lines'),
        'text_invoice_out': fields.text('Text to print on out invoices.'),
        'text_invoice_in': fields.text('Text to print on in invoices.'),
    }

    _defaults = {
        # 'margin_scheme_type': 'new',
        'custom_export_notification_required': False,
        'commodity_code_required': False,
        'shipping_invoice': False,
        'include_ivoice_copy_extra_ue': False,
    }

account_fiscal_position()