"""The first 150 cards, ordered as ten small thematic chapters.

Russian pronunciation hints are deliberately approximate. The recorded English
word is the pronunciation model; hints are only a bridge for new readers.
"""

CHAPTERS = [
    ("Первые слова", """
I|ай|я
you|ю|ты
he|хи|он
she|ши|она
it|ит|оно
we|уи|мы
they|зэй|они
hello|хэлоу|привет
bye|бай|пока
is|из|есть (он, она)
are|ар|есть (они)
have|хэв|иметь
has|хэз|имеет
my|май|мой
your|йор|твой
"""),
    ("Животные", """
cat|кэт|кошка
dog|дог|собака
mouse|маус|мышь
bird|бёрд|птица
fish|фиш|рыба
rabbit|рэбит|кролик
bear|бэр|медведь
fox|фокс|лиса
cow|кау|корова
horse|хорс|лошадь
sheep|шип|овца
chicken|чикен|курица
frog|фрог|лягушка
bee|би|пчела
butterfly|батэрфлай|бабочка
"""),
    ("Сад и природа", """
tree|три|дерево
flower|флауэр|цветок
leaf|лиф|лист
grass|грас|трава
seed|сид|семечко
plant|плэнт|растение
sun|сан|солнце
rain|рэйн|дождь
cloud|клауд|облако
sky|скай|небо
moon|мун|луна
star|стар|звезда
stone|стоун|камень
river|ривэр|река
garden|гарден|сад
"""),
    ("Еда и напитки", """
apple|эпл|яблоко
banana|бэнана|банан
orange|ориндж|апельсин
pear|пэр|груша
carrot|кэрэт|морковь
tomato|томэйто|помидор
potato|потэйто|картошка
bread|брэд|хлеб
cheese|чиз|сыр
milk|милк|молоко
egg|эг|яйцо
cake|кейк|торт
cookie|куки|печенье
soup|суп|суп
juice|джус|сок
"""),
    ("Дом", """
house|хаус|дом
room|рум|комната
door|дор|дверь
window|уиндоу|окно
bed|бэд|кровать
chair|чэр|стул
table|тэйбл|стол
lamp|лэмп|лампа
box|бокс|коробка
cup|кап|чашка
ball|бол|мяч
toy|той|игрушка
clock|клок|часы
book|бук|книга
key|ки|ключ
"""),
    ("Семья и друзья", """
mother|мазэр|мама
father|фазэр|папа
sister|систэр|сестра
brother|бразэр|брат
baby|бэйби|малыш
boy|бой|мальчик
girl|гёрл|девочка
friend|фрэнд|друг
teacher|тичэр|учитель
child|чайлд|ребёнок
family|фэмили|семья
grandma|грэндма|бабушка
grandpa|грэндпа|дедушка
man|мэн|мужчина
woman|вумэн|женщина
"""),
    ("Цвета и размеры", """
red|рэд|красный
blue|блу|синий
green|грин|зелёный
yellow|йелоу|жёлтый
black|блэк|чёрный
white|уайт|белый
pink|пинк|розовый
brown|браун|коричневый
purple|пёрпл|фиолетовый
gray|грэй|серый
big|биг|большой
small|смол|маленький
long|лонг|длинный
short|шорт|короткий
round|раунд|круглый
"""),
    ("Действия", """
eat|ит|есть
drink|дринк|пить
sleep|слип|спать
run|ран|бегать
jump|джамп|прыгать
walk|уок|ходить
sit|сит|сидеть
stand|стэнд|стоять
play|плэй|играть
look|лук|смотреть
listen|лисэн|слушать
open|оупэн|открывать
close|клоуз|закрывать
give|гив|давать
take|тэйк|брать
"""),
    ("Чувства и место", """
happy|хэпи|радостный
sad|сэд|грустный
angry|энгри|сердитый
tired|тайэрд|уставший
hungry|хангри|голодный
thirsty|сёрсти|хочет пить
hot|хот|горячий
cold|коулд|холодный
clean|клин|чистый
dirty|дёрти|грязный
new|нью|новый
good|гуд|хороший
little|литл|маленький
yes|йес|да
no|ноу|нет
"""),
    ("Связки и место", """
in|ин|внутри
on|он|на
under|андэр|под
here|хир|здесь
there|зэр|там
this|зис|этот
that|зэт|тот
and|энд|и
but|бат|но
can|кэн|мочь
to|ту|к
with|уиз|с
for|фор|для
not|нот|не
where|уэр|где
"""),
]


def load_words():
    words = []
    for chapter_index, (chapter_name, raw) in enumerate(CHAPTERS):
        lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
        if len(lines) != 15:
            raise ValueError(f"Chapter {chapter_name!r} has {len(lines)} words, expected 15")
        for line in lines:
            english, hint, russian = line.split("|", 2)
            words.append({
                "id": english,
                "en": english,
                "hint": hint,
                "ru": russian,
                "chapter": chapter_index,
                "chapter_name": chapter_name,
            })
    if len(words) != 150 or len({word["id"] for word in words}) != 150:
        raise ValueError("The word bank must contain 150 distinct English words")
    return words


WORDS = load_words()
WORD_BY_ID = {word["id"]: word for word in WORDS}
