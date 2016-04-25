# This file is part of the sale_return module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['SaleLine', 'ReturnSale']
_RETURN_STATES = ['cancel', 'draft', 'quotation']


class SaleLine:
    __name__ = 'sale.line'
    __metaclass__ = PoolMeta

    origin = fields.Reference('Origin', selection='get_origin', select=True,
        states={
            'readonly': Eval('_parent_sale', {}
                ).get('state') != 'draft',
            })

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return [cls.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]


class ReturnSale:
    __name__ = 'sale.return_sale'
    __metaclass__ = PoolMeta

    def do_return_(self, action):
        # Overwrite return sale wizard. Not call super
        # Total qty line is calculate according other sales returned
        pool = Pool()
        Sale = pool.get('sale.sale')
        Line = pool.get('sale.line')

        sales = Sale.browse(Transaction().context['active_ids'])
        sales_to_return = [sale for sale in sales \
                if sale.state not in _RETURN_STATES]
        if not sales_to_return:
            return
        return_sales = Sale.copy(sales_to_return)

        returned_lines = Line.search([
            ('origin', 'in', [
                str(line) for sale in sales for line in sale.lines]),
            ])

        returned_origin = {}
        for line in returned_lines:
            if line.origin in returned_origin:
                returned_origin[line.origin] += [line]
            else:
                returned_origin[line.origin] = [line]

        for return_sale, sale in zip(return_sales, sales):
            return_sale.origin = sale
            for line in sale.lines:
                if not line.type == 'line':
                    continue

                if line in returned_origin:
                    total_returned = 0
                    for l in returned_origin[line]:
                        if l.quantity >= 0:
                            total_returned -= l.quantity
                        else:
                            total_returned += l.quantity
                    if total_returned  * -1 >= line.quantity:
                        quantity = 0
                    else:
                        quantity = -(line.quantity + total_returned)
                else:
                    quantity = line.quantity * -1

                for return_line in return_sale.lines:
                    if line.quantity == return_line.quantity \
                            and line.description == return_line.description:
                        return_line.origin = line
                        return_line.quantity = quantity

            return_sale.lines = return_sale.lines  # Force saving
        Sale.save(return_sales)

        data = {'res_id': [s.id for s in return_sales]}
        if len(return_sales) == 1:
            action['views'].reverse()
        return action, data
