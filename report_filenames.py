"""Portable names for downloaded HTML reports."""
import re
import unicodedata

MONTHS = ('januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli',
          'august', 'september', 'oktober', 'november', 'dezember')


def wave_period(wave, first_date):
    month = r'(0?[1-9]|1[0-2])'
    year = r'((?:19|20)\d{2})'
    # A July wave can open in June. Prefer the reported wave over answer dates.
    iso = re.search(r'(?<!\d)' + year + r'[-_. /]' + month + r'(?!\d)', wave)
    if iso:
        return f'{iso[1]}_{int(iso[2]):02d}'
    reverse = re.search(r'(?<!\d)' + month + r'[-_. /]' + year + r'(?!\d)', wave)
    if reverse:
        return f'{reverse[2]}_{int(reverse[1]):02d}'
    label = wave.casefold().replace('maerz', 'märz').replace('mrz', 'märz')
    words = re.findall(r'[^\W\d_]+', label)
    wave_year = re.search(r'(?<!\d)' + year + r'(?!\d)', wave)
    date = re.match(r'(\d{4})-(\d{2})', first_date or '')
    y = wave_year[1] if wave_year else date[1] if date else '0000'
    for number, name in enumerate(MONTHS, 1):
        if name in words or name[:3] in words or (number == 9 and 'sept' in words):
            return f'{y}_{number:02d}'
    return f'{y}_{date[2] if date else "00"}'


def report_filename(period, unit):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '_', unicodedata.normalize('NFC', unit))
    name = name.encode('utf-8')[:220].decode('utf-8', errors='ignore').strip(' .') or 'OE'
    return f'{period}_Puls_{name}.html'
