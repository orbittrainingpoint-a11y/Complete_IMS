from django import template
import json

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