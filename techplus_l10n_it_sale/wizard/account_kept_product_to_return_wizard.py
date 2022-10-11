# -*- coding: utf-8 -*-
##############################################################################
#
#    Tech Plus l10n it Sale
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
from ..product_to_return import RETURN_TYPES

MODES = [
    ('create_out_invoices', 'create an out invoice gruped by partner for each entry.'),
    ('create_in_receipt', 'create an in receipt for the entry.'),
    ('in_invoice_add_lines', 'create an in invoice line for each entry.'),
    ('in_receipt_add_lnes', 'create a purchase receipt line for each entry.')
]

class account_kept_product_to_return_wizard(TransientModel):
    _name = "account.kept.product.to.return.wizard"

    def _get_view_id_ref(self, cr, uid, module, view):
        return self.pool.get('ir.model.data').get_object_reference(
            cr, uid, module, view)[1]

    _columns = {
        'accounting_mode': fields.selection(MODES, string='Accounting mode', required=True, readonly=True),
        'invoice_id': fields.many2one('account.invoice', string='Invoice', readonly=True),
        'voucher_id': fields.many2one('account.voucher', string='Invoice', readonly=True),
        'kept_product_to_return_ids': fields.many2many('kept.product.to.return',
            'account_kept_product_to_return_wizard_kept_product_to_return', 'wizard_id',
            'kept_product_to_return_id', string='Kept Products'),
    }

    def default_get(self, cr, uid, fields=None, context=None):
        res = {}
        kept_obj = self.pool.get('kept.product.to.return')
        if context.get('active_id') and context.get('active_model') == 'account.invoice':
            invoice = self.pool.get('account.invoice').browse(cr, uid, context.get('active_id'), context)
            if invoice.type != 'in_invoice':
                raise openerp.exceptions.Warning(_('This invoice type "%s" is not allowed.') % invoice.type)
            res.update({
                'invoice_id': context.get('active_id'),
                'accounting_mode': 'in_invoice_add_lines',
                'kept_product_to_return_ids': kept_obj.search(cr, uid, [
                        ('state', 'in', ('to_account', 'partial_accounted')),
                        ('partner_id', '=', invoice.partner_id.id),
                    ], context=context),
            })

        elif context.get('active_id') and context.get('active_model') == 'account.voucher':
            voucher = self.pool.get('account.voucher').browse(cr, uid, context.get('active_id'), context)
            if not voucher.partner_id:
                raise openerp.exceptions.Warning(_('The voucher must specify a partner in order to proceed.'))
            if voucher.type != 'purchase':
                raise openerp.exceptions.Warning(_('This voucher type "%s" is not allowed.') % voucher.type)
            res.update({
                'voucher_id': context.get('active_id'),
                'accounting_mode': 'in_receipt_add_lnes',
                'kept_product_to_return_ids': kept_obj.search(cr, uid, [
                        ('state', 'in', ('to_account', 'partial_accounted')),
                        ('partner_id', '=', voucher.partner_id.id),
                    ], context=context)
            })
        elif context.get('active_ids') or context.get('active_id') and context.get('active_model') == 'kept.product.to.return':
            k_ids = context.get('active_ids') or [context.get('active_id')]
            kept_products = self.pool.get('kept.product.to.return').browse(cr, uid, k_ids, context)
            if kept_products[0].type == 'outgoing':
                res['kept_product_to_return_ids'] = [p.id for p in kept_products if p.type == 'outgoing']
                res['accounting_mode'] = 'create_out_invoices'
            elif kept_products[0].type == 'incoming' and len(kept_products) == 1:
                res['kept_product_to_return_ids'] = [p.id for p in kept_products if p.type == 'incoming']
                res['accounting_mode'] = 'create_in_receipt'
        return res

    def proceed(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context)
        if wizard.invoice_id and wizard.accounting_mode == 'in_invoice_add_lines':
            invoice = wizard.invoice_id
            if wizard.invoice_id.state != 'draft':
                raise openerp.exceptions.Warning('Only draft invoices can be updated!')
            lines = []
            fpos = invoice.fiscal_position
            tax_lookup = {}
            account_lookup = {}
            for line in fpos.tax_ids:
                tax_lookup[line.tax_src_id.id] = line.tax_dest_id.id
            for line in fpos.account_ids:
                account_lookup[line.account_src_id.id] = line.account_dest_id.id
            for k in wizard.kept_product_to_return_ids:
                if k.product_id.property_account_expense:
                    account_id = k.product_id.property_account_expense.id
                elif k.product_id.categ_id.property_account_expense_categ:
                    account_id = k.product_id.categ_id.property_account_expense_categ.id
                else:
                    account_id = invoice.journal_id.default_debit_account_id.id \
                        if invoice.journal_id.default_debit_account_id else None
                tax_ids = [t.id for t in k.product_id.supplier_taxes_id]
                fpos_tax_ids = []
                for tax_id in tax_ids:
                    if tax_lookup.get(tax_id):
                        fpos_tax_ids.append(tax_lookup.get(tax_id))
                    else:
                        fpos_tax_ids.append(tax_id)
                if account_lookup.get(account_id):
                    account_id = account_lookup.get(account_id)
                lines.append((0, 0, {
                        'name': k.product_id.name,
                        'sequence': 1,
                        'account_id': account_id,
                        'price_unit': k.left_amount / (k.product_qty or 1),
                        'quantity': k.product_qty,
                        'uos_id': k.product_uom_id.id,
                        'product_id': k.product_id.id,
                        'invoice_line_tax_id': [(6, 0, fpos_tax_ids)],
                        'kept_product_id': k.id,
                        'lot_id': k.lot_id.id if k.lot_id else None,
                    }))
            wizard.invoice_id.write({'invoice_line': lines})
        elif wizard.voucher_id and wizard.accounting_mode == 'in_receipt_add_lnes':
            if wizard.voucher_id.state != 'draft':
                raise openerp.exceptions.Warning('Only draft receipts can be updated!')
            lines = []
            for k in wizard.kept_product_to_return_ids:
                if k.product_id.property_account_expense:
                    account_id = k.product_id.property_account_expense.id
                elif k.product_id.categ_id.property_account_expense_categ:
                    account_id = k.product_id.categ_id.property_account_expense_categ.id
                else:
                    account_id = invoice.journal_id.default_debit_account_id.id \
                        if invoice.journal_id.default_debit_account_id else None
                lines.append((0, 0, {
                    'product_id': k.product_id.id,
                    'sequence': 1,
                    'account_id': account_id,
                    'lot_id': k.lot_id.id if k.lot_id else None,
                    'type': 'dr',
                    'name': k.product_id.name,
                    'kept_product_id': k.id,
                    'amount': k.left_amount,
                    }))
            wizard.voucher_id.write({'line_ids': lines})
        elif wizard.accounting_mode == 'create_out_invoices':
            kept_obj = self.pool.get('kept.product.to.return')
            invoice_obj = self.pool.get('account.invoice')
            invoice_line_obj = self.pool.get('account.invoice.line')
            if not wizard.kept_product_to_return_ids:
                raise openerp.exceptions.Warning(_('No any kept product line has been found!'))
            k_lookup = {}
            for k in wizard.kept_product_to_return_ids:
                if k.type == 'outgoing':
                    k_lookup.setdefault(k.partner_id.id, []).append(k.id)
            for partner_id in k_lookup.keys():
                partner = self.pool.get('res.partner').browse(cr, uid, partner_id, context)
                invoice_vals = invoice_obj.default_get(cr, uid, [
                        'journal_id',
                        'currency_id',
                        'company_id',
                        'reference_type',
                        'check_total',
                        'internal_number',
                        'user_id',
                        'sent',
                    ], context)
                invoice_vals.update({
                        'partner_id': partner_id,
                        'account_id': partner.property_account_receivable.id,
                        'type': 'out_invoice',
                        'state': 'draft',
                    })
                invoice_id = invoice_obj.create(cr, uid, invoice_vals, context)
                for k in kept_obj.browse(cr, uid, k_lookup[partner_id], context):
                    if k.product_id.property_account_expense:
                        account_id = k.product_id.property_account_expense.id
                    elif k.product_id.categ_id.property_account_expense_categ:
                        account_id = k.product_id.categ_id.property_account_expense_categ.id
                    else:
                        account_id = invoice.journal_id.default_debit_account_id.id \
                            if invoice.journal_id.default_debit_account_id else None
                    invoice_line_obj.create(cr, uid, {
                            'invoice_id': invoice_id,
                            'name': k.product_id.name,
                            'sequence': 1,
                            'account_id': account_id,
                            'price_unit': k.left_amount / (k.product_qty or 1),
                            'quantity': k.product_qty,
                            'uos_id': k.product_uom_id.id,
                            'product_id': k.product_id.id,
                            'invoice_line_tax_id': [(6, 0, [t.id for t in k.product_id.taxes_id])],
                            'kept_product_id': k.id,
                            'lot_id': k.lot_id.id if k.lot_id else None,
                        }, context=context)
            form_view_id = self._get_view_id_ref(cr, uid, 'techplus_l10n_it_sale', 'invoice_form')
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.invoice',
                'view_mode': 'tree,form',
                'view_id': False,
                'views': [
                    (False, 'tree'),
                    (form_view_id, 'form'),
                ],
                'target': 'current',
            }
        elif wizard.accounting_mode == 'create_in_receipt':
            raise openerp.exceptions.Warning(
                _('This option has not been handled yet! If you need to create the receipt for a sale, \
                    you can create the receipt using the cart button that is displayed on the sale line.'))
        else:
            raise openerp.exceptions.Warning(_('Cannot handle this confifguration!'))
        return {
            'type': 'ir.actions.act_window_close',
        }