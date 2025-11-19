
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import urlencode

from app.config import get_settings
from app.llm import LifeStoryLLM
from app.database import init_db, get_db, get_db_context
from app.models import User, Chapter, Answer, Story, StoryChapter
from app.auth import (
    create_access_token,
    get_current_user,
    get_or_create_user_from_oauth,
    get_google_oauth_client,
    get_google_user_info,
)

# Global LLM instance
llm: Optional[LifeStoryLLM] = None


def seed_chapters(db: Session):
    """Seed the chapters table with predefined chapters."""
    chapters_data = [
        {"id": "1", "title": "שורשים ומשפחה מוקדמת", "order": 1},
        {"id": "2", "title": "ילדות", "order": 2},
        {"id": "3", "title": "נעורים", "order": 3},
        {"id": "4", "title": "אהבה וזוגיות", "order": 4},
        {"id": "5", "title": "צבא / שירות / לימודים", "order": 5},
        {"id": "6", "title": "קריירה ועשייה", "order": 6},
        {"id": "7", "title": "הורות ומשפחה", "order": 7},
        {"id": "8", "title": "חברים וקהילה", "order": 8},
        {"id": "9", "title": "תחביבים ופנאי", "order": 9},
        {"id": "10", "title": "אמונות וערכים", "order": 10},
        {"id": "11", "title": "רגעים קשים ומשמעותיים", "order": 11},
        {"id": "12", "title": "חלומות והבטים קדימה", "order": 12},
    ]
    
    for chapter_data in chapters_data:
        existing = db.query(Chapter).filter(Chapter.id == chapter_data["id"]).first()
        if not existing:
            chapter = Chapter(**chapter_data)
            db.add(chapter)
    
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for app startup/shutdown."""
    global llm
    # Startup
    settings = get_settings()
    
    # Initialize database
    try:
        init_db()
        # Seed chapters
        with get_db_context() as db:
            seed_chapters(db)
        print("Database initialized and chapters seeded successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")
    
    # Initialize LLM
    try:
        llm = LifeStoryLLM(settings)
    except Exception as e:
        # If LLM initialization fails (e.g., missing API keys), log but continue
        # The endpoints will handle this gracefully
        print(f"Warning: LLM initialization failed: {e}")
        llm = None
    
    yield
    
    # Shutdown
    llm = None


app = FastAPI(title="Life Story Q&A API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep RAW_QUESTIONS for backward compatibility and question generation
RAW_QUESTIONS: Dict[str, List[Dict]] = {
    "1": [
        "איך קוראים לך? בן כמה אתה? ואיפה נולדת? ",
        "איפה נולדת, ומה אתה זוכר מהמקום שבו התחלת את חייך?",
        "מה הסיפור מאחורי השם שלך — מי בחר אותו ולמה דווקא הוא?",
        "מהו הזיכרון הראשון שלך כילד או ילדה?",
        "איך נראה הבית שבו גדלת — הריחות, הצלילים, התחושות?",
        "מי היו האנשים שחיו איתך בבית, ואיך הייתם מסתדרים?",
        "אילו חגים היו הכי משמעותיים בבית שלכם, ואיך חגגתם אותם?",
        "מה המאכל שהכי אהבת בילדותך, ומי היה מכין אותו?",
        "תוכל לספר על סיפור מצחיק או מביך שקרה לך כילד?",
        "מי היה האדם הקרוב אליך ביותר בילדות — ומדוע?",
        "אילו משחקים או פעילויות אהבת לעשות כשהיית קטן?",
        "מי היה החבר או החברה הכי טובים שלך בילדות, ומה אהבתם לעשות יחד?",
        "אילו שירים, סיפורים או מנגינות זכורים לך מהבית?",
        "מה למדת מאמא שלך — לאו דווקא במילים, אלא מההתנהגות שלה?",
        "ומה למדת מאבא שלך?",
        "אילו אמונות, ערכים או משפטים “קבועים” היו נשמעים בבית שלך?",
        "תאר רגע משפחתי שאתה זוכר כחמים במיוחד?",
        "האם היה מישהו במשפחה שכולם צחקו בזכותו, או שהיה “הליצן” של המשפחה?",
        "אילו מסורות או הרגלים משפחתיים הכי אהבת?",
        "האם היו במשפחה סיפורים שעברו מדור לדור — על נדודים, עלייה, אהבה, או הישרדות?",
        "איך נראתה השכונה או הכפר שבו גדלת? מי היו האנשים שסבבו אותך?",
        "איך התמודדה המשפחה עם רגעים קשים או מאתגרים?",
        "איזה ריח או טעם מייד מחזיר אותך הביתה?",
        "אם היית צריך לבחור תמונה אחת שמייצגת את הבית שבו גדלת — איזו תמונה זו הייתה?",
        "מה אתה חושב שירשת מהמשפחה שלך — תכונה, הרגל או גישה לחיים?",
        "אם היית יכול לדבר עם אחד מאבות המשפחה שלך, מי זה היה ומה היית שואל אותו?"
    ],
    "2": [
        "איפה בילית את רוב זמנך כילד? בבית, בחוץ, אצל חברים, בטבע?",
        "מי היה החבר או החברה הכי טובים שלך בילדות, ומה אהבתם לעשות יחד?",
        "איזה משחק או צעצוע היה האהוב עליך ביותר?",
        "מה המאכל או הממתק שהכי שימחו אותך כילד?",
        "היה לך מקום סודי או מיוחד שאהבת להיות בו לבד?",
        "איזה ריח או טעם מזכיר לך מיד את הילדות שלך?",
        "מהו אחד הזיכרונות הראשונים שלך מהגן או מבית הספר?",
        "איזה מורה או גננת השפיעו עליך במיוחד — ולמה?",
        "איך היית מתאר את עצמך כילד? ביישן, סקרן, שובב, רגוע...?",
        "מה גרם לך לצחוק הכי חזק כשהיית קטן?",
        "תוכל לספר סיפור מצחיק או מוזר שקרה לך בילדות?",
        "ממה פחדת כשהיית קטן — ומה היה עוזר לך להירגע?",
        "מה גרם לך להרגיש מוגן או נאהב?",
        "האם היו בבית חיות מחמד? מה זכור לך מהן?",
        "איזה תחביבים או עיסוקים אהבת לעשות לבד?",
        "איך נראו ימי ההולדת שלך? מי היה מגיע, ואיך חגגתם?",
        "מה היה חלום הילדות שלך — מה רצית להיות כשתגדל?",
        "האם הייתה תקופה בילדות שלך שאתה זוכר במיוחד לטובה? למה דווקא היא?",
        "תוכל לתאר יום טיפוסי בילדותך — מהבוקר עד הערב?",
        "מה היה קורה כשעשית משהו שובב או לא הקשבת להורים?",
        "אילו חופשות, טיולים או חוויות משפחתיות זכורות לך במיוחד?",
        "אם היית יכול לחזור ליום אחד בילדותך — לאיזה יום היית חוזר?",
        "מי היה הגיבור או הדמות שהערצת בילדותך — מסרט, ספר או מהחיים?",
        "מה למדת על עצמך כילד שהולך איתך עד היום?",
        "אם היית צריך לתאר את הילדות שלך במילה אחת — איזו מילה זו הייתה?"
    ],
    "3": [
        "באיזה גיל אתה מרגיש שהתחילו באמת ה\"נעורים\" שלך?",
        "איך נראית התקופה הזו עבורך — היית יותר מרדן, סקרן, רומנטיקן, ביישן?",
        "תוכל לתאר איך נראית השכונה, העיר או בית הספר באותן שנים?",
        "מי היו החברים הקרובים שלך בגיל ההתבגרות? מה חיבר ביניכם?",
        "איזה מוזיקה שמעת אז — ואיזה שיר ישר מחזיר אותך לתקופה ההיא?",
        "היה לך מקום קבוע שבו הייתם נפגשים — גג, גינה, קניון, חוף?",
        "איך היית מתלבש אז? היו סגנונות או טרנדים שמזוהים איתך?",
        "מה היה גורם לך להרגיש \"שייך\"?",
        "מתי בפעם הראשונה הרגשת שאתה שונה — במחשבה, בטעם, או בדרך שבה אתה רואה את העולם?",
        "אילו תחביבים או עיסוקים מילאו את זמנך אז?",
        "תוכל לספר על אהבה ראשונה — איך זה התחיל, איך זה נגמר, מה למדת מזה?",
        "מי היה המודל לחיקוי שלך באותה תקופה?",
        "איך היו היחסים עם ההורים באותן שנים?",
        "האם הרגשת חופש או מגבלות בבית / בבית הספר?",
        "מתי בפעם הראשונה עמדת על שלך או עשית משהו \"בניגוד לחוקים\"?",
        "מה היה החלום שלך אז לגבי העתיד?",
        "אם היית צריך לבחור רגע אחד שמסמל את הנעורים שלך — מהו?",
        "איך חווית את בית הספר התיכון — למדת ברצון, השתעממת, חיפשת את עצמך?",
        "היה לך מורה או מדריך שנשאר לך בזיכרון במיוחד?",
        "איך נראתה תקופת הבגרויות או סיום בית הספר עבורך?",
        "אילו חופשות, טיולים או חוויות קבוצתיות אתה זוכר מהתקופה הזו?",
        "אם היית יכול לדבר היום עם עצמך בגיל 16, מה היית אומר לו?",
        "איך נראתה החברות הראשונה שלך — מה למדת ממנה על עצמך?",
        "מה היית רוצה שילדיך או נכדיך ידעו עליך בגיל הזה?",
        "באיזו מילה אחת היית מתאר את תקופת הנעורים שלך?"
    ],
    "4": [
        "מתי בפעם הראשונה הרגשת אהבה? איך זה הרגיש?",
        "אתה זוכר את הפעם הראשונה שהתאהבת באמת? איך התחיל הקשר הזה?",
        "מה משך אותך באדם שאהבת לראשונה?",
        "איך היית מתאר את עצמך במערכות יחסים בגיל צעיר?",
        "מה למדת על עצמך מהאהבה הראשונה שלך?",
        "איך נראתה תקופת החיזור אצלך — מה היה נחשב “רומנטי”?",
        "תוכל לספר על רגע מצחיק או מביך שקרה לך באחת האהבות שלך?",
        "איך ידעת שפגשת אדם שאתה רוצה לחלוק איתו את חייך?",
        "מה גרם לך להרגיש ביטחון ואמון בקשר זוגי?",
        "אילו תכונות חיפשת או הערכת בבן/בת זוג?",
        "איך היו נראים הרגעים הקטנים של אהבה — לא המחוות הגדולות, אלא היומיום?",
        "תוכל לתאר רגע שבו הרגשת אהוב באמת?",
        "איך התמודדתם עם חילוקי דעות או תקופות קשות בזוגיות?",
        "מה למדת על תקשורת ואמון ממערכות היחסים שלך?",
        "אילו ערכים היו חשובים לך בתוך זוגיות?",
        "אם הייתה תקופה של פרידה או לב שבור — מה עזר לך לעבור אותה?",
        "איך השתנתה בעיניך המשמעות של אהבה לאורך השנים?",
        "אילו דמויות או זוגות בחייך היו עבורך מודל לאהבה טובה?",
        "איך הרגשת ביום שבו נישאת (אם נישאת)? מה אתה זוכר מהרגעים סביב זה?",
        "איזה שיר, מקום או ריח מזכיר לך אהבה גדולה?",
        "האם אתה חושב שיש דבר כזה “אהבה אחת ויחידה”?",
        "מה גורם לזוגיות להחזיק לאורך זמן, לדעתך?",
        "אם היית צריך לייעץ לנכד/ה שלך על אהבה — מה היית אומר?",
        "מה הכי מרגש אותך בזוגיות שלך עד היום?",
        "מה למדת על אהבה — במובן העמוק ביותר של המילה?"
    ],
    "5": [
        "איך הרגשת כשעמדת לפני השלב הזה — גיוס, שירות לאומי, או תחילת לימודים?",
        "איך בחרת את המסלול שלך — זה היה חלום, החלטה רציונלית או פשוט מה שיצא?",
        "תוכל לתאר את היום הראשון שלך בצבא או בלימודים? מה עובר לך בראש כשאתה נזכר בו?",
        "מי היו האנשים הראשונים שהכרת שם, והאם נשארתם בקשר?",
        "אילו תכונות שלך בלטו במיוחד בתקופה הזו?",
        "היה מישהו שראית בו מפקד, מדריך או מורה לחיים? מה למדת ממנו?",
        "תוכל לספר על חוויה משמעותית במיוחד מהשירות או מהלימודים?",
        "היה רגע שבו הרגשת גאווה אמיתית בעצמך?",
        "ומה עם רגע קשה — איך התמודדת איתו?",
        "איך השתנתה הדרך שבה ראית את עצמך באותה תקופה?",
        "האם זו הייתה תקופה של חופש ועצמאות או של אתגרים ולחצים?",
        "אילו חברויות נוצרו לך שם, ומה היה מיוחד בהן?",
        "תוכל לתאר סיטואציה מצחיקה או בלתי נשכחת מהשירות או מהקמפוס?",
        "אם למדת מקצוע — למה דווקא אותו, והאם אתה חושב שזה היה הבחירה הנכונה?",
        "האם היו אנשים שפתחו לך דלת או האמינו בך במיוחד?",
        "איך נראו הימים שלך — שגרה, משימות, לימודים, חופשות?",
        "מה היה בשבילך הדבר הכי מאתגר באותה תקופה?",
        "האם היה רגע שבו הרגשת שאתה מתבגר באמת?",
        "איך שמרת על קשר עם הבית והמשפחה בתקופה הזו?",
        "האם התגעגעת למשהו מהחיים שלפני כן?",
        "תוכל לתאר מקום מסוים מהשירות או מהלימודים שנחרט לך בזיכרון?",
        "מה למדת שם על אנשים — על חברות, על אמון, על שיתופי פעולה?",
        "האם היו חלומות או תכניות שצמחו באותן שנים?",
        "איך התקופה הזו תרמה לעיצוב מי שאתה היום?",
        "אם היית יכול לפגוש את עצמך ביום השחרור או סיום הלימודים — מה היית אומר לעצמך?"
    ],
    "6": [
        "מה הייתה העבודה או העיסוק הראשון שלך? איך הגעת אליו?",
        "איך הרגשת ביום הראשון שלך בעבודה?",
        "מי היה האדם הראשון שלימד אותך “איך הדברים באמת עובדים”?",
        "מה גרם לך לבחור במקצוע או בתחום שבו עסקת רוב חייך?",
        "אילו ערכים ניסית להביא איתך לעבודה?",
        "היה רגע שבו הרגשת שאתה “במקום הנכון”?",
        "ומה עם רגע שבו הרגשת תקוע או מאוכזב?",
        "מה למדת על עצמך דרך העבודה?",
        "איך היית מתאר את היחסים שלך עם קולגות, עובדים או מנהלים?",
        "תוכל לספר על החלטה מקצועית משמעותית שקיבלת — ומדוע?",
        "היה פרויקט, משימה או הישג שאתה זוכר בגאווה מיוחדת?",
        "אם היית צריך לבחור תכונה אחת שעזרה לך להצליח — מה היא?",
        "איך הצלחת לשמור על איזון בין עבודה לבית ולחיים האישיים?",
        "היו רגעים שבהם שקלת לשנות כיוון? מה גרם לך להישאר או לעבור?",
        "תוכל לתאר אדם בעבודה שהשפיע עליך במיוחד?",
        "איך היית מתמודד עם לחץ או עם מצבים לא פשוטים בעבודה?",
        "מה גרם לך תחושת משמעות אמיתית בעשייה שלך?",
        "האם הייתה תקופה שבה עבדת קשה במיוחד, ומה למדת ממנה?",
        "אם ניהלת אנשים — מה למדת על הנהגה ועל עבודה עם אחרים?",
        "אילו לקחים היית רוצה להעביר לדור הצעיר על קריירה ובחירות מקצועיות?",
        "איך היית מתאר את עצמך כעובד או כעמית לצוות?",
        "מהו הרגע שבו הכי הרגשת מוערך בעבודה?",
        "ומהו הרגע שבו היית צריך להתחזק או לעמוד על שלך?",
        "אם היית יכול לחזור אחורה — האם היית בוחר באותו מסלול?",
        "איך היית רוצה שיזכרו את העשייה שלך — מה החותם שהשארת?"
    ],
    "7": [
        "תמיד רצית להיות הורה?",
        "אתה זוכר את הרגע שבו הפכת להורה? איך הרגשת באותו יום?",
        "איך בחרתם את השמות לילדים שלכם? יש מאחוריהם סיפור מיוחד?",
        "מה השתנה בחיים שלך מרגע שנולדו הילדים?",
        "איך היית מתאר את עצמך כהורה בתחילת הדרך?",
        "מה היה הדבר שהכי הפחיד אותך בהורות — ומה היה הדבר הכי מרגש?",
        "מהו זיכרון ילדות חזק שלך מהתקופה שבה הילדים היו קטנים?",
        "אילו רגעים משפחתיים יומיומיים אתה זוכר באהבה?",
        "היה טקס, מסורת או הרגל משפחתי שהיה חשוב לך לשמור עליו בבית?",
        "איך נראתה השגרה שלכם כמשפחה?",
        "מה למדת מהילדים שלך — אולי משהו שלא ציפית ללמוד?",
        "היה רגע שבו הבנת שאתה באמת “הורה”?",
        "איך התמודדתם עם אתגרים או קשיים — בריאותיים, כלכליים או רגשיים?",
        "תוכל לספר על רגע שבו הרגשת גאווה אמיתית בילדיך?",
        "ומה עם רגע של דאגה או פחד גדול?",
        "איך חילקתם את האחריות בבית — מי עשה מה, ואיך זה עבד?",
        "אילו ערכים ניסית להעביר לילדיך?",
        "איך נראתה אצלכם ארוחת ערב משפחתית — על מה דיברתם, איך הייתה האווירה?",
        "אילו הרגלים או מנהגים מהבית שלך ניסית לשמר — ואילו שינית?",
        "היה רגע שבו למדת לבקש סליחה או להקשיב אחרת לילדים שלך?",
        "איך היית מתאר את היחסים בינך לבין כל אחד מהילדים — מה מיוחד בכל אחד מהם?",
        "איך השתנתה הזוגיות שלכם עם השנים ועם ההורות?",
        "מהו אחד הזיכרונות הכי יפים שלך כמשפחה?",
        "מה היית רוצה שילדיך יזכרו ממך כשיחשבו על הילדות שלהם?",
        "אם היית יכול לחזור אחורה — יש משהו שהיית עושה אחרת כהורה?",
        "כשאתה מסתכל על המשפחה שלך היום — במה אתה הכי גאה?"
    ],
    "8": [
        "מי היה החבר או החברה הראשונים שאתה זוכר מהילדות?",
        "מה לדעתך יוצר חברות טובה באמת?",
        "תוכל לספר על חברות שנמשכה שנים רבות? מה החזיק אותה?",
        "איך אתה בוחר במי לתת אמון?",
        "היה לך חבר או חברה שהרגשת שהם “כמו משפחה”?",
        "איך שמרת על קשרים לאורך השנים — עם המעברים, השינויים והזמן?",
        "היה ריב או נתק עם חבר קרוב? איך זה הרגיש, ומה קרה אחר כך?",
        "תוכל לספר על מישהו שעזר לך בתקופה קשה?",
        "ומה עם מישהו שאתה עזרת לו — רגע שבו היית שם בשביל אחר?",
        "אילו חוויות משותפות הכי חיזקו את הקשרים שלך עם אחרים?",
        "תוכל לתאר מפגש חברים או בילוי שנחרט לך בזיכרון?",
        "האם יש קבוצה או קהילה שאתה מרגיש חלק ממנה — בבית, בעבודה, בשכונה או בתחביבים?",
        "איך התחושה להיות שייך למקום או לקבוצה?",
        "האם היה שלב בחיים שבו הרגשת לבד או מנותק חברתית? איך יצאת מזה?",
        "מה אתה הכי מעריך באנשים שאתה מוקף בהם?",
        "תוכל לתאר אדם אחד מחייך החברתיים שהשפיע עליך במיוחד?",
        "איך השתנו מערכות היחסים החברתיות שלך לאורך השנים?",
        "מה היה תפקידך בחבורה — היית המקשיב, המצחיק, המארגן?",
        "איך חוגגים אצלך עם חברים — יום הולדת, חג, ערב רגיל?",
        "האם אתה מרגיש שיש לך מעגל תמיכה — אנשים שאתה יכול לסמוך עליהם באמת?",
        "תוכל לספר על מפגש לא צפוי עם אדם מהעבר?",
        "מה למדת מחברות שנגמרה — על עצמך או על החיים?",
        "האם היו אנשים שהפכו מחברים לשותפים לעבודה, או להפך?",
        "מה גורם לך להרגיש שייך — מקום, אנשים, ערכים?",
        "אם היית צריך לבחור אדם אחד שילווה אותך לכל החיים — מי זה היה ולמה?"
    ],
    "9": [
        "אילו דברים אהבת לעשות בזמנך הפנוי כשהיית צעיר?",
        "מהו התחביב הראשון שאתה זוכר שהיה ממש “שלך”?",
        "איך התחלת לעסוק בו — במקרה, ממישהו שלימד אותך, או פשוט סקרנות?",
        "מה גורם לך תחושת רוגע או שמחה אמיתית?",
        "אילו תחביבים מלווים אותך עד היום?",
        "האם אתה טיפוס של יצירה, תנועה, למידה, או אולי הכול יחד?",
        "תוכל לתאר רגע שבו פשוט הרגשת “באזור שלך” — לגמרי נוכח ומאושר?",
        "האם יש פעילות שאתה חולם תמיד לנסות אבל עוד לא הספקת?",
        "אילו חפצים, כלים או פריטים מתקשרים אצלך לתחביבים שלך?",
        "אם היית צריך לבחור יום חופש מושלם — איך הוא היה נראה?",
        "האם אתה נהנה יותר מפעילויות לבד או בחברה?",
        "היה לך תקופה שבה גילית תחביב חדש לגמרי? איך זה קרה?",
        "מה אתה אוהב לעשות כשיש לך זמן לעצמך בלבד?",
        "תוכל לספר על מקום שאתה אוהב ללכת אליו כדי “לנקות את הראש”?",
        "האם יש פעילות שאתה משתף בה גם את המשפחה או החברים?",
        "מה המוזיקה, הסרטים או הספרים שאתה חוזר אליהם שוב ושוב?",
        "אילו טיולים, נופים או מקומות מרגשים במיוחד עבורך?",
        "האם אתה אוהב ליצור במו ידיך — לבשל, לבנות, לצייר, לכתוב?",
        "היה רגע שבו תחביב הפך למשהו גדול יותר — אולי לעיסוק או שליחות?",
        "אם היית צריך לתאר את עצמך דרך תחביביך — מה הם היו מספרים עליך?",
        "איך אתה אוהב לנוח אחרי יום עמוס?",
        "אילו פעילויות קטנות עושות לך שמח ביומיום?",
        "תוכל לזכור חוויה מצחיקה או מיוחדת שקרתה תוך כדי עיסוק בתחביב שלך?",
        "האם היית רוצה ללמוד משהו חדש היום — תחום, שפה, כלי נגינה, ספורט?",
        "מה בעיניך הזמן הפנוי האידיאלי — שקט, מלא תנועה, או שילוב ביניהם?"
    ],
    "10": [
        "אילו ערכים היית אומר שמלווים אותך כל חייך?",
        "מאיפה למדת את הערכים האלה — מהבית, מהחיים, מהניסיון?",
        "יש משפט, אמירה או כלל שאתה משתדל לחיות לפיו?",
        "מה בעיניך חשוב יותר — כנות, נדיבות, אהבה, אחריות, או משהו אחר?",
        "איך אתה מגדיר מהו “אדם טוב”?",
        "היו רגעים שבהם הערכים שלך עמדו למבחן?",
        "אילו דברים אתה מתקשה לסלוח עליהם — ולאיזה דברים אתה מוכן לוותר בקלות?",
        "האם יש אדם שאתה רואה בו דוגמה לערכים שאתה מעריך?",
        "מה בעיניך הדבר הנכון לעשות כשיש התנגשות בין מה שאתה רוצה למה שאתה מאמין בו?",
        "איך אתה מתמודד עם קונפליקטים מוסריים או מצפוניים?",
        "האם יש עיקרון שאתה משתדל להעביר לילדיך או לנכדיך?",
        "איך אתה מתייחס לדת או לרוחניות — האם יש לזה מקום בחייך?",
        "האם אתה מאמין שיש משהו מעבר למה שאנחנו רואים כאן ועכשיו?",
        "אילו חגים, טקסים או מסורות משמעותיים עבורך — ומדוע?",
        "תוכל לתאר רגע שבו הרגשת חיבור רוחני, גם אם לא דתי?",
        "האם יש ערך שלמדת רק בגיל מאוחר — אחרי שנפלת, חווית, או ראית משהו בעיניים אחרות?",
        "מה אתה חושב שמחזיק משפחה או חברה ביחד — על מה זה נשען?",
        "אילו דברים אתה לא מוכן לוותר עליהם לעולם?",
        "האם היה זמן שבו שינת דעה או אמונה שהייתה לך בעבר?",
        "מה אתה חושב על מושגים כמו גורל, מזל או בחירה חופשית?",
        "איך אתה מתמודד עם טעויות שלך — האם אתה סלחן כלפי עצמך?",
        "מה אתה מרגיש שנותן משמעות לחיים שלך?",
        "אילו ערכים היית רוצה שיזכרו אותך לפיהם?",
        "מה אתה חושב שהעולם שלנו צריך יותר ממנו כיום?",
        "אם היית צריך להעביר מסר אחד לדור הבא — מה הוא היה?"
    ],
    "11": [
        "האם תוכל לספר על תקופה קשה בחיים שלך — ומה עזר לך לעבור אותה?",
        "איך אתה נוטה להתמודד כשמגיעים אתגרים או משברים?",
        "היה רגע שבו הרגשת שאתה מאבד כיוון — ומה עזר לך למצוא אותו מחדש?",
        "האם חווית אובדן משמעותי בחייך? איך התמודדת עם התחושות שאחריו?",
        "מהו הדבר שלמדת על עצמך דווקא מתוך כאב או קושי?",
        "מי היו האנשים שהיו לצידך ברגעים האלה?",
        "היה מישהו שהפתיע אותך בתמיכה שלו?",
        "האם יש משפט, אמונה או מחשבה שעזרה לך “להחזיק מעמד”?",
        "מה עוזר לך למצוא תקווה כשדברים נראים אבודים?",
        "תוכל לתאר רגע שבו הבנת שאתה חזק יותר ממה שחשבת?",
        "האם יש חוויה קשה שהפכה אחר כך להזדמנות לצמיחה?",
        "איך אתה מתמודד עם פרידות — מאנשים, ממקומות, מתקופות בחיים?",
        "היה מקרה שבו היית צריך לסלוח — לעצמך או למישהו אחר?",
        "אילו תובנות קיבלת מתקופות מאתגרות שעברת?",
        "מה למדת על החיים מהמקומות הפחות פשוטים?",
        "האם יש רגע שבו הרגשת שינוי פנימי גדול — כמו “משהו נפל למקום”?",
        "מי או מה נותן לך תחושת יציבות כשאתה מתמודד עם סערה?",
        "איך אתה מדבר עם עצמך ברגעים קשים — באיזה קול פנימי?",
        "האם יש משהו מהעבר שלא סופר או לא נגעת בו עד היום?",
        "איך אתה נפרד מדברים שכבר לא שלך — יחסים, תקופות, חלומות?",
        "האם חווית רגע שבו מישהו הציל אותך, במובן רגשי או ממשי?",
        "מה למדת על חמלה — כלפי עצמך וכלפי אחרים?",
        "תוכל לספר על רגע שבו בחרת להמשיך הלאה למרות הכול?",
        "מה עוזר לך להרגיש שלווה אחרי סערה?",
        "כשאתה מסתכל אחורה — מהו השיעור הכי גדול שהחיים לימדו אותך?"
    ],
    "12": [
        "כשאתה מביט אחורה על חייך — מה אתה רואה קודם כל?",
        "אילו רגעים קטנים אתה הכי מעריך היום, במבט לאחור?",
        "מה בעיניך המשמעות של חיים טובים?",
        "אם היית צריך לבחור שלושה דברים שאתה גאה בהם במיוחד — מה הם?",
        "מה היית אומר לגרסה הצעירה של עצמך, לו היית פוגש אותה היום?",
        "האם יש משהו שהיית רוצה לעשות אחרת — או אולי בכלל לא לשנות?",
        "איזה חולם היית בילדותך — ומה מהחלומות ההם התגשם?",
        "יש חלום שעדיין לא הגשמת, אבל אתה עדיין מאמין בו?",
        "אילו דברים קטנים אתה עוד רוצה לחוות או לנסות?",
        "איך אתה מדמיין את השנים הבאות?",
        "מה גורם לך להרגיש חי באמת?",
        "מה אתה מאחל לעצמך לעתיד?",
        "איך אתה רוצה שיזכרו אותך — כאדם, כהורה, כחבר, כאיש משפחה?",
        "אילו מסרים היית רוצה להשאיר לדורות הבאים במשפחה שלך?",
        "מה למדת על אהבה, על זמן, על החיים עצמם?",
        "האם יש משהו שאתה מרגיש שסגרת איתו מעגל?",
        "על מה אתה רוצה להמשיך ללמוד, להתפתח או להתעניין?",
        "מה גורם לך עדיין להתרגש או להתלהב כמו פעם?",
        "האם יש דבר שתרצה לספר ולא יצא לך אף פעם — משהו שחשוב לך שיישמע?",
        "אם היית כותב מכתב לעתיד שלך — מה היית כותב בו?",
        "מה אתה מאחל לעולם של הדור הבא?",
        "אילו הרגלים או ערכים היית רוצה שיעברו הלאה מהמשפחה שלך?",
        "איך אתה מתמודד עם הזמן שעובר — עם שינויים, זיכרונות, געגועים?",
        "אם היית יכול לתמצת את כל מה שלמדת במשפט אחד — מה הוא היה?",
        "כשאתה חושב על סיפור חייך, מה הכותרת שהיית נותן לו?"
    ],
}



# ANSWERS dictionary removed - now using database

class ChapterOut(BaseModel):
    id: str
    title: str

class QuestionOut(BaseModel):
    id: str
    chapter_id: str
    text: str
    order: int

class UpsertQuestionsIn(BaseModel):
    chapter_id: str
    questions: List[str]

class AnswerIn(BaseModel):
    person_id: str
    chapter_id: str
    question_id: str
    text: str
    audio_url: Optional[str] = None

class StoryChapterIn(BaseModel):
    person_id: str
    chapter_id: str
    style_guide: Optional[str] = None
    context_summary: Optional[str] = None

class StoryCompileIn(BaseModel):
    person_id: str
    style_guide: Optional[str] = None

class UserOut(BaseModel):
    id: str
    person_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    picture: Optional[str] = None
    oauth_provider: Optional[str] = None
    can_use_llm: bool = False
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class UpdateLLMPermissionIn(BaseModel):
    user_id: Optional[str] = None  # UUID as string
    person_id: Optional[str] = None
    email: Optional[str] = None
    can_use_llm: bool

def ensure_chapter(ch_id: str, db: Session):
    """Ensure a chapter exists in the database."""
    chapter = db.query(Chapter).filter(Chapter.id == ch_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found")
    return chapter


def get_or_create_user(person_id: str, db: Session) -> User:
    """Get or create a user by person_id (legacy function for backward compatibility)."""
    user = db.query(User).filter(User.person_id == person_id).first()
    if not user:
        user = User(person_id=person_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_question_text(question_id: str) -> Optional[str]:
    """
    Get the question text from question_id.
    
    Args:
        question_id: Question ID in format "chapter-order" (e.g., "1-01")
        
    Returns:
        Question text or None if not found
    """
    try:
        parts = question_id.split("-")
        if len(parts) != 2:
            return None
        
        chapter_id = parts[0]
        order = int(parts[1])
        
        questions = RAW_QUESTIONS.get(chapter_id, [])
        if 1 <= order <= len(questions):
            return questions[order - 1].strip()
    except (ValueError, IndexError):
        pass
    
    return None


def verify_llm_permission(user: User) -> None:
    """
    Verify that the user has permission to make LLM API calls.
    
    Args:
        user: User object to check
        
    Raises:
        HTTPException: If user doesn't have LLM permission
    """
    if not user.can_use_llm:
        raise HTTPException(
            status_code=403,
            detail="LLM API access denied. You don't have permission to use LLM features. Please contact support to enable this feature."
        )


# ==================== Authentication Routes ====================

@app.get("/api/auth/google/login")
async def google_login():
    """Initiate Google OAuth login flow."""
    settings = get_settings()
    
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )
    
    # Google OAuth2 authorization URL
    # Note: redirect_uri should match what's configured in Google Cloud Console
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        "scope=openid email profile&"
        "access_type=offline&"
        "prompt=consent"
    )
    
    return RedirectResponse(url=google_auth_url)


@app.get("/api/auth/google/callback")
async def google_callback(
    code: str,
    db: Session = Depends(get_db)
):
    """Handle Google OAuth callback and create/login user."""
    settings = get_settings()
    
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured"
        )
    
    # Use backend URL for callback (must match Google Cloud Console configuration)
    redirect_uri = f"{settings.BACKEND_URL}/api/auth/google/callback"
    
    # Exchange authorization code for access token
    async with get_google_oauth_client() as client:
        token_response = await client.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
            redirect_uri=redirect_uri,
        )
        
        access_token = token_response.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400,
                detail="Failed to obtain access token"
            )
        
        # Get user info from Google
        user_info = await get_google_user_info(access_token)
    
    # Get or create user
    user = get_or_create_user_from_oauth(
        oauth_provider="google",
        oauth_id=user_info.get("id"),
        email=user_info.get("email"),
        name=user_info.get("name"),
        picture=user_info.get("picture"),
        db=db,
    )
    
    # Create JWT token
    access_token_jwt = create_access_token(data={"sub": str(user.id)})
    
    # Redirect to frontend with token
    frontend_url = settings.FRONTEND_URL
    token_param = urlencode({"token": access_token_jwt})
    return RedirectResponse(url=f"{frontend_url}/auth/callback?{token_param}")


@app.get("/api/auth/me", response_model=UserOut)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return UserOut(
        id=str(current_user.id),
        person_id=current_user.person_id,
        name=current_user.name,
        email=current_user.email,
        picture=current_user.picture,
        oauth_provider=current_user.oauth_provider,
        can_use_llm=current_user.can_use_llm,
    )


@app.post("/api/auth/logout")
async def logout():
    """Logout endpoint (client should remove token)."""
    return {"message": "Logged out successfully"}


@app.post("/api/admin/llm-permission")
async def update_llm_permission(
    payload: UpdateLLMPermissionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update LLM permission for a user.
    
    Note: In production, you should add admin role checking here.
    For now, any authenticated user can grant/revoke permissions.
    """
    # Find the target user
    user = None
    
    if payload.user_id:
        try:
            user = db.query(User).filter(User.id == UUID(payload.user_id)).first()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid user_id format"
            )
    elif payload.person_id:
        user = db.query(User).filter(User.person_id == payload.person_id).first()
    elif payload.email:
        user = db.query(User).filter(User.email == payload.email).first()
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide one of: user_id, person_id, or email"
        )
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Update permission
    user.can_use_llm = payload.can_use_llm
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"LLM permission {'granted' if payload.can_use_llm else 'revoked'} successfully",
        "user": {
            "id": str(user.id),
            "person_id": user.person_id,
            "email": user.email,
            "can_use_llm": user.can_use_llm
        }
    }


