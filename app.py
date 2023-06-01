from aiogram import Bot, Dispatcher, executor, exceptions
from aiogram.types import ReplyKeyboardMarkup, ChatJoinRequest, Message, ContentType, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher import FSMContext

import asyncio
import sqlite3

from BError import BError
from config import TOKEN, CHAT_ID, LOG_CHAT, ADMINS

storage = MemoryStorage()

bot = Bot(token=TOKEN)
dp = Dispatcher(bot=bot,
                storage=storage)
db = sqlite3.connect("user_info.db")
db.row_factory = lambda cursor, row: row[0]

status_member = ['creator', 'administrator', 'member']

time_to_invite = 60 * 30 # время в секундах по умолчанию

class ClientStatesGroup(StatesGroup):
    photo = State()
    description = State()
    accept = State()

class InviteStatesGroup(StatesGroup):
    time = State()

from aiogram.dispatcher.filters import Text

async def check_admins(id: int):
    if id not in ADMINS:
        await bot.send_message(chat_id=id, text=f'Нет доступа к данной функции.')
        return False
    return True

def get_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton('Отменить'))

def get_accept() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton('Подтвердить'))
    kb.add(KeyboardButton('Отменить'))
    return kb

def get_main_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True,
                                one_time_keyboard=True)
    kb.add(KeyboardButton(text="Пост с картинкой"))
    kb.add(KeyboardButton(text="Пост без картинки"))
    kb.add(KeyboardButton(text="Кол-во пользователей для рассылки"))
    #kb.add(KeyboardButton(text="Поменять интервал приема заявок в канал")) # временнно отключена
    return kb

@dp.message_handler(Text(equals='Отменить', ignore_case=True), state='*')
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if not await check_admins(message.chat.id):
        return
    if await state.get_state() is None:
        return
    await message.reply('Отменил действие', reply_markup=get_main_keyboard())
    await state.finish()

@dp.message_handler(lambda message: not message.photo, state=ClientStatesGroup.photo)
async def check_photo(message: Message):
    if not await check_admins(message.chat.id):
        return
    return await message.reply('Это не фотография!')

@dp.message_handler(lambda message: message.photo, content_types=['photo'], state=ClientStatesGroup.photo)
async def load_photo(message: Message, state: FSMContext):
    if not await check_admins(message.chat.id):
        return
    async with state.proxy() as data:
        data['photo'] = message.photo[-1].file_id
    await ClientStatesGroup.description.set()
    await message.reply('А теперь отправь описание')

@dp.message_handler(state=ClientStatesGroup.description)
async def add_description(message: Message, state: FSMContext):
    if not await check_admins(message.chat.id):
        return
    async with state.proxy() as data:
        data['desc'] = message.text
    await ClientStatesGroup.accept.set()
    await message.reply('Подтверди, что хочешь отправить пост', reply_markup=get_accept())

@dp.message_handler(Text(equals="Подтвердить", ignore_case=True), state=ClientStatesGroup.accept)
async def accept(message: Message, state: FSMContext):
    if not await check_admins(message.chat.id):
        return
    try:
        async with state.proxy() as data:
            if data['photo'] is not None:
                print ('send_photo')
                await send_message_to_all_users(message=message,
                                                text=data['desc'],
                                                file_photo_id=data['photo'])
            else:
                print ('send_message')
                await send_message_to_all_users(message=message,
                                                text=data['desc'])
            await message.reply('🎉 Пост отправлен! 🎉', reply_markup=get_main_keyboard())
            await state.finish()
    except Exception as error:
        await message.reply(f'Упс! Случилось что-то не предсказуемое, когда отправлял пост: \n{error}', reply_markup=get_main_keyboard())
        await state.finish()

@dp.message_handler(Text(equals='Пост с картинкой', ignore_case=True))
async def post_with_photo(message: Message):
    if not await check_admins(message.chat.id):
        return
    await ClientStatesGroup.photo.set()
    await message.answer('Сначала отправь фотографию.', reply_markup=get_cancel())

@dp.message_handler(Text(equals='Пост без картинки', ignore_case=True))
async def post_text(message: Message, state: FSMContext):
    if not await check_admins(message.chat.id):
        return
    async with state.proxy() as data:
        data['photo'] = None
    await ClientStatesGroup.description.set()
    await message.answer('Отправь текст', reply_markup=get_cancel())

@dp.message_handler(commands=['photo'])
async def photo_bot(message: Message):
    if not await check_admins(message.chat.id):
        return
    await bot.send_message(chat_id=message.chat.id, text='Пробую отправить фото')
    await bot.send_photo(chat_id=message.chat.id, photo=message.photo, caption=f'{message.text}')

# @dp.message_handler(commands=['chatid'])
# async def get_chatid(message: Message):
#     await bot.send_message(message.chat.id, f"chatid: {message.chat.id}")
#     await bot.send_message(message.chat.id, f'user_chatid: {message.from_user.id}')

@dp.message_handler(commands=['start'], state=None)
async def start_bot(message: Message):
    if not await check_admins(message.chat.id):
        return
    kb = get_main_keyboard()
    await message.answer(text=f'Привет, {message.from_user.first_name}, пользуйся клавиатурой.', reply_markup=kb)

@dp.message_handler(Text(equals='Кол-во пользователей для рассылки', ignore_case=True))
async def users_count(message: Message):
    if not await check_admins(message.chat.id):
        return
    await message.answer(text=f'Кол-во пользователей: {await count_users_from_db()}')

@dp.message_handler(Text(equals='Поменять интервал приема заявок в канал', ignore_case=True))
async def change_time(message: Message):
    if not await check_admins(message.chat.id):
        return
    await InviteStatesGroup.time.set()
    await message.answer(text=f'Кол-во пользователей: {await count_users_from_db()}')

