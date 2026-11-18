import os
import re
import telebot
from telebot import types

TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN")
VIP_USERS = [7682498558, 287941679, 268036848]

bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_states = {}
user_data = {}

# ⚠️ БЛОК НАСТРОЙКИ СТАВОК И СУБСИДИЙ ⚠️
RATE_1 = 12.79
SUBSIDY_1 = 12.08
MIN_PV_1 = 20.1 

RATE_2 = 12.99
SUBSIDY_2 = 13.34
MIN_PV_2 = 26.0 
# ==========================================

Q_LISTS = {
    'НАМ': ['price', 'area', 'format', 'floor', 'apt_num', 'section', 'floor_num', 'discount', 'wb', 'mortgage', 'rate', 'pv', 'date_book', 'date_contract', 'fio', 'broker'],
    'МКМ': ['price', 'area', 'format', 'floor', 'apt_num', 'section', 'floor_num', 'discount', 'mortgage', 'rate', 'pv', 'date_book', 'date_contract', 'fio', 'broker'],
    'ММ': ['complex_mm', 'price', 'area', 'apt_num', 'discount', 'payment_type', 'date_book', 'date_contract', 'fio']
}

Q_TEXT = {
    'complex_mm': 'Какой комплекс? (НАМ / МКМ)', 'price': 'Цена лота?', 
    'area': 'Площадь?', 'format': 'Формат?', 'floor': 'Этаж?', 
    'apt_num': '№ лота?', 'section': 'Секция?', 'floor_num': '№ на этаже?',
    'discount': 'Какой % скидки? (Только цифра)', 'wb': 'Есть WB?', 
    'mortgage': 'Ипотека?', 'rate': 'Ставка (%)?', 
    'pv': 'ПВ (можно в % или в рублях)?', 'payment_type': 'Тип оплаты? (например: 100% или рассрочка)',
    'date_book': 'Дата бронирования?', 'date_contract': 'Дата контрактации?',
    'fio': 'ФИО клиента?', 'broker': 'Сделка с брокером?'
}

def fmt(val):
    s = f"{val:,.2f}".replace(",", " ")
    if s.endswith(".00"): return s[:-3]
    return s.replace(".", ",")

def get_mortgage_msg(price, custom_pv=None):
    contact_block = "👩‍💼 <b>Оформить ипотеку:</b>\nБлабба Мадина, 📞 +7 909 941 21 62\nTelegram: @MBlabba"
    def calc_prog(rate, min_pv_pct, custom_pv_val):
        years = 15 if rate == RATE_1 else 20
        pv_amount = price * (min_pv_pct / 100) if custom_pv_val is None else custom_pv_val
        pv_pct = (pv_amount / price) * 100
        if pv_pct < min_pv_pct - 0.01:
            return f"🔹 <b>Программа: {rate}% на {years} лет</b>\n❌ Недоступно (мин. взнос {min_pv_pct}%)\n"
        loan = price - pv_amount
        m_rate = (rate / 100) / 12
        payment = loan * (m_rate * (1 + m_rate)**(years*12)) / ((1 + m_rate)**(years*12) - 1)
        return f"🔹 <b>Программа: {rate}% на {years} лет</b>\nПервый взнос: {pv_amount:,.0f} ₽ ({pv_pct:.1f}%)\nСумма кредита: {loan:,.0f} ₽\n🔥 <b>Ежемесячный платеж: {payment:,.0f} ₽</b>\n"

    msg = f"💳 <b>{'Базовый расчет' if custom_pv is None else 'Расчет с вашим ПВ'} для стоимости {price:,.0f} ₽</b>\n\n"
    msg += calc_prog(RATE_1, MIN_PV_1, custom_pv) + "\n"
    msg += calc_prog(RATE_2, MIN_PV_2, custom_pv) + "\n"
    msg += f"<b>Доп. расход:</b>\n• Бронь/сделка - 170 000 ₽\n• Страховка ~ 200 000 ₽\n\n{contact_block}\n\n"
    if custom_pv is None: msg += "👆 <i>Чтобы изменить ПВ, просто напишите % или точную сумму.</i>"
    else: msg += "🔄 <i>Чтобы рассчитать заново с базовым взносом, нажмите кнопку «🧮 Ипотека» в меню.</i>"
    return msg.replace(',', ' ')

