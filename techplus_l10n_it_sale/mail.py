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



class mail_compose_message(Model):
    _inherit = 'mail.compose.message'

    def send_mail(self, cr, uid, ids, context=None):
        context = context or {}
        if context.get('default_model') == 'kept.product.to.return' and context.get('default_res_id') and \
           context.get('mark_notification_as_sent'):
            context = dict(context, mail_post_autofollow=True)
            self.pool.get('kept.product.to.return').write(cr, uid, context['default_res_id'], {
                    'notification_sent': True,
                }, context)
        return super(mail_compose_message, self).send_mail(cr, uid, ids, context=context)