@dp.message_handler(state=InviteStatesGroup.time)
async def change_number(message: Message):
    if not await check_admins(message.chat.id):
        return
    try:
        number = int(message.text)
        await message.answer(f'Интервал принятия в канал изменен на {number}')
    except:
        await message.answer('К сожалению, это не число')

@dp.chat_join_request_handler()
async def echo(chat_member: ChatJoinRequest):
    kb = ReplyKeyboardMarkup(resize_keyboard=True,
                                   one_time_keyboard=True)
    kb.add(KeyboardButton(text="🧙 Я человек",))
    await bot.send_message(chat_id=chat_member.from_user.id, text=f'Привет, {chat_member.from_user.first_name}, спасибо за подписку на канал! \nЯ анти-спам бот. \nДля подтверждения того, что ты живой человек, нажмите кнопку «🧙 Я человек»',reply_markup=kb)

@dp.message_handler(Text(endswith='Я человек', ignore_case=True))
async def message_check(message: Message):
    await send_log(f'Пользователь c id: {message.from_user.id} и именем: {message.from_user.full_name} Нажал на кнопку «🧙 Я человек»')
    await check_member_status(message)
    await bot.send_message(chat_id=message.from_user.id, text='Спасибо, ты подтвердил, что не являешься ботом. Твоя заявка на вступление будет одобрена модераторами в течении 30 минут.')
    await save_user_to_db(message)
    await asyncio.sleep(10)
    await send_log(f'Пользователь c id: {message.from_user.id} и именем: {message.from_user.full_name} был аппрувнут и добавлен в канал ✅')
    try:
        await bot.approve_chat_join_request(CHAT_ID, message.from_user.id)
    except Exception as error:
        await send_log(f'Упс! Произошла ошибка, во время апрува пользователя: {error}')


async def check_member_status(message: Message):
    member = await bot.get_chat_member(chat_id=CHAT_ID, user_id=message.from_user.id)
    for i in status_member:
        if i == member.status:
            return await bot.send_message(chat_id=message.from_user.id, text=f'Привет, {message.from_user.first_name}, ты уже состоишь в канале.')

async def save_user_to_db(message: Message):
    cursor = db.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS user(
	 	id INTEGER
	 	);""")
    db.commit()
    user_id = message.from_user.id
    cursor.execute(f"SELECT id FROM user WHERE id = {user_id};")
    data = cursor.fetchone()
    if data is None:
        cursor.execute(f"INSERT INTO user (id) VALUES ({user_id});")
        db.commit()
    cursor.close()

async def count_users_from_db() -> int:
    cursor = db.cursor()
    cursor.execute('SELECT COUNT(*) FROM user;')
    data = cursor.fetchone()
    cursor.close()
    if data is None:
        return 0
    return data
    

async def send_message_to_all_users(message: Message, text: str, file_photo_id: str = None):
    file_photo_id = file_photo_id
    text = text
    cursor = db.cursor()
    cursor.execute(f"SELECT id FROM user;")
    data = cursor.fetchall()
    dict = { BError.BotBlocked: 0, BError.ChatNotFound: 0,
             BError.RetryAfter: 0, BError.UserDeactivated: 0,
             BError.TelegramAPIError: 0, BError.Success: 0 }

    for chat_id in data:
        await send_bot_message(chat_id=chat_id,
                               errors_dict=dict,
                               text=text,
                               file_photo_id=file_photo_id)
    await send_statistics(message, LOG_CHAT, dict)
    cursor.close()

async def send_bot_message(chat_id: int,
                           errors_dict: dict[BError, int],
                           text: str,
                           file_photo_id: str = None):
    try:
        if file_photo_id is None:
            await bot.send_message(chat_id=chat_id, text=text)
        else:
            await bot.send_photo(chat_id=chat_id,
                                  photo=file_photo_id,
                                  caption=text)
    except exceptions.BotBlocked:
        errors_dict[BError.BotBlocked] += 1
    except exceptions.ChatNotFound:
        errors_dict[BError.ChatNotFound] += 1
    except exceptions.RetryAfter as e:
        errors_dict[BError.RetryAfter] += 1
        await bot.send_message(LOG_CHAT,
                              f"Target [ID:{chat_id}]: Flood limit is exceeded. "
                              f"Sleep {e.timeout} seconds.")
        await asyncio.sleep(e.timeout)
        return await bot.send_message(chat_id, text=f'Тест сообщения всем юзерам')  # Recursive call
    except exceptions.UserDeactivated:
        errors_dict[BError.UserDeactivated] += 1
    except exceptions.TelegramAPIError:
        errors_dict[BError.TelegramAPIError] += 1
    else:
        errors_dict[BError.Success] += 1
        return True
    return False

async def send_statistics(message: Message, chat_id: int, stat_dict: dict[BError, int]):
    message = """
⚠️<b>Был отправлен пост, отправитель: {} </b>⚠️
Пользователей с заблокированным ботом: {}
Пользователей чей чат не был найден: {}
Пользователей где нужен retry message: {} (отправится снова через некоторое время)
Пользователей у кого деактивирован бот: {}
Произошла ошибка TelegramAPIError: {}
Пользователей с успешным отправлением: {}
    """.format(str(message.from_user.full_name), str(stat_dict[BError.BotBlocked]), str(stat_dict[BError.ChatNotFound]),
               str(stat_dict[BError.RetryAfter]), str(stat_dict[BError.UserDeactivated]),
               str(stat_dict[BError.TelegramAPIError]), str(stat_dict[BError.Success]))
    await send_log(message)

async def send_log(message: str):
    await bot.send_message(LOG_CHAT, message, parse_mode='html')

@dp.message_handler(commands=['log'])
async def send_logger(message: Message):
    await send_log('ku')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)