def generate_approval_docs(chat_id):
    ans = user_data[chat_id]['ans']
    t = user_data[chat_id]['approve_type']
    price, area = float(ans.get('price', 0)), float(ans.get('area', 1))
    sqm = price / area if area else 0
    discount_val = price * (float(ans.get('discount', 0)) / 100)
    
    if t in ['НАМ', 'МКМ']:
        wb_cost = 40000 * area if ans.get('wb') else 0
        wb_text = fmt(wb_cost) if ans.get('wb') else "нет"
        price_ddu_base = price - discount_val
        
        threshold_applied = False
        if t == 'НАМ' and (price_ddu_base / area) < 325000:
            price_ddu_base = 325000 * area
            threshold_applied = True
            
        price_ddu = price_ddu_base + wb_cost
        sqm_ddu = price_ddu / area if area else 0
        sqm_ddu_str = f"{fmt(sqm_ddu)} - порог" if threshold_applied else fmt(sqm_ddu)
        
        mortgage = ans.get('mortgage', False)
        rate = float(ans.get('rate', 0))
        pv = float(ans.get('pv', 0))
        
        if mortgage:
            credit = price_ddu - pv
            subsidy_pct = SUBSIDY_1 if rate == RATE_1 else (SUBSIDY_2 if rate == RATE_2 else rate)
            subsidy_val = credit * (subsidy_pct / 100)
            expenses_pct = (subsidy_val / price_ddu * 100) if price_ddu else 0
            payment_text = f"Субсид. ипотека ({fmt(rate)}%)"
        else:
            payment_text = "100%"
            
        broker_str = "да" if ans.get('broker') else "нет"

        if t == 'НАМ':
            msg1 = f"Добрый день!\nПрошу согласовать продажу и скидку для следующего лота по комплексу NAMETKIN TOWER\n\nАпартамент № - {ans.get('apt_num')}\nНАМ-10(А)-{ans.get('section')}/{ans.get('floor')}/{ans.get('floor_num')}\n{ans.get('format')} - {fmt(area)} кв.м\nЦена: {fmt(price)} ({fmt(sqm)})\nСкидка: {fmt(float(ans.get('discount',0)))}%\nWB: {wb_text}\nЦена в ДДУ: {fmt(price_ddu)} ({sqm_ddu_str})\n\n"
        else:
            msg1 = f"Добрый день!\nПрошу согласовать продажу для следующего лота по комплексу VERY на Миклухо-Маклая\n\nМКМ-23(КВ)-{ans.get('section')}/{ans.get('floor')}/{ans.get('floor_num')}\n{ans.get('format')} ({fmt(area)})\nСтоимость: {fmt(price)} ({fmt(sqm)})\nСкидка: {fmt(float(ans.get('discount',0)))}%\nЦена в договоре: {fmt(price_ddu)} ({sqm_ddu_str})\n\n"

        if mortgage:
            pv_pct = (pv / price_ddu * 100) if price_ddu else 0
            msg1 += f"ПВ: {fmt(pv)} ({fmt(pv_pct)}%)\nКредит: {fmt(credit)}\nСубсидия: {fmt(subsidy_val)} ({fmt(subsidy_pct)}%)\nРасходы: {fmt(expenses_pct)}% ({fmt(subsidy_val)})\n"
            
        msg1 += f"Оплата: {payment_text}\nДата бронирования: {ans.get('date_book')}\nДата контрактации: {ans.get('date_contract')}\nКлиент: {ans.get('fio')}\nОтветственный менеджер: Ходорович Роман\nСделка с брокером: {broker_str}"
        
        prefix = "НАМ" if t == 'НАМ' else "МКМ"
        msg2 = f"Аванс {prefix}\n\n{ans.get('section')}/{ans.get('floor')}/{ans.get('floor_num')} ({fmt(area)})\n{fmt(price_ddu)} ({sqm_ddu_str})\nОплата: {payment_text}"
        
        msg3 = f"✉️ <b>ПИСЬМО НА ПОЧТУ:</b>\n\nТема: {prefix} / договор бронирования / Ап. {ans.get('apt_num')} / {ans.get('fio')}\n\n"
        msg3 += f"Уважаемый(ая) {ans.get('fio')}!\n\nНаправляем Вам проект договора бронирования. Просим Вас ознакомиться с ним. В случае, если Вы согласны с подписанием приложенного договора, Вам необходимо воспользоваться функцией «ответить всем» на данное электронное письмо.\n\n"
        msg3 += "В тексте Вашего ответного письма необходимо указать следующую фразу:\n"
        msg3 += f"<i>«Со всеми условиями приложенного Договора согласен(-на). Принимаю на себя обязательства по приложенному Договору, {ans.get('fio')}»</i>\n\n"
        msg3 += "Обращаем внимание на то, что Ваше ответное письмо с согласием на заключение договора должно быть отправлено следующим получателям (воспользуйтесь кнопкой «ответить всем»):\n"
        msg3 += "• на адрес электронной почты, с которой Вы получили данное письмо;\n• на электронную почту i.razin@gk-osnova.ru\n• на электронную почту accept@gk-osnova.ru"
        return [msg1, msg2, msg3]
    else:
        price_ddu = price - discount_val
        prefix = ans.get('complex_mm', 'НАМ')
        complex_name = "NAMETKIN TOWER" if prefix == 'НАМ' else "VERY на Миклухо-Маклая"
        code = "НАМ-10(мм)" if prefix == 'НАМ' else "МКМ-10(мм)"
        
        msg1 = f"Добрый день!\nПрошу согласовать продажу и скидку для следующего лота по комплексу {complex_name}\n\n{code}-{ans.get('apt_num')}\nЦена: {fmt(price)}\nСкидка: {fmt(float(ans.get('discount',0)))}%\nЦена в ДДУ: {fmt(price_ddu)}\nОплата: {ans.get('payment_type')}\nДБ: {ans.get('date_book')}\nДата бронирования: {ans.get('date_book')}\nКонтр.: {ans.get('date_contract')}\nКлиент: {ans.get('fio')}\nОтветственный менеджер: Ходорович Роман\nСделка с участием брокера: нет\n\nАванс не присылать, только письмо."
        msg3 = f"✉️ <b>ПИСЬМО НА ПОЧТУ:</b>\n\nТема: {prefix} (ММ) / договор бронирования / ММ №{ans.get('apt_num')} / {ans.get('fio')}\n\nУважаемый(ая) {ans.get('fio')}!\nНаправляем Вам проект договора бронирования на машиноместо..."
        return [msg1, msg3]