# ==================== API Routes ====================

@app.get("/api/chapters", response_model=List[ChapterOut])
def list_chapters(db: Session = Depends(get_db)):
    """List all available chapters."""
    chapters = db.query(Chapter).order_by(Chapter.order).all()
    return [{"id": ch.id, "title": ch.title} for ch in chapters]

@app.get("/api/questions", response_model=List[QuestionOut])
def get_questions(chapter: str, db: Session = Depends(get_db)):
    """Get questions for a specific chapter."""
    ensure_chapter(chapter, db)
    raw = RAW_QUESTIONS.get(chapter, [])
    items = [
        {"id": f"{chapter}-{i:02d}", "chapter_id": chapter, "text": q.strip(), "order": i}
        for i, q in enumerate(raw, start=1)
    ]
    return items

@app.post("/api/questions", response_model=List[QuestionOut])
def upsert_questions(payload: UpsertQuestionsIn, db: Session = Depends(get_db)):
    """Upsert questions for a chapter."""
    ensure_chapter(payload.chapter_id, db)
    items = []
    for i, qtext in enumerate(payload.questions, start=1):
        qid = f"{payload.chapter_id}-{i:02d}"
        items.append({
            "id": qid,
            "chapter_id": payload.chapter_id,
            "text": (qtext or "").strip(),
            "order": i,
        })
    return items


