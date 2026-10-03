"""Student ID card compositing: paste the student's photo (cropped to a circle) and their
details onto the official Orbit card design, server-side, and save a printable PNG.

The template PNG (static/invoices/id_cards/template.png) carries every fixed element — the
logo, the circle outline, the green swoosh, the divider line, the field labels ("ID No.:",
"Phone No.:", "Email:", "Address:") and the "Vaild Untill:" pill — nothing in it is drawn
here. This module only draws what changes per student: the photo and the values next to each
label. Positions below were measured directly off the approved template image (576x951 px)
pixel-by-pixel (where each label's text actually ends), not eyeballed — drawing a label text
of our own on top of the baked-in one produces visible double/ghosted text.
"""
import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont, ImageOps

CARD_W, CARD_H = 576, 951
TEMPLATE_PATH = os.path.join(settings.BASE_DIR, 'invoices', 'static', 'invoices', 'id_cards', 'template.png')
FONT_DIR = os.path.join(settings.BASE_DIR, 'invoices', 'static', 'invoices', 'fonts')

CIRCLE_CENTER = (288, 270)
CIRCLE_RADIUS = 140   # a touch inside the printed outline so the photo never overlaps the stroke

INK = (255, 255, 255)
PILL_INK = (10, 10, 10)

# x where each baked-in label's own text ends, plus a small gap — this is where the value starts.
ID_VALUE_X = 194
PHONE_VALUE_X = 227
EMAIL_VALUE_X = 194
ADDRESS_VALUE_X = 214
PILL_VALUE_X = 165

ORBIT_ADDRESS = ['211, Pinnacle Sheikh Zayed Road,', 'Al Barsha 1, Dubai, UAE']


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered(draw, text, cy, font, fill, max_width=None):
    if max_width and draw.textlength(text, font=font) > max_width:
        while len(text) > 3 and draw.textlength(text + '…', font=font) > max_width:
            text = text[:-1]
        text = text + '…'
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((CARD_W / 2 - w / 2 - bbox[0], cy), text, font=font, fill=fill)


def _value(draw, text, x, top, font, max_width, fill=INK):
    v = text
    if draw.textlength(v, font=font) > max_width:
        while len(v) > 3 and draw.textlength(v + '…', font=font) > max_width:
            v = v[:-1]
        v = v + '…'
    draw.text((x, top), v, font=font, fill=fill)


def generate_card_image(card):
    """Build the composited PNG for a StudentIDCard and return (ContentFile, errors).
    errors is a list of human messages for data that's missing but didn't stop the card
    (e.g. no phone on file) — the card still renders, just with that field left blank."""
    errors = []
    reg = card.registration
    bg = Image.open(TEMPLATE_PATH).convert('RGBA')

    # photo, cropped to a circle
    card.photo.open()
    photo = Image.open(card.photo)
    try:
        photo = ImageOps.exif_transpose(photo)
    except Exception:
        pass
    photo = photo.convert('RGBA')
    d = CIRCLE_RADIUS * 2
    photo = ImageOps.fit(photo, (d, d), Image.LANCZOS, centering=(0.5, 0.35))
    mask = Image.new('L', (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d, d), fill=255)
    bg.paste(photo, (CIRCLE_CENTER[0] - CIRCLE_RADIUS, CIRCLE_CENTER[1] - CIRCLE_RADIUS), mask)

    draw = ImageDraw.Draw(bg)
    name_font = _font('VeraBd.ttf', 32)
    course_font = _font('Vera.ttf', 17)
    value_font = _font('VeraBd.ttf', 15)
    pill_font = _font('VeraBd.ttf', 15)

    name = f'{reg.first_name} {reg.last_name}'.strip() or reg.registration_number
    _centered(draw, name, 574, name_font, INK, max_width=500)

    course_name = card.course.name if card.course else '-'
    _centered(draw, course_name, 624, course_font, INK, max_width=460)

    _value(draw, reg.registration_number, ID_VALUE_X, 698, value_font, CARD_W - ID_VALUE_X - 30)
    phone = reg.phone_no or ''
    if not phone:
        errors.append('No phone number on file — left blank on the card.')
    _value(draw, phone or '-', PHONE_VALUE_X, 723, value_font, CARD_W - PHONE_VALUE_X - 30)
    email = reg.email or ''
    if not email:
        errors.append('No email on file — left blank on the card.')
    _value(draw, email or '-', EMAIL_VALUE_X, 757, value_font, CARD_W - EMAIL_VALUE_X - 30)

    for i, line in enumerate(ORBIT_ADDRESS):
        draw.text((ADDRESS_VALUE_X, 787 + 19 * i), line, font=value_font, fill=INK)

    _value(draw, f'{card.valid_until:%d %b %Y}', PILL_VALUE_X, 888, pill_font, CARD_W - PILL_VALUE_X - 60, fill=PILL_INK)

    out = BytesIO()
    bg.convert('RGB').save(out, format='PNG', optimize=True)
    return ContentFile(out.getvalue(), name=f'id_card_{reg.registration_number.replace("/", "-")}.png'), errors
