import asyncio, os, sys
sys.path.insert(0, '.')
import httpx
from dotenv import load_dotenv
load_dotenv(override=True)
from backend import build_backend_payload

BACKEND_URL = os.getenv('BACKEND_URL', '').rstrip('/')
BACKEND_PHONE = os.getenv('BACKEND_PHONE', '')
CODE = '2260'

vacancies = [
    {'position': 'Повар', 'category': 'food', 'work_schedule': '6/1', 'requirements': 'Опыт работы', 'conditions': 'Зарплата 2000 за смену, Выплаты раз в неделю', 'description': 'Требуется повар для приготовления шаурмы. Адрес работы: площадь Ала Тоо.', 'experience_work': '', 'remote_work': False, 'city': 'Бишкек', 'work_address': 'площадь Ала Тоо', 'region': '', 'payment_period': 'В день', 'salary_net': 2000, 'company': 'Частный работодатель', 'company_description': 'https://wa.me/996708943590'},
    {'position': 'Сушист', 'category': 'food', 'work_schedule': '5/2 с 10:00 до 23:00', 'requirements': '', 'conditions': '', 'description': 'Требуется сушист для работы в фастфуде.', 'experience_work': '', 'remote_work': False, 'city': 'Бишкек', 'work_address': 'Ахунбаева', 'region': '', 'payment_period': '', 'salary_net': 0, 'company': 'Частный работодатель', 'company_description': 'https://wa.me/996700446528'},
    {'position': 'Администратор', 'category': 'admin', 'work_schedule': '', 'requirements': 'Приятная внешность, Грамотная речь, Коммуникабельность, Ответственность, Уверенное владение ПК', 'conditions': 'Комфортные условия работы, Своевременная заработная плата, Возможность профессионального развития', 'description': 'В клинику Life Hospital требуется девушка на ресепшн.', 'experience_work': '', 'remote_work': False, 'city': 'Бишкек', 'work_address': '', 'region': '', 'payment_period': '', 'salary_net': 0, 'company': 'Life Hospital', 'company_description': 'https://wa.me/996508060424'},
    {'position': 'Торговый представитель', 'category': 'sales', 'work_schedule': '', 'requirements': 'Опыт работы торговым агентом, Умение продавать и вести переговоры, Авто — преимущество', 'conditions': 'Оклад 30 000 сом + % от продаж + пассивный доход', 'description': 'Требуется торговый представитель для подключения кофеен и точек питания. Средний заработок 60-120 тыс. сомов.', 'experience_work': 'От 1 года', 'remote_work': False, 'city': 'Бишкек', 'work_address': '', 'region': '', 'payment_period': 'В месяц', 'salary_net': 30000, 'company': 'The Base', 'company_description': 'https://wa.me/996505795659'},
]


async def go():
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(f'{BACKEND_URL}/auth/confirm-phone', json={'phoneNumber': BACKEND_PHONE, 'code': CODE})
        print(f'Confirm: {r.status_code}')
        token = r.json().get('access_token', '')
        refresh = r.cookies.get('refresh_token', '')
        print(f'access_token: {token[:50]}' if token else 'access_token: NOT FOUND')
        print(f'refresh_token: {refresh}')

        if not token:
            print('ERROR: no access token received')
            return

        for v in vacancies:
            payload = build_backend_payload(v)
            rv = await http.post(
                f'{BACKEND_URL}/vacancy',
                headers={'Authorization': f'Bearer {token}'},
                json=payload
            )
            ok = rv.status_code in (200, 201)
            print(f"{'OK' if ok else 'ERROR ' + str(rv.status_code)} — {v['position']}")

        if refresh:
            from dotenv import set_key
            set_key('.env', 'BACKEND_REFRESH_TOKEN', refresh)
            print(f'\nRefresh token saved to .env: {refresh}')


asyncio.run(go())
