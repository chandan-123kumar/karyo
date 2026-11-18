"""Interactive investing research settings, independent of model inference."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation


LABELS = {
    'market': 'Market', 'currency': 'Currency', 'holding_period': 'Holding period',
    'experience': 'Experience', 'capital': 'Capital', 'max_loss': 'Total loss limit',
}


def show_investing_settings(parameters):
    print('Investing research settings')
    for key, label in LABELS.items():
        value = parameters.get(key)
        print(f'  {label}: {value if value is not None else "Not set"}')
    print('Capital and loss limit use the displayed currency. Loss limit is for the whole research portfolio, not per trade.')
    print('Use /investing setup to edit; /investing save to keep settings for future launches.')


class SetupCancelled(Exception):
    pass


def _answer(prompt):
    answer = input(prompt).strip()
    if answer.lower() == '/cancel':
        raise SetupCancelled
    return answer


def _choice(label, options, current):
    print(f'{label}: ' + ', '.join(f'{i}. {value}' for i, value in enumerate(options, 1)))
    while True:
        answer = _answer(f'{label} [{current or "Not set"}]: ')
        if not answer:
            return current
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        match = next((value for value in options if value.lower() == answer.lower()), None)
        if match:
            return match
        print('Choose a listed number or value, or press Enter to keep the current setting.')


def _amount(label, current, *, positive=False, maximum=None):
    while True:
        answer = _answer(f'{label} [{current if current is not None else "Not set"}] (number, or clear): ')
        if not answer:
            value = current
        elif answer.lower() == 'clear':
            return None
        else:
            try:
                value = float(Decimal(answer))
            except (InvalidOperation, ValueError, OverflowError):
                print('Enter a finite numeric amount without currency symbols or commas.')
                continue
        if value is None:
            return None
        try:
            number = Decimal(str(value))
            valid = number.is_finite() and (number > 0 if positive else number >= 0)
            valid = valid and (maximum is None or number <= Decimal(str(maximum)))
        except InvalidOperation:
            valid = False
        if valid:
            return float(value)
        print('Enter an amount greater than zero.' if positive else
              'Enter a nonnegative amount no greater than capital, if capital is set.')


def configure_investing(parameters):
    """Return a new settings object, or None on cancel. Do not change the input."""
    updated = deepcopy(parameters)
    print('Investing setup · Enter keeps a setting; /cancel discards this setup.')
    try:
        previous_market = updated.get('market') if isinstance(updated.get('market'), str) else None
        updated['market'] = _choice('Market', ['India', 'US', 'Other'], previous_market)
        if updated['market'] == 'Other':
            updated['market'] = _answer('Market name: ') or previous_market
        currency_default = updated.get('currency')
        if not isinstance(currency_default, str) or not (
                len(currency_default) == 3 and currency_default.isascii() and currency_default.isalpha()):
            currency_default = None
        elif currency_default:
            currency_default = currency_default.upper()
        if updated['market'] != previous_market or not currency_default:
            currency_default = {'India': 'INR', 'US': 'USD'}.get(updated['market'])
        while True:
            currency = _answer(f'Currency [{currency_default or "Not set"}] (3-letter code): ').upper() or currency_default
            if currency is None or (len(currency) == 3 and currency.isascii() and currency.isalpha()):
                break
            print('Enter a 3-letter currency code such as INR or USD.')
        if parameters.get('currency') and currency != parameters['currency']:
            updated.pop('capital', None)
            updated.pop('max_loss', None)
            print('Currency changed; re-enter amounts in the new currency. No conversion was applied.')
        updated['currency'] = currency
        updated['holding_period'] = _choice('Holding period',
            ['Intraday', 'Several days', 'Several weeks', 'Long-term'], updated.get('holding_period'))
        updated['experience'] = _choice('Experience',
            ['Beginner', 'Some experience', 'Experienced'], updated.get('experience'))
        updated['capital'] = _amount(f'Capital ({currency or "currency not set"})', updated.get('capital'), positive=True)
        updated['max_loss'] = _amount(f'Total loss limit ({currency or "currency not set"})',
            updated.get('max_loss'), maximum=updated['capital'])
        show_investing_settings(updated)
        if _answer('Apply these settings to this session? [Y/n]: ').lower() not in ('', 'y', 'yes'):
            return None
        return updated
    except SetupCancelled:
        return None
