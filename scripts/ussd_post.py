import os, uuid, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','ecoret_backend.settings')
import django
django.setup()
from django.test import Client
from apps.groups.models import Group, GroupMember
from apps.accounts.models import User

phone = '+265999789012'
code = '751400'

# Ensure group exists
group = Group.objects.filter(group_code=code, is_active=True).first()
if not group:
    group = Group.objects.create(group_name='Temp Group Auto', group_code=code, is_active=True)

# Ensure member exists
member = GroupMember.objects.filter(group=group, phone_number=phone, is_active=True).first()
if not member:
    user = User.objects.filter(phone_number=phone).first()
    if not user:
        user = User.objects.create_user(email=f'temp_{uuid.uuid4().hex[:6]}@example.com', password='x', first_name='Auto', last_name='User', phone_number=phone)
    member = GroupMember.objects.create(group=group, user=user, full_name='Auto Member', national_id=str(uuid.uuid4())[:10], phone_number=phone)

client = Client()
payload = {
    'phoneNumber': phone,
    'sessionId': 'session-live-test-'+uuid.uuid4().hex[:6],
    'serviceCode': '*123#',
    'text': '1*'+code
}
print('Posting payload:', payload)
resp = client.post('/api/ussd/', json.dumps(payload), content_type='application/json')
print('Status:', resp.status_code)
print('Response body:\n', resp.content.decode())

# print current session if created
from apps.ussd.models import USSDSession
s = USSDSession.objects.filter(session_id=payload['sessionId']).first()
print('Session found:', bool(s))
if s:
    print('Session:', s.session_id, s.phone_number, s.current_menu, s.group_code, s.member_id)
