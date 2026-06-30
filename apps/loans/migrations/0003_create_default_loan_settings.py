from django.db import migrations

def create_default_loan_settings(apps, schema_editor):
    """
    🔧 Create default loan settings for all existing groups
    """
    # Get the models
    Group = apps.get_model('groups', 'Group')
    LoanSettings = apps.get_model('loans', 'LoanSettings')
    
    # Count groups without settings
    groups = Group.objects.all()
    created_count = 0
    
    for group in groups:
        # Check if settings already exist
        if not LoanSettings.objects.filter(group=group).exists():
            # Create default settings
            LoanSettings.objects.create(
                group=group,
                # Group Loan Settings
                group_loan_interest_rate=10.00,
                group_loan_duration_months=6,
                group_loan_min_amount=1000.00,
                group_loan_max_amount=500000.00,
                # ECORET Loan Settings
                ecoret_loan_interest_rate=5.00,
                ecoret_loan_duration_months=12,
                ecoret_loan_min_amount=10000.00,
                ecoret_loan_max_amount=1000000.00,
                # General Settings
                requires_guarantor=True,
                min_guarantors=2,
                grace_period_days=7,
                late_fee_percentage=0.00
            )
            created_count += 1
    
    if created_count > 0:
        print(f"Created loan settings for {created_count} groups")
    else:
        print("ℹAll groups already have loan settings")

def reverse_func(apps, schema_editor):
    """
    Reverse function - remove all loan settings
    """
    LoanSettings = apps.get_model('loans', 'LoanSettings')
    LoanSettings.objects.all().delete()
    print("All loan settings have been deleted")

class Migration(migrations.Migration):

    dependencies = [
        ('loans', '0002_remove_loansettings_default_interest_rate_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_loan_settings, reverse_func),
    ]