@app.post("/api/answers")
def add_answer(
    ans: AnswerIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add or update an answer to a question (upsert)."""
    ensure_chapter(ans.chapter_id, db)
    
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if ans.person_id and ans.person_id != current_user.person_id:
        # If person_id is provided and different, use it (backward compatibility)
        user = get_or_create_user(ans.person_id, db)
    else:
        user = current_user
    
    # Check if answer already exists for this user, chapter, and question
    existing_answer = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == ans.chapter_id,
        Answer.question_id == ans.question_id
    ).first()
    
    if existing_answer:
        # Update existing answer
        existing_answer.text = ans.text
        if ans.audio_url:
            existing_answer.audio_url = ans.audio_url
        db.commit()
        db.refresh(existing_answer)
        return {"ok": True, "answer_id": str(existing_answer.id), "updated": True}
    else:
        # Create new answer
        answer = Answer(
            user_id=user.id,
            chapter_id=ans.chapter_id,
            question_id=ans.question_id,
            text=ans.text,
            audio_url=ans.audio_url,
        )
        db.add(answer)
        try:
            db.commit()
            db.refresh(answer)
            return {"ok": True, "answer_id": str(answer.id), "updated": False}
        except IntegrityError:
            # Handle race condition: if another request created the answer between our check and insert
            db.rollback()
            # Try to get the existing answer again
            existing_answer = db.query(Answer).filter(
                Answer.user_id == user.id,
                Answer.chapter_id == ans.chapter_id,
                Answer.question_id == ans.question_id
            ).first()
            if existing_answer:
                # Update it
                existing_answer.text = ans.text
                if ans.audio_url:
                    existing_answer.audio_url = ans.audio_url
                db.commit()
                db.refresh(existing_answer)
                return {"ok": True, "answer_id": str(existing_answer.id), "updated": True}
            else:
                # This shouldn't happen, but handle it anyway
                raise HTTPException(status_code=500, detail="Failed to save answer")

@app.get("/api/answers")
def get_answers(
    chapter: str,
    person_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get answers for a person and chapter."""
    ensure_chapter(chapter, db)
    
    # Use authenticated user or person_id parameter (if provided and matches)
    if person_id:
        user = db.query(User).filter(User.person_id == person_id).first()
        if not user:
            return []
        # Verify it matches current user (security)
        if user.id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only access your own answers"
            )
    else:
        user = current_user
    
    # Get answers
    answers = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == chapter
    ).order_by(Answer.created_at).all()
    
    return [
        {
            "id": str(ans.id),
            "question_id": ans.question_id,
            "text": ans.text,
            "audio_url": ans.audio_url,
            "created_at": ans.created_at.isoformat(),
        }
        for ans in answers
    ]