def get_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📊 Основная информация', '🔍 Подобрать планировку', '🧮 Ипотека', '📞 Ипотечный менеджер', '🏢 Расчет ЖКУ', '📍 Офис продаж', '🗺 Карта сделки (100%)', '🏦 Карта сделки (Ипотека)')
    if chat_id in VIP_USERS: markup.add('💼 Инструменты менеджера (VIP)')
    return markup

def get_vip_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📝 Создать согласование', '📁 База файлов', '🔗 Условия реализации', '◀️ Назад в меню')
    return markup

def get_mortgage_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📋 Документы для одобрения', '⚙️ Структура сделки', '◀️ Назад в меню')
    return markup

def get_files_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('📄 FAQ HAM', '📄 Презентация NT', '📄 Памятка Госключ', '📄 Памятка эскроу', '📄 Шаблон ДДУ', '📄 Шаблон бронь', '📄 Доверенность Ершов', '📄 Доверенность Разин', '◀️ Назад в VIP-меню')
    return markup

def get_inline_cancel():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_calc"))
    return markup

def ask_approve_question(chat_id):
    state_data = user_data[chat_id]
    q_type = state_data['approve_type']
    step = state_data['approve_step']
    q_id = Q_LISTS[q_type][step]
    if q_id in ['rate', 'pv'] and not state_data['ans'].get('mortgage', False):
        state_data['approve_step'] += 1
        return ask_approve_question(chat_id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if q_id in ['wb', 'mortgage', 'broker']: markup.add('Да', 'Нет')
    elif q_id == 'format': markup.add('Студия', '1-комн.', '2-комн.', '3-комн.', 'евро-2', 'евро-3', 'евро-4')
    elif q_id == 'complex_mm': markup.add('НАМ', 'МКМ')
    elif q_id == 'rate': markup.add(str(RATE_1), str(RATE_2))
    
    markup.add('❌ Отмена') 
    bot.send_message(chat_id, f"📝 <b>Шаг {step+1}/{len(Q_LISTS[q_type])}</b>\n{Q_TEXT[q_id]}", reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "cancel_calc":
        user_states[call.message.chat.id] = None
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=call.message.text + "\n\n<i>Действие отменено.</i>", parse_mode="HTML")
        bot.answer_callback_query(call.id, "Отменено")

@bot.message_handler(commands=['start', 'myid'])
def start(message):
    if message.text == '/myid':
        bot.send_message(message.chat.id, f"Ваш ID: <code>{message.chat.id}</code>", parse_mode="HTML")
        return
    user_states[message.chat.id] = None
    bot.send_message(message.chat.id, "Здравствуйте! Я цифровой ассистент Nametkin Tower.\nВыберите раздел в меню или напишите вопрос текстом 👇", reply_markup=get_main_menu(message.chat.id), parse_mode="Markdown")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    text, chat_id = message.text, message.chat.id
    state = user_states.get(chat_id)
    
    nav_buttons = ['◀️ Назад в меню', '◀️ Назад в VIP-меню', '❌ Отмена']
    main_buttons = ['📊 Основная информация', '🔍 Подобрать планировку', '🧮 Ипотека', '📞 Ипотечный менеджер', '🏢 Расчет ЖКУ', '📍 Офис продаж', '🗺 Карта сделки (100%)', '🏦 Карта сделки (Ипотека)']
    vip_buttons = ['💼 Инструменты менеджера (VIP)', '📝 Создать согласование', '📁 База файлов', '🔗 Условия реализации']
    sub_buttons = ['📋 Документы для одобрения', '⚙️ Структура сделки', '📄 FAQ HAM', '📄 Презентация NT', '📄 Памятка Госключ', '📄 Памятка эскроу', '📄 Шаблон ДДУ', '📄 Шаблон бронь', '📄 Доверенность Ершов', '📄 Доверенность Разин']
    
    if text in nav_buttons or text in main_buttons or text in vip_buttons or text in sub_buttons or text.lower() == 'отмена':
        user_states[chat_id] = None
        state = None 
        
        if text == '◀️ Назад в меню':
            bot.send_message(chat_id, "Главное меню:", reply_markup=get_main_menu(chat_id))
            return
        elif text == '◀️ Назад в VIP-меню' or text == '❌ Отмена' or text.lower() == 'отмена':
            bot.send_message(chat_id, "Действие отменено. Закрытый раздел:", reply_markup=get_vip_menu() if chat_id in VIP_USERS else get_main_menu(chat_id))
            return

    # --- VIP БЛОК ---
    if text == '💼 Инструменты менеджера (VIP)' and chat_id in VIP_USERS:
        bot.send_message(chat_id, "🔐 Доступ в закрытый раздел открыт. Выберите инструмент:", reply_markup=get_vip_menu())
        return
    if text == '🔗 Условия реализации' and chat_id in VIP_USERS:
        bot.send_message(chat_id, "🔗 <b>Условия реализации:</b>\n<a href='https://docs.google.com/document/d/1BKXI61wcmnOcoT4rgUZVsLqqjpR4ML82b0-wWHnewy8/edit?tab=t.0'>Перейти в Google Doc</a>", parse_mode="HTML")
        return
    if text == '📁 База файлов' and chat_id in VIP_USERS:
        bot.send_message(chat_id, "📁 <b>База файлов</b>\nВыберите нужный документ:", reply_markup=get_files_menu(), parse_mode="HTML")
        return

    if text == '📄 FAQ HAM' and chat_id in VIP_USERS:
        xlsx_files = [f for f in os.listdir('.') if f.lower().endswith('.xlsx')]
        if xlsx_files:
            try: bot.send_document(chat_id, open(xlsx_files[0], "rb"))
            except: bot.send_message(chat_id, f"⚠️ Ошибка отправки файла {xlsx_files[0]}.")
        else:
            bot.send_message(chat_id, "⚠️ Excel-файл (.xlsx) не найден в системе.")
        return

    file_map = {
        '📄 Презентация NT': 'Nametkin Tower.pdf',
        '📄 Памятка Госключ': 'Памятка_Госключ.pdf',
        '📄 Памятка эскроу': 'Памятка_эскроу.pdf',
        '📄 Шаблон ДДУ': 'Шаблон ДДУ.docx',
        '📄 Шаблон бронь': 'Шаблон бронь.pdf',
        '📄 Доверенность Ершов': 'Доверенность Ершов Гартея.pdf',
        '📄 Доверенность Разин': 'Доверенность Разин 2026.pdf'
    }
    if text in file_map and chat_id in VIP_USERS:
        filename = file_map[text]
        try: bot.send_document(chat_id, open(filename, "rb"))
        except: bot.send_message(chat_id, f"⚠️ Файл {filename} не загружен в систему.")
        return

    if text == '📝 Создать согласование' and chat_id in VIP_USERS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add('НАМ', 'МКМ', 'Машиноместа', '❌ Отмена')
        bot.send_message(chat_id, "Выберите тип объекта для согласования:", reply_markup=markup)
        user_states[chat_id] = 'approve_type_select'
        return

    if state == 'approve_type_select' and chat_id in VIP_USERS:
        if text in ['НАМ', 'МКМ', 'Машиноместа']:
            t = 'ММ' if text == 'Машиноместа' else text
            user_data[chat_id] = {'approve_type': t, 'approve_step': 0, 'ans': {}}
            user_states[chat_id] = 'approve_process'
            ask_approve_question(chat_id)
        else: bot.send_message(chat_id, "Выберите кнопкой внизу.")
        return
        
    if state == 'approve_process' and chat_id in VIP_USERS:
        state_data = user_data[chat_id]
        q_type = state_data['approve_type']
        step = state_data['approve_step']
        q_id = Q_LISTS[q_type][step]
        val = text.strip()
        
        if q_id in ['price', 'area', 'discount', 'rate', 'pv']:
            val_clean = val.replace(' ', '').replace(',', '.')
            is_percent = '%' in val_clean
            val_clean = val_clean.replace('%', '')
            try: num = float(val_clean)
            except: 
                bot.send_message(chat_id, "❌ Нужно ввести число (например, 15000000 или 20%).")
                return
                
            if q_id == 'pv':
                ans = user_data[chat_id]['ans']
                p = float(ans.get('price', 0))
                a = float(ans.get('area', 1))
                d = float(ans.get('discount', 0))
                p_ddu_base = p - (p * (d/100))
                if q_type == 'НАМ' and (p_ddu_base / a) < 325000:
                    p_ddu_base = 325000 * a
                wb_cost = 40000 * a if ans.get('wb') else 0
                final_price_ddu = p_ddu_base + wb_cost
                if is_percent or num <= 100: num = final_price_ddu * (num / 100)
            val = num
        elif q_id in ['wb', 'mortgage', 'broker']:
            if 'да' in val.lower(): val = True
            elif 'нет' in val.lower(): val = False
            else:
                bot.send_message(chat_id, "❌ Нажмите кнопку Да/Нет.")
                return
                
        user_data[chat_id]['ans'][q_id] = val
        user_data[chat_id]['approve_step'] += 1
        
        if user_data[chat_id]['approve_step'] >= len(Q_LISTS[q_type]):
            docs = generate_approval_docs(chat_id)
            for d in docs: bot.send_message(chat_id, d, parse_mode="HTML")
            bot.send_message(chat_id, "✅ Согласование готово!", reply_markup=get_vip_menu())
            user_states[chat_id] = None
        else: ask_approve_question(chat_id)
        return

    # --- КЛИЕНТСКИЙ БЛОК ---
    if text == '🧮 Ипотека':
        bot.send_message(chat_id, "Введите стоимость лота (только цифры):\n<i>Например: 15000000</i>", parse_mode="HTML", reply_markup=get_inline_cancel())
        user_states[chat_id] = 'mortgage_price'
        
    elif text == '🏢 Расчет ЖКУ':
        bot.send_message(chat_id, "Введите данные (студия, 1к, 2к, 2е, 3е, 3к, 4е), площадь и стоимость:\n\n<i>Пример: студия 27.7 13000000</i>", parse_mode="HTML", reply_markup=get_inline_cancel())
        user_states[chat_id] = 'taxes'
        
    elif text == '📊 Основная информация':
        project_info = """🏢 <b>NAMETKIN TOWER — Основная информация</b>\n\n🕐 <b>Сроки</b>\n• <b>Ввод:</b> январь 2027\n• <b>Ключи:</b> до апреля 2027\n\n📍 <b>Локация и архитектура</b>\n• <b>Район:</b> ЮЗАО, Новые Черемушки\n• <b>Метро (пешком):</b> Новые Черемушки (8-10 мин), Калужская (12 мин), Зюзино (15-20 мин)\n• <b>Архитектура:</b> бюро Mecanoo\n• <b>Масштаб:</b> 24-29 наземных этажей, 2 подземных\n• <b>Площадь участка:</b> 19 367 м² (~1.94 га)\n• <b>Фонд:</b> 2314 апартаментов и 670 машиномест (+11 гостевых)\n\n🌳 <b>Инфраструктура и сервис</b>\n• <b>Двор:</b> Закрытый двор без машин, благоустроенная территория, столы для настольного тенниса и игры в шахматы, мини гольф\n• <b>Лобби:</b> Просторные входные группы площадью 300 м²\n• <b>Sky Area:</b> Терраса на 25 этаже площадью 2500 м². Amenities: sky bar, амфитеатр, work-out, детская площадка, комната персонала, коворкинг, хобби-комнаты\n• <b>Безопасность:</b> Охрана, видеонаблюдение и Рецепция 24/7\n\n✨ <b>Технические хар-ки</b>\n• <b>Потолки:</b> 3,10 м (от плиты до плиты без стяжки)\n• <b>Окна:</b> Панорамное остекление Alutech (проемы 2.7 м, 10 см от пола)\n• <b>Отделка:</b> Без ремонта (White Box - 40 000₽/м2)\n• <b>Отопление:</b> Внутрипольные конвекторы SPL с терморегулятором\n• <b>Климат:</b> Установлены внешние VRF-блоки Hisense, трасса до апарта проведена\n• <b>Технологии:</b> Умный дом (Smart Base)"""
        bot.send_message(chat_id, project_info, parse_mode="HTML")
        try: bot.send_document(chat_id, open("Nametkin Tower.pdf", "rb"))
        except: pass
        
    elif text == '🔍 Подобрать планировку':
        bot.send_message(chat_id, "🔍 <b>Подобрать идеальный лот:</b>\n\n👉 <a href='https://nametkin-tower.ru/apartments/?quantity=0'>Перейти к выбору апартаментов</a>", parse_mode="HTML")
    elif text == '📞 Ипотечный менеджер':
        bot.send_message(chat_id, "👩‍💼 <b>Контакты:</b>\nБлабба Мадина\n📞 +7 909 941 21 62\nTelegram: @MBlabba", parse_mode="HTML")
    elif text == '📍 Офис продаж':
        bot.send_message(chat_id, "📍 <b>Адрес:</b> https://yandex.ru/maps/-/CXFpUHnp\n🚗 У шлагбаума звоните: <b>+79663727924</b>", parse_mode="HTML")
        
    elif text == '🗺 Карта сделки (100%)':
        roadmap_100 = """Для оформления просьба прислать:\n\n- паспорт (фото/скан полных разворотов основной страницы и регистрации);\n- СНИЛС (фото/скан/файл из госуслуг);\n- почта;\n- номер телефона.\n- уточните семейное положение\n\n<b>По структуре сделки:</b>\n\n1. Сейчас подготовим договор бронирования.\n2. Далее произведёте оплату по нему (пришлю ссылку) — 170 000, и необходимо ответить обратным письмом на почте. Нажать в почте кнопку «Ответить всем» и вставить фразу (в тексте письма она есть):\n<i>«Со всеми условиями приложенного Договора согласен(-на). Принимаю на себя обязательства по приложенному Договору, ФИО».</i>\n3. Подготовим ДДУ и направим его вам для ознакомления\n4. От Сбербанка, с номера 900, придёт сообщение с предложением открыть эскроу-счёт — там интуитивно всё будет понятно. Должно быть установлено приложение Сбера (веб-версия не подходит). Если СМС не приходит, нужно ввести в поиске приложения «эскроу». Если нет приложения, нужно дойти до отделения Сбера и открыть счёт.\n5. Необходимо выпустить электронную цифровую подпись (ЭЦП) — Госключ. Памятку пришлю, очень важно с ней ознакомиться. На Госуслуги вам придёт уведомление от застройщика, нужно будет перейти по нему и подписать акцепт в Госключе (выставим ДДУ на подпись).\n6. Необходимо быть клиентом Альфа-Банка (там будет открыт аккредитив). Ко дню сделки туда нужно будет разместить всю сумму и прислать мне реквизиты счёта.\n7. В Госключ подгрузим все документы на подпись, после чего направим их в Росреестр.\n\n<b>После сделки:</b>\n8. Через 2-4 рабочих дня вам на почту придет зарегистрированный архив с ДДУ и выпиской из ЕГРН. Дополнительно продублирую.\n9. Ожидание начала выдачи ключей (следите за сайтом, будет смс рассылка).\n10. Запись на выдачу ключей -> приемка -> акт приема-передачи -> регистрация акта и ДДУ в Росреестре -> ремонт."""
        bot.send_message(chat_id, roadmap_100, parse_mode="HTML")
        try: bot.send_document(chat_id, open("Памятка_Госключ.pdf", "rb"))
        except: pass
        
    elif text == '🏦 Карта сделки (Ипотека)':
        bot.send_message(chat_id, "🏦 Ипотечная сделка. Выберите нужный раздел:", reply_markup=get_mortgage_menu())
        
    elif text == '📋 Документы для одобрения':
        doc_text = """Для заведения заявки просьба направить фото/скан паспорта (2-19 стр), СНИЛС фото/скан и ответить на вопросы:\n\n1. Контактный номер телефона, электронная почта; ИНН\n2. Юридическое название компании, в которой работаете, ее адрес, ИНН и телефон работодателя.\n3. Должность;\n4. Дата, с которой работаете в компании;\n5. Среднемесячный доход на руки после вычета налога;\n6. Наличие текущих кредитных обязательств. Совокупная сумма ежемесячного платежа по ним.\n7. Совпадает ли адрес прописки с фактическим проживанием. Если нет, указать актуальный.\n8. Семейное положение. Количество несовершеннолетних детей.\n9. Наличие брачного договора. Если нет, к сделке необходимо подготовить нотариальное согласие.\n10. Справки о доходах:\n  1. 2-ндфл за 2025-2026гг;\n  2. Выписка из ИЛС (индивидуальный лицевой счет из госуслуг)\n  3. СТРД из госуслуг (электронная трудовая книжка)\n11. Закажите кредитную историю https://nbki.ru/\n\n<b>Почта для документов:</b>\nm.blabba@gk-osnova.ru\nв копию r.hodorovich@gk-osnova.ru\n\n<b>В теме письма:</b> Заявка на ипотеку ФИО\n<b>В тексте письма:</b>\n- Ответы на вопросы в анкете\n- Стоимость лота\n- ПВ"""
        bot.send_message(chat_id, doc_text, parse_mode="HTML")
        
    elif text == '⚙️ Структура сделки':
        struc_text = """<b>Для Альфы ко дню сделки:</b>\n1. Внести до сделки на счет в Альфа-банк денежные средства в размере комиссии за аккредитив – 3500 руб\n2. Предоставить чек об оплате полиса страхования (ссылку на оплату пришлет ипотечный специалист - Мадина)\n<i>Проведение сделки проходит по видео-конференции в течении 20-30 мин (ссылка за 5-10 мин). При себе иметь оригиналы паспорта и СНИЛС (показать по видео).</i>\n\n<b>По структуре сделки:</b>\n1. Сейчас подготовим договор бронирования.\n2. Далее произведёте оплату по нему (пришлю ссылку) — 170 000, и необходимо ответить обратным письмом на почте: <i>«Со всеми условиями приложенного Договора согласен(-на). Принимаю на себя обязательства по приложенному Договору, ФИО».</i>\n3. Подготовим ДДУ и отправим его на согласование в банк. Далее ожидайте звонок от банка для назначения даты сделки.\n4. От Сбербанка (900) придёт сообщение открыть эскроу-счёт (нужно приложение).\n5. Выпустим вам электронную цифровую подпись (ЭЦП) — Госключ. Памятку пришлю. Подпишете акцепт в Госключе.\n6. В Госключ подгрузим все документы на подпись, после чего направим их в Росреестр."""
        bot.send_message(chat_id, struc_text, parse_mode="HTML")
        try: bot.send_document(chat_id, open("Памятка_Госключ.pdf", "rb"))
        except: pass

    else:
        if state == 'mortgage_price':
            try:
                price = float(re.search(r'\d+(?:\.\d+)?', re.sub(r'\s+', '', text).replace(',', '.')).group())
                user_data[chat_id] = price
                user_states[chat_id] = 'mortgage_pv' 
                bot.send_message(chat_id, get_mortgage_msg(price), parse_mode="HTML", reply_markup=get_inline_cancel())
            except: bot.send_message(chat_id, "❌ Пожалуйста, назовите сумму цифрами.")
        elif state == 'mortgage_pv':
            try:
                price = user_data.get(chat_id)
                val_clean = text.replace(' ', '').replace(',', '.')
                is_percent = '%' in val_clean
                val_clean = val_clean.replace('%', '')
                val = float(re.search(r'\d+(?:\.\d+)?', val_clean).group())
                
                pv_amount = price * (val/100) if is_percent or val <= 100 else val
                bot.send_message(chat_id, get_mortgage_msg(price, custom_pv=pv_amount), parse_mode="HTML")
            except: bot.send_message(chat_id, "❌ Пожалуйста, отправьте цифру взноса.")
        elif state == 'taxes':
            try:
                text_clean = re.sub(r'(?<=\d)[\s_]+(?=\d{3}(?!\d))', '', text.lower().replace(',', '.'))
                parts = text_clean.split()
                apt_type, area, price = None, None, None
                for p in parts:
                    if p in ['студия', '1к', '2е', '2к', '3е', '3к', '4е']: apt_type = p
                    else:
                        try:
                            val = float(p)
                            if val < 500: area = val
                            else: price = val
                        except ValueError: pass
                if not apt_type or not area or not price: raise ValueError
                
                uk_month = area * 200
                if apt_type in ['студия']: counters_month = 3500
                elif apt_type in ['1к', '2е']: counters_month = 4500
                elif apt_type in ['2к', '3е', '3к', '4е']: counters_month = 6000
                else: counters_month = 4500
                tax_year = (price / 2) * 0.005
                land_rent_year = area * 653
                total_month_full = uk_month + counters_month + (tax_year / 12) + (land_rent_year / 12)
                
                msg = (f"📊 <b>Расчет ЖКУ ({apt_type.capitalize()}, {area} м², {price:,.0f} ₽):</b>\n\n"
                       f"🔹 <b>Ежемесячно:</b>\n• УК (200 р./м²): {uk_month:,.0f} ₽/мес\n• Счетчики (+20%): {counters_month:,.0f} ₽/мес\n\n"
                       f"🔹 <b>Ежегодно:</b>\n• Налог (0,5% от кадастра): {tax_year:,.0f} ₽/год\n• Аренда земли: {land_rent_year:,.0f} ₽/год\n\n"
                       f"🔥 <b>Итог за месяц (с учетом налога и аренды): {total_month_full:,.0f} ₽</b>\n"
                       f"💡 <b>Итог за месяц (без налога и аренды): {uk_month + counters_month:,.0f} ₽</b>\n\n"
                       f"⚠️ <i>Обращаем внимание: расчеты ориентировочные. Итоговая сумма зависит от тарифов УК и кадастровой стоимости.</i>")
                
                bot.send_message(chat_id, msg.replace(',', ' '), parse_mode="HTML")
                user_states[chat_id] = None
            except Exception: bot.send_message(chat_id, "❌ Ошибка. Пример ввода: студия 27.7 13000000", parse_mode="HTML")

print("🚀 Запускаем цифрового ассистента...")
try: bot.remove_webhook()
except Exception: pass
bot.infinity_polling()

