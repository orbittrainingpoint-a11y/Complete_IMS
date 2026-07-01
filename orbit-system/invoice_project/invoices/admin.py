from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from .models import UserProfile, SalesTarget, Course, Registration
import datetime


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Role & Profile'
    fields = ('role', 'phone')


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'first_name', 'last_name', 'email', 'get_role', 'is_active')

    def get_role(self, obj):
        try:
            return obj.profile.get_role_display()
        except UserProfile.DoesNotExist:
            return '—'
    get_role.short_description = 'Role'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(SalesTarget)
class SalesTargetAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_month_label', 'target_amount_display', 'target_registrations', 'get_created_by')
    list_filter = ('month', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    ordering = ('-month', 'user__first_name')
    date_hierarchy = None

    fieldsets = (
        ('Salesperson', {
            'fields': ('user',)
        }),
        ('Target Period', {
            'fields': ('month',),
            'description': 'Enter the first day of the month (e.g. 2026-07-01 for July 2026)'
        }),
        ('Targets', {
            'fields': ('target_amount', 'target_registrations')
        }),
    )

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Salesperson'
    get_full_name.admin_order_field = 'user__first_name'

    def get_month_label(self, obj):
        return obj.month.strftime('%B %Y')
    get_month_label.short_description = 'Month'
    get_month_label.admin_order_field = 'month'

    def target_amount_display(self, obj):
        return format_html('AED {:,.0f}', obj.target_amount)
    target_amount_display.short_description = 'Target Amount'
    target_amount_display.admin_order_field = 'target_amount'

    def get_created_by(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.username if obj.created_by else '—'
    get_created_by.short_description = 'Set By'

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        # Always store the first day of the month
        obj.month = obj.month.replace(day=1)
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            kwargs['queryset'] = User.objects.filter(
                profile__role='sales_executive', is_active=True
            ).order_by('first_name', 'username')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'month' in form.base_fields:
            form.base_fields['month'].initial = datetime.date.today().replace(day=1)
            form.base_fields['month'].help_text = 'Always set to the 1st of the month automatically.'
        return form


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'rate', 'online_rate', 'batch_rate', 'private_rate')
    search_fields = ('name', 'code')
    ordering = ('name',)