@app.post("/api/story/chapter")
async def story_chapter(
    payload: StoryChapterIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a chapter narrative from answers using LLM."""
    ensure_chapter(payload.chapter_id, db)
    
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if payload.person_id and payload.person_id != current_user.person_id:
        user = get_or_create_user(payload.person_id, db)
    else:
        user = current_user
    
    # Fetch answers for this chapter
    chapter_answers = db.query(Answer).filter(
        Answer.user_id == user.id,
        Answer.chapter_id == payload.chapter_id
    ).order_by(Answer.created_at).all()
    
    if not chapter_answers:
        raise HTTPException(
            status_code=400,
            detail=f"No answers found for person {payload.person_id} in chapter {payload.chapter_id}"
        )
    
    # Get current chapter info for ordering
    current_chapter = ensure_chapter(payload.chapter_id, db)
    
    # Get previous chapter summaries for context
    previous_summaries = []
    if not payload.context_summary:
        # Get all previous chapters (with lower order number)
        previous_chapters = db.query(StoryChapter).filter(
            StoryChapter.user_id == user.id,
            StoryChapter.summary.isnot(None)  # Only chapters with summaries
        ).join(Chapter).filter(
            Chapter.order < current_chapter.order
        ).order_by(Chapter.order).all()
        
        # Build context summary from previous chapter summaries
        if previous_chapters:
            previous_summaries = [
                f"פרק {sc.chapter_id} ({sc.chapter.title}): {sc.summary}"
                for sc in previous_chapters
            ]
            context_summary = "\n\n".join(previous_summaries)
        else:
            context_summary = payload.context_summary or "אין תקציר מהפרקים הקודמים."
    else:
        context_summary = payload.context_summary
    
    # Convert answers to facts format
    facts = [
        {
            "question_id": ans.question_id,
            "question": get_question_text(ans.question_id) or "",
            "text": ans.text,
            "created_at": ans.created_at.isoformat(),
        }
        for ans in chapter_answers
    ]
    
    # Verify LLM permission before making API calls
    verify_llm_permission(user)
    
    # Generate narrative using LLM
    if llm is None:
        # Fallback if LLM not initialized
        narrative = f"[Stub] Narrative for chapter {payload.chapter_id} based on {len(chapter_answers)} answers. LLM not configured."
        summary = ""
    else:
        try:
            narrative = await llm.agenerate_chapter(
                person_id=payload.person_id,
                chapter_id=payload.chapter_id,
                facts=facts,
                style_guide=payload.style_guide,
                context_summary=context_summary,
            )
            narrative = narrative or f"[Generated] Narrative for chapter {payload.chapter_id}"
            
            # Generate summary from the narrative
            summary = await llm.agenerate_summary(narrative)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate chapter narrative: {str(e)}"
            )
    
    # Save or update story chapter in database
    existing = db.query(StoryChapter).filter(
        StoryChapter.user_id == user.id,
        StoryChapter.chapter_id == payload.chapter_id
    ).first()
    
    if existing:
        existing.narrative = narrative
        existing.summary = summary
        existing.style_guide = payload.style_guide
        existing.context_summary = context_summary
        db.commit()
        db.refresh(existing)
    else:
        story_chapter = StoryChapter(
            user_id=user.id,
            chapter_id=payload.chapter_id,
            narrative=narrative,
            summary=summary,
            style_guide=payload.style_guide,
            context_summary=context_summary,
        )
        db.add(story_chapter)
        db.commit()
        db.refresh(story_chapter)
    
    return {
        "chapter_id": payload.chapter_id,
        "narrative": narrative,
        "summary": summary
    }

class StoryChapterOut(BaseModel):
    chapter_id: str
    narrative: str
    summary: Optional[str] = None
    style_guide: Optional[str] = None
    context_summary: Optional[str] = None
    created_at: str
    updated_at: str

@app.get("/api/story/chapter/{chapter_id}", response_model=Optional[StoryChapterOut])
async def get_story_chapter(
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a story chapter from the database by chapter_id. Returns null if not found."""
    ensure_chapter(chapter_id, db)
    
    # Get story chapter for current user
    story_chapter = db.query(StoryChapter).filter(
        StoryChapter.user_id == current_user.id,
        StoryChapter.chapter_id == chapter_id
    ).first()
    
    if not story_chapter:
        # Return null instead of 404 - this is expected when story hasn't been generated yet
        return None
    
    return {
        "chapter_id": story_chapter.chapter_id,
        "narrative": story_chapter.narrative,
        "summary": story_chapter.summary,
        "style_guide": story_chapter.style_guide,
        "context_summary": story_chapter.context_summary,
        "created_at": story_chapter.created_at.isoformat(),
        "updated_at": story_chapter.updated_at.isoformat(),
    }

@app.post("/api/story/compile")
async def story_compile(
    payload: StoryCompileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compile a full book from all chapters using LLM."""
    # Use authenticated user or fallback to person_id (for backward compatibility)
    if payload.person_id and payload.person_id != current_user.person_id:
        user = get_or_create_user(payload.person_id, db)
    else:
        user = current_user
    
    # Get all story chapters for this user
    story_chapters = db.query(StoryChapter).filter(
        StoryChapter.user_id == user.id
    ).join(Chapter).order_by(Chapter.order).all()
    
    if not story_chapters:
        raise HTTPException(
            status_code=400,
            detail=f"No story chapters found for person {payload.person_id}"
        )
    
    # Build chapters list with narratives
    chapters = []
    for story_ch in story_chapters:
        chapters.append({
            "id": story_ch.chapter_id,
            "title": story_ch.chapter.title,
            "narrative": story_ch.narrative,
        })
    
    # Verify LLM permission before making API calls
    verify_llm_permission(user)
    
    # Compile book using LLM
    if llm is None:
        # Fallback if LLM not initialized
        book_text = "[Stub] Full life story book text will appear here. LLM not configured."
    else:
        try:
            book_text = await llm.acompile_book(
                person_id=payload.person_id,
                chapters=chapters,
                style_guide=payload.style_guide,
            )
            book_text = book_text or "[Generated] Full life story book"
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compile book: {str(e)}"
            )
    
    # Save or update story in database
    existing = db.query(Story).filter(Story.user_id == user.id).first()
    
    if existing:
        existing.book_text = book_text
        existing.style_guide = payload.style_guide
        existing.chapters_used = len(chapters)
        db.commit()
        db.refresh(existing)
    else:
        story = Story(
            user_id=user.id,
            book_text=book_text,
            style_guide=payload.style_guide,
            chapters_used=len(chapters),
        )
        db.add(story)
        db.commit()
        db.refresh(story)
    
    return {
        "compiled": True,
        "book": book_text
    }

@app.get("/api/story/{person_id}")
async def get_story(
    person_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the compiled story for a person by person_id."""
    # Get user
    user = db.query(User).filter(User.person_id == person_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User not found for person_id {person_id}"
        )
    
    # Verify user can only access their own story
    if user.id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own story"
        )
    
    # Get story from database
    story = db.query(Story).filter(Story.user_id == user.id).first()
    
    if story is None:
        # Fallback to LLM if available
        if llm is not None:
            llm_story = llm.get_compiled_story(person_id)
            if llm_story:
                return {
                    "person_id": person_id,
                    "book": llm_story.get("book_text", ""),
                    "style_guide": llm_story.get("style_guide"),
                    "compiled_at": llm_story.get("compiled_at"),
                    "chapters_used": llm_story.get("chapters_used", 0),
                }
        
        raise HTTPException(
            status_code=404,
            detail=f"No compiled story found for person {person_id}"
        )
    
    return {
        "person_id": person_id,
        "book": story.book_text,
        "style_guide": story.style_guide,
        "compiled_at": story.compiled_at.isoformat(),
        "chapters_used": story.chapters_used,
    }
