import os, uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE','ecoret_backend.settings')
import django
django.setup()
from apps.ussd.views import USSDView
from apps.ussd.models import USSDSession
from apps.accounts.models import User
from apps.groups.models import Group, GroupMember
phone='+265999789012'
code='751400'
# ensure group exists
group = Group.objects.filter(group_code=code, is_active=True).first()
if not group:
    group = Group.objects.create(group_name='Temp Group Auto', group_code=code, is_active=True)
# ensure member exists for phone
member = GroupMember.objects.filter(group=group, phone_number=phone, is_active=True).first()
if not member:
    # try find any user with same phone
    user = User.objects.filter(phone_number=phone).first()
    if not user:
        user = User.objects.create_user(email=f'temp_{uuid.uuid4().hex[:6]}@example.com', password='x', first_name='Auto', last_name='User', phone_number=phone)
    member = GroupMember.objects.create(group=group, user=user, full_name='Auto Member', national_id=str(uuid.uuid4())[:10], phone_number=phone)
# create unique session
sid = 'sess-'+uuid.uuid4().hex[:8]
s = USSDSession.objects.create(session_id=sid, phone_number=phone, current_menu='welcome', language='en')
v = USSDView()
print('Calling handle_menu with:', '1*'+code)
resp = v.handle_menu(s, '1*'+code)
print('Response:')
print(resp)
# show session fields
s.refresh_from_db()
print('Session state after:', s.current_menu, s.group_code, s.member_id)
