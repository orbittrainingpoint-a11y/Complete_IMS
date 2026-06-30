from django import template
import json
from decimal import Decimal

register = template.Library()

@register.filter(name='json_script')
def json_script(value, arg):
    try:
        # If value is already a string, try to parse it as JSON
        if isinstance(value, str):
            return value
        
        # If it's a QuerySet or list, serialize it
        return json.dumps([{
            'course_name': item.course.name if item.course else '',
            'unit_price': float(item.unit_price),
            'quantity': item.quantity,
            'vat_rate': float(item.vat_rate)
        } for item in value])
    except Exception as e:
        # If there's any error, return an empty JSON array
        return '[]'

@register.filter(name='quotation_json_script')
def quotation_json_script(value, arg):
    try:
        # If value is already a string, try to parse it as JSON
        if isinstance(value, str):
            return value
        
        # If it's a QuerySet or list, serialize it
        return json.dumps([{
            'course_name': item.course.name if item.course else '',
            'rate': float(item.course.rate),
            'duration': float(item.duration),
            'number_of_persons': float(item.number_of_persons)
        } for item in value])
    except Exception as e:
        # If there's any error, return an empty JSON array
        return '[]'
    
@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0 

@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0 

@register.filter
def add(value, arg):
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return 0 

@register.filter
def divide(value, arg):
    return float(value) / float(arg)

@register.filter(name='calculate_course_price')
def calculate_course_price(course_rate, discount):
    try:
        rate = float(course_rate)
        discount_percent = float(discount)
        vat_rate = 0.05  # 5% VAT

        discounted_price = rate - (rate * discount_percent / 100)
        price_with_vat = discounted_price + (discounted_price * vat_rate)

        return round(price_with_vat, 2)
    except (ValueError, TypeError):
        return 0

@register.simple_tag
def calculate_total_price(registration_courses):
    total = 0
    for course in registration_courses:
        course_price = calculate_course_price(course.price, course.discount)
        total += course_price
    return round(total, 2)

@register.filter
def get_item(lst, i):
    try:
        return lst[int(i)]
    except:
        return None

@register.simple_tag(takes_context=True)
def calculate_running_due(context, invoice, forloop_counter):
    if forloop_counter == 1:
        # For the first invoice, initialize running_due with total_amount
        context['running_due'] = invoice.total_amount
    else:
        # For subsequent invoices, use the previous running_due
        context['running_due'] = context.get('running_due', Decimal('0'))
    
    # Calculate the adjusted amount_paid (including 5% increase)
    adjusted_amount_paid = invoice.amount_paid + (invoice.amount_paid * Decimal('0.05'))
    
    # Calculate the current due amount
    current_due = context['running_due'] - adjusted_amount_paid
    
    # Update the running_due for the next iteration
    context['running_due'] = current_due
    
    return current_due

@register.filter
def subtract_percentage(value, percentage):
    return value - (value * Decimal(percentage) / 100)

@register.simple_tag
def calculate_total_vat(registration_courses):
    total_vat = Decimal('0.00')
    for course in registration_courses:
        discounted_price = course.course.rate * (1 - Decimal(course.discount) / 100)
        course_vat = discounted_price * Decimal('0.05')
        total_vat += course_vat
    return total_vat.quantize(Decimal('0.01'))

@register.filter(name='add_required_attribute')
def add_required_attribute(field):
    return field.as_widget(attrs={"required": "required"})