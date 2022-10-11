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
{
    'name': 'Tech Plus l10n it Sale',
    'version': '0.1',
    'category': 'Localisation/Italy',
    'description': """
OpenERP Italian Localization - Sale

Functionalities:

- Documento di trasporto e fattura accompagnatoria.
""",
    'author': 'Tech Plus srl',
    'website': 'http://www.techplus.it',
    'summary': 'DDT & Fattura accompagnatoria',
    'license': 'AGPL-3',
    'depends': [
        'stock',
        'sale',
        'sale_stock',
        'techplus_sale_stock_picking_out',
        'purchase',
        'account',
        'delivery',
        'report_aeroo_ooo',
        'techplus_l10n_it',
        'techplus_stock',
        'identity_documents',
        'techplus_stock_invoice_picking',
        'techplus_stock_picking_invoice_link',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/data.xml',
        'data/mail_thread_data.xml',
        'wizard/stock_picking_in_split_lines_wizard_view.xml',
        'wizard/stock_picking_out_split_margin_scheme_lines_view.xml',
        'wizard/fix_product_to_return_wizard_view.xml',
        'wizard/migrate_ddt_view.xml',
        'wizard/sale_order_gift_wizard_view.xml',
        'wizard/transport_document_wizard_view.xml',
        'wizard/price_update_wizard_view.xml',
        'wizard/stock_invoice_onshipping_view.xml',
        'wizard/customer_sales_report_view.xml',
        'wizard/customer_sales_sheet_view.xml',
        'wizard/kept_product_to_return_wizard_view.xml',
        'wizard/return_product_to_return_wizard_view.xml',
        'wizard/margin_scheme_invoice_wizard_view.xml',
        'wizard/change_move_return_date_wizard_view.xml',
        'wizard/set_reason_on_picking_moves_wizard_view.xml',
        'wizard/edit_stock_move_notes_wizard_view.xml',
        'wizard/change_sale_order_tax_wizard_view.xml',
        'wizard/product_replace_wizard_view.xml',
        'wizard/import_inventory_lines_wizard_view.xml',
        'wizard/lot_lock_create_wizard_view.xml',
        'wizard/lot_lock_disable_wizard_view.xml',
        'wizard/invoice_edit_shipping_info_wizard_view.xml',
        'wizard/sale_order_change_invoice_address_wizard_view.xml',
        'wizard/stock_location_evaluation_report_view.xml',
        'wizard/update_all_sale_order_contents_html_wizard_view.xml',
        'wizard/check_stock_move_lot_and_product_integrity_wizard_view.xml',
        'wizard/account_kept_product_to_return_wizard_view.xml',
        'wizard/stock_picking_in_set_invoice_state_wizard_view.xml',
        'report/report.xml',
        'report/techplus_l10n_it_sale_print_transport_document.xml',
        'data/mail.xml',
        'account_view.xml',
        'account_settings_view.xml',
        'account_voucher_view.xml',
        'custom_export_notification_view.xml',
        'picking_data.xml',
        'sale_view.xml',
        'sale_workflow.xml',
        'partner_view.xml',
        'invoice_view.xml',
        'product_view.xml',
        'product_to_return_view.xml',
        'stock_view.xml',
        'purchase_view.xml',
        'transport_document_view.xml',
        'transport_document_workflow.xml',
        'goods_loading_register_view.xml',
        'goods_loading_register_workflow.xml',
        'res_config_view.xml',
        'delivery_view.xml',
        'lot_lock_view.xml',
        'menu.xml',
    ],
    'css': [
        'static/src/css/style.css',
    ],
    'installable': False,
}